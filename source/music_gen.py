import string
from collections import defaultdict
import shlex
import json
import string as literals
import os
import sys
import random
import re
import pathlib
import numpy
import pygame
import time
import math
import copy
import bz2
import wave
import datetime
import numpy as np
from random import randint, choice
import curses
from curses.textpad import Textbox, rectangle
from threading import Thread, Lock
import ctypes
import tempfile
import subprocess


"""
addstr = None
c = None
sc = None
lsc = None
rsc = None
log = None
jsd = None
"""

def name_by_temp_bps(bps):
    return ("grave" if 0 <= bps <= 44 else
            "largo" if 44 <= bps <= 52 else
            "adagio" if 52 <= bps <= 58 else
            "andante" if 58 <= bps <= 72 else
            "comodo" if 72 <= bps <= 80 else
            "moderato" if 80 <= bps <= 96 else
            "allegretto" if 96 <= bps <= 108 else
            "animato" if 108 <= bps <= 118 else
            "allegro" if 118 <= bps <= 144 else
            "allegro assai" if 144 <= bps <= 168 else
            "vivo" if 168 <= bps <= 176 else
            "vivace" if 176 <= bps <= 188 else
            "presto" if 188 <= bps <= 200 else
            "prestissimo")

class GeneratorTone:
    def __init__(self, tool, time, length, volume, frequency):
        self.tool = tool
        self.time = time
        self.length = length
        self.volume = volume
        self.frequency = frequency

class Generator:
    def __init__(self, api_function):
        self.api_function = api_function
        self.kernel = ""
        self.inputs: [GeneratorTone] = []

    def add(self, item):
        self.inputs.append(item)

    def adjust_start_time(self, start_time):
        self.inputs = list(filter(lambda x: x.time + 0.0001 >= start_time, self.inputs))
        for i in self.inputs:
            i.time -= start_time

    def compile(self, log_fn):
        # sort data
        self.inputs.sort(key=lambda x: x.time)

        # generate buffers
        result_length = int(128 + 44100 * max(map(lambda i: i.time + i.length, self.inputs)))
        result = np.zeros(result_length, dtype="float32")

        input_len = len(self.inputs)
        input_tools = np.zeros(input_len, dtype="int32")
        input_times = np.zeros(input_len, dtype="float32")
        input_lengths = np.zeros(input_len, dtype="float32")
        input_frequencies = np.zeros(input_len, dtype="float32")
        input_volumes = np.zeros(input_len, dtype="float32")

        # set
        for n, i in enumerate(self.inputs):
            input_tools[n] = self.inputs[n].tool
            input_times[n] = self.inputs[n].time
            input_lengths[n] = self.inputs[n].length
            input_frequencies[n] = self.inputs[n].frequency
            input_volumes[n] = self.inputs[n].volume

        # call
        try:
            self.api_function(result, result_length, input_tools, input_times, input_lengths, input_frequencies, input_volumes, input_len)
        except Exception as e:
            log_fn(f"{e.__class__.__name__} [in api call]: {e}", c.log.error)
        
        # return
        return result


class SynthesizerProjectTone:
    def __init__(self, tool, frequency, time, length, volume):
        self.tool = tool
        self.frequency = frequency
        self.time = time
        self.length = length
        self.volume = volume


class SynthesizerProjectNote:
    def __init__(self, text):
        self.text: str = text.strip()
        self.meta: jsd | None = None


class SynthesizerProjectTact:
    def __init__(self, time, tools_count):
        self.time = time
        self.notes: [[SynthesizerProjectNote]] = [[None] for i in range(tools_count)]
        self.meta = jsd()
        # len(notes[i]) should be similar for all i

    def insert_column(self, column_id):
        for i in self.notes:
            i.insert(column_id, None)

    def delete_column(self, column_id):
        for i in self.notes:
            i.pop(column_id)

    def to_string(self):
        d = {
            "time": self.time,
            "notes": list(map(lambda x: " ".join(map(lambda y: "" if y is None else y.text, x)),self.notes)),
            "meta": self.meta
        }
        return json.dumps(d)

    @staticmethod
    def from_string(s, tools_count):
        d = json.loads(s)
        x = SynthesizerProjectTact(d["time"], tools_count)
        if "meta" in d.keys():
            x.meta = jsd(d["meta"])
        for i in range(tools_count):
            x.notes[i].clear() # remove 'Nones'
        for k, i in enumerate(d["notes"]):
            for ii in i.split(" "):
                if ii == "":
                    x.notes[k].append(None)
                else:
                    x.notes[k].append(SynthesizerProjectNote(ii))
        # repair broken notes
        l = max(map(len, x.notes))
        for i in x.notes:
            while len(i) < l:
                i.append(None)
        return x

    @property
    def length(self):
        return len(self.notes[0])


class SynthesizerTool:
    def __init__(self, name, code=""):
        self.name = name
        self.code = code
        self.configs = jsd(
            mute=False,
            volume=1.0,
            legato_mod=1.0,
            stereo=False,
        )

    def copy(self):
        return self.from_string(self.to_string())

    def to_string(self):
        d = {
            "name": self.name,
            "code": self.code,
            "configs": dict(self.configs)
        }
        return json.dumps(d)

    @staticmethod
    def from_string(s):
        d = json.loads(s)
        x = SynthesizerTool(d["name"], d["code"])
        x.configs = jsd(d["configs"])
        return x

    @staticmethod
    def from_wave(log_fn, name, file, base_frequency_multipler=1.0, bass_boost=0.0, L=64, distortion=None):
        # read file
        sound = pygame.mixer.Sound(file)
        # sound.play(-1)
        y = pygame.sndarray.array(sound)
        # convert y to float64 in [-1.0, 1.0]
        y = y.astype('float64')
        # make one chanel from two
        if len(y.shape) == 2 and y.shape[1] == 2:
            y = (y[:,0] + y[:,1]) * 0.5
        # normalize y
        y = (y - np.min(y)) / (np.max(y) - np.min(y)) * 2.0 - 1.0
        # multiply y with window
        window = np.zeros(y.shape, y.dtype)
        for i in range(window.shape[0]):
            x = i / window.shape[0]
            window[i] = (1 - math.cos(math.pi * 2 * x) ) * 0.5
        y *= window
        # generate wave frequency information
        discrete = 1/44100  # interval of y
        a = np.fft.fft(y)
        f = np.fft.fftfreq(y.shape[0], d=discrete)

        # # a = np.abs(a)
        # a = np.fft.ifft(a)
        # raw = (np.tanh(a.real) * 32767.0).astype(dtype=np.int16)
        # raw = np.column_stack((raw, raw)).copy(order='C')
        # res = pygame.sndarray.make_sound(raw)
        # res.play()
        # while True:
        #     ...
        # exit(0)

        a = a[:y.shape[0]//2]
        f = f[:y.shape[0]//2]
        # remove some first frequencies (constant shifts)
        a = a[2:]
        f = f[2:]
        # sort other data
        mod = np.abs(a)
        mod = mod.argsort()[::-1]
        a = a[mod]
        p = np.zeros(f.shape, f.dtype)
        f = f[mod]
        for i in range(p.shape[0]):
            p[i] = math.atan2(a[i].real, a[i].imag)
        # amplitudes
        a = np.abs(a)
        # find base frequency:
        base_frequency = f[0] / base_frequency_multipler # max volume frequency
        f *= 1.0 / base_frequency

        # select biggest frequencies
        a_list = []
        p_list = []
        f_list = []

        K = 4

        for i in range(a.shape[0]):
            f1 = f[i]
            f2 = 1.0 / f1
            if (abs(f1 * K - round(f1 * K)) < 0.001 or abs(f2 * K - round(f2 * K)) < 0.001) and (f1 < L and f2 < L):
                a_list.append(a[i])
                p_list.append(p[i])
                f_list.append(f[i])

        if bass_boost < 1.0:
            bass_boost = 1/bass_boost
            for i in range(len(a_list)):
                if f_list[i] >= 1.0:
                    a_list[i] *= bass_boost
                if f_list[i] >= 2.0:
                    a_list[i] *= bass_boost
                if f_list[i] >= 4.0:
                    a_list[i] *= bass_boost
        else:
            for i in range(len(a_list)):
                if f_list[i] <= 1.0:
                    a_list[i] *= bass_boost
                if f_list[i] <= 0.5:
                    a_list[i] *= bass_boost
                if f_list[i] <= 0.25:
                    a_list[i] *= bass_boost

        a_sum = sum(a_list)
        for i in range(len(a_list)):
            a_list[i] /= a_sum

        if distortion is None:
            sin_txt = "sin_value"
        else:
            sin_txt = f"""
                (3 + {distortion}) * atan(5.0*sinh(0.25*sin_value)) / ({math.pi} + {distortion} * fabs(sin_value))
            """.replace(" "*12, " "*4)

        log_fn(f"Used {len(a_list)}/{a.shape[0]} frequencies, base: {base_frequency}")
        # generate code for file
        frq = ",".join(map(str, f_list))
        amp = ",".join(map(str, a_list))
        phs = ",".join(map(str, p_list))
        code = f"""
            float frq[] = {{
                {frq}
            }};
            float phs[] = {{
                {phs}
            }};
            float amp[] = {{
                {amp}
            }};
            
            float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
            v *= fmax(0.01f, k);
            
            float res = 0.0, dr;
            for (int i = 0; i < {len(a_list)}; ++i)
            {{
                float f = note->frequency * (frq[i]);
                float fv = amp[i];
                float x_pos = s * f / 44100.0f * 0.5 * 3.1415926 * 2.0 + phs[i];
                float sin_value = sin(x_pos);
                dr = {sin_txt};
                res += fv*v*dr;
            }}
            return res;
        """.replace(" "*12, " "*4)
        self = SynthesizerTool(name, code)
        return self


class SynthesizerProject:
    def __init__(self, api_function):
        self.x = Generator(api_function)
        self.w, self.ht, self.hl, self.log_w = 0, 0, 0, 0
        self.d = jsd()
        self.configs = jsd()
        self.tacts: [SynthesizerProjectTact] = []

    def draw(self):
        sc.clear()
        self.tacts.sort(key=lambda x: x.time or -1)
        if self.d.music.playing:
            self.d.music.draw_time = (pygame.time.get_ticks() - self.d.music.time_start) / 1000.0
        else:
            self.d.music.draw_time = math.inf
        self.draw_tacts()

    def log(self, s, color):
        s = [s]
        while len(s[-1]) > self.log_w:
            s.append(s[-1][self.log_w:])
            s[-2] = s[-2][:self.log_w]
        for line in s:
            self.d.log.append((line, color))
        while len(self.d.log) > self.hl - 1:
            self.d.log.pop(0)

    def get_input(self, validate, required=False, info_string="", start_string=""):
        s = start_string
        waiting = True
        sc.hline(self.h // 2 - 1, 0, '-', self.w)
        if required:
            st = f"{info_string} [required]"
            addstr(self.h // 2 - 1, self.w // 2 - len(st) // 2, st, c.path.unfocus)
        else:
            st = f"{info_string}"
            addstr(self.h // 2 - 1, self.w // 2 - len(st) // 2, st, c.path.unfocus)
        sc.hline(self.h // 2, 0, ' ', self.w)
        sc.hline(self.h // 2 + 1, 0, '-', self.w)
        while waiting:
            # draw state
            sc.hline(self.h // 2, 0, ' ', self.w)
            no_error = True
            try:
                res = validate(s)
            except Exception as e:
                no_error = False
                res = str(e)
            res = f"{s} -> {res}"[:self.w]
            addstr(self.h // 2, self.w // 2 - len(res) // 2, res, c.base)
            sc.chgat(self.h // 2, self.w // 2 - len(res) // 2 + min(len(s), self.w) - 1, 1, curses.color_pair(c.path.unfocus))
            sc.refresh()
            # read key press
            while True:
                key = sc.getch()
                if key == -1:
                    break
                elif key == curses.KEY_RESIZE:
                    curses.resize_term(*sc.getmaxyx())
                    sc.clear()
                    sc.refresh()
                elif key == 27:
                    if not required:
                        return None
                elif key == 8:  # backspace
                    s = s[:-1]
                elif key == 10:  # confirm
                    if no_error:
                        waiting = False
                        break
                elif chr(key) in string.printable:
                    s += chr(key)
        try:
            return validate(s)
        except Exception as e:
            return None

    def redo(self):
        if self.d.redo.arr:
            self.d.visual.selection, self.tacts = self.d.redo.arr[-1]
            self.d.visual.selection = jsd(self.d.visual.selection)
            self.d.redo.arr.pop(len(self.d.redo.arr)-1)

    def save_action(self):
        self.d.redo.arr.append((
            copy.deepcopy(self.d.visual.selection),
            copy.deepcopy(self.tacts)
        ))
        while len(self.d.redo.arr) > self.d.redo.length:
            self.d.redo.arr.pop(0)

    def save(self, filename):
        self.d.last_save_file = filename
        d = {
            "tools": [],
            "tacts": [],
            "configs": copy.deepcopy(self.configs)
        }
        # save configs
        d["configs"]["kernel"]["tools"] = None # tools save not here
        # save tools
        for tool in self.configs.kernel.tools:
            d["tools"].append(tool.to_string())
        # save tacts
        for tact in self.tacts:
            d["tacts"].append(tact.to_string())
        with open("tmp/save", "w") as file:
            json.dump(d, file)
        with open("tmp/save", mode="rb") as fin, bz2.open(filename, "wb", compresslevel=9) as fout:
            fout.write(fin.read())

    def load(self, filename):
        with bz2.open(filename, "rb") as fout:
            d = json.load(fout)
        # load configs
        self.configs = jsd_recurse(d["configs"])
        # load tools
        self.configs.kernel.tools = []
        for tool_string in d["tools"]:
            self.configs.kernel.tools.append(SynthesizerTool.from_string(tool_string))
        # load tacts
        self.tacts = []
        for tact_string in d["tacts"]:
            self.tacts.append(SynthesizerProjectTact.from_string(tact_string, len(self.configs.kernel.tools)))
        self.init_d()
        self.d.last_save_file = filename

    def export(self, filename):
        raw = self.compile(0.0)
        audio_bytes = raw.tobytes()
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(2)  # Stereo
            wav_file.setsampwidth(2)  # Sample width in bytes
            wav_file.setframerate(44100)  # Sample rate
            wav_file.writeframes(audio_bytes)
        # log end
        size = os.path.getsize(filename)
        self.log(f"Exported. Result file size: {size/1024**2:.1f} MB.", c.log.info)
        return

    def draw_tacts(self):
        line_height = 5+len(self.configs.kernel.tools)
        line_width_shift = 5
        line_width = self.w - 6

        mus_y = math.inf
        sel_y = math.inf
        x, y = 0, -self.d.visual.cy
        for tact_id, i in enumerate(self.tacts):
            # draw tact meta:
            if i.meta:
                s = ""
                if "tone_pitch" in i.meta:
                    ss = ";".join(map(lambda x: f'{x[0]}->{x[1]}', i.meta.tone_pitch.items()))
                    s += f"tone_pitch={ss}"
                px, py = x, y
                cpx = 0
                while s.strip() and cpx < 50:
                    ss = s[:self.w - px - 1 - line_width_shift]
                    s = s[self.w - px - 1 - line_width_shift:]
                    addstr(py, px + line_width_shift, ss, c.log.info)
                    py += line_height
                    px = 0
                    cpx += 1
            px, py = x, y
            for note_column, notes in enumerate(zip(*i.notes)):
                l = max(map(lambda i: 0 if i is None else len(i.text) - (1 if i.text and i.text[0] == '-' else 0), notes)) + 2
                if x + l >= line_width:
                    y += line_height
                    x = 0
                for pos, note in enumerate(notes):
                    is_playing = False
                    if note is not None and note.meta is not None:
                        is_playing = self.d.music.draw_time > note.meta.time and (self.d.music.draw_time - note.meta.time) < note.meta.length
                    if y + pos < self.ht:
                        color = c.gen.note.base
                        if is_playing:
                            color = c.gen.note.playing
                        elif self.d.visual.selection.pos is not None:
                            a, b = self.d.visual.selection.pos, self.d.visual.selection.end_pos
                            if b is None:
                                b = a
                            if min(a, b) <= tact_id <= max(a, b):
                                if note_column == self.d.visual.selection.column and pos == self.d.visual.selection.tool:
                                    color = c.gen.note.selected
                                elif self.d.visual.selection.column is None or self.d.visual.selection.column is None:
                                    color = c.gen.note.selected
                                else:
                                    color = c.log.info
                        if note is not None:
                            sh = (0 if note.text and note.text[0] == '-' else 1)
                            s = f"{note.text:{l}}"
                        else:
                            sh = 1
                            s = " " * l
                        addstr(y+pos+1, x + line_width_shift + sh, s, color)
                # next notes
                x += l

            # collect meta information
            min_y, max_y = math.inf, -math.inf
            for notes in zip(*i.notes):
                l = max(map(lambda i: 0 if i is None else len(i.text) - (1 if i.text and i.text[0] == '-' else 0), notes)) + 2
                while px > self.w:
                    py += line_height
                    px -= self.w
                min_y = min(min_y, py+self.d.visual.cy)
                max_y = max(max_y, py+self.d.visual.cy)
                for pos, note in enumerate(notes):
                    if note is not None and note.meta is not None:
                        if self.d.music.draw_time > note.meta.time and (self.d.music.draw_time - note.meta.time) < note.meta.length:
                            mus_y = min(mus_y, py+self.d.visual.cy)
            if tact_id == self.d.visual.selection.pos:
                sel_y = (min_y + max_y) // 2

            # end line to not break next tact
            x += 10
            if x > line_width:
                y += line_height
                x = 0
            if line_width - x < line_width // 3:
                y += line_height
                x = 0

        if self.d.visual.follow_music and mus_y != math.inf:
            if self.d.visual.cy < mus_y - self.ht * 2 // 3:
                self.d.visual.cy = mus_y - self.ht // 3
            if self.d.visual.cy > mus_y - self.ht * 1 // 9:
                self.d.visual.cy = mus_y - self.ht // 3

        if self.d.mode == "view":
            if not self.d.visual.follow_music:
                if pygame.time.get_ticks() - self.d.visual.last_action_time > 5500:
                    self.d.visual.follow_music = True
                if self.d.visual.selection.recalculate_cy and self.d.visual.selection.pos is not None and sel_y != math.inf:
                    self.d.visual.selection.recalculate_cy = False
                    if self.d.visual.cy < sel_y - self.ht * 2 // 3:
                        self.d.visual.cy = sel_y - self.ht // 3
                    if self.d.visual.cy > sel_y - self.ht * 1 // 9:
                        self.d.visual.cy = sel_y - self.ht // 3
        elif self.d.mode == "insert":
            if self.d.visual.selection.recalculate_cy and sel_y != math.inf:
                self.d.visual.selection.recalculate_cy = False
                if self.d.visual.cy < sel_y - self.ht * 2 // 3:
                    self.d.visual.cy = sel_y - self.ht // 3
                if self.d.visual.cy > sel_y - self.ht * 1 // 9:
                    self.d.visual.cy = sel_y - self.ht // 3

        # draw line
        sc.hline(self.ht, 0, '-', self.w)
        # draw low log panel
        for pos, _ in enumerate(self.d.log, 1):
            line, color = _
            addstr(self.ht + pos, 1, line[:self.log_w], color)
        # draw low info panel
        sc.vline(self.ht+1, self.log_w, '|', self.hl-1)

        addstr(self.ht+1, self.log_w + 2, f'mode: {self.d.mode}', c.base)

        addstr(self.ht+3, self.log_w + 2, f'temp size: {self.configs.tact_size}/{self.configs.tact_split}', c.base)
        temp_string = name_by_temp_bps(self.configs.bps)
        avr_time = len(self.tacts) * self.configs.tact_size * 60.0 / self.configs.bps
        addstr(self.ht+4, self.log_w + 2, f'temp: {self.configs.bps} kicks/minute (={temp_string})', c.base)
        addstr(self.ht+5, self.log_w + 2, f'tacts: {len(self.tacts)} (~{avr_time:.1f} seconds)', c.base)

    def events(self):
        while True:
            key = sc.getch()
            if key == -1:
                return True
            elif key == curses.KEY_RESIZE:
                curses.resize_term(*sc.getmaxyx())
                sc.clear()
                sc.refresh()
            elif key == 27:
                return False
            elif key == ord(curses.ascii.ctrl('s')):
                def path_string_save(x):
                    if not os.path.exists(os.path.dirname(x)):
                        raise Exception(f"Path <{os.path.dirname(x)}> not exists")
                    return os.path.normpath(x)
                s = "" if self.d.last_save_file is None else self.d.last_save_file
                filename = self.get_input(path_string_save, info_string="enter file to save", start_string=s)
                if filename is not None:
                    self.save(filename)
            elif key == ord(curses.ascii.ctrl('l')):
                def path_string_load(x):
                    if not os.path.exists(x):
                        raise Exception(f"Path <{x}> not exists")
                    return os.path.normpath(x)
                s = "" if self.d.last_save_file is None else self.d.last_save_file
                filename = self.get_input(path_string_load, info_string="enter file to load", start_string=s)
                if filename is not None:
                    self.load(filename)
            elif key == ord(curses.ascii.ctrl('e')): # export
                def path_string_export(x):
                    if not os.path.exists(os.path.dirname(x)):
                        raise Exception(f"Path <{os.path.dirname(x)}> not exists")
                    s = os.path.normpath(x)
                    if not s.endswith('.wav'):
                        s += ".wav"
                    return s
                filename = self.get_input(path_string_export, info_string="enter file to save [in wav format]")
                if filename is not None:
                    self.export(filename)
            # elif key == ord(curses.ascii.ctrl('g')): # export to glsl
            #     def path_string_export(x):
            #         if not os.path.exists(os.path.dirname(x)):
            #             raise Exception(f"Path <{os.path.dirname(x)}> not exists")
            #         s = os.path.normpath(x)
            #         if not s.endswith('.glsl'):
            #             s += ".glsl"
            #         return s
            #     filename = self.get_input(path_string_export, info_string="enter file to save [in glsl format]")
            #     if filename is not None:
            #         self.export_to_glsl(filename)
            elif self.d.mode == 'view':
                self.events_view(key)
            elif self.d.mode == 'insert':
                self.events_insert(key)

    def events_view(self, key):
        self.d.visual.selection.end_pos = None
        if key == curses.KEY_UP:
            self.d.visual.follow_music = False
            self.d.visual.last_action_time = pygame.time.get_ticks()
            self.d.visual.cy -= 1
        elif key == curses.KEY_DOWN:
            self.d.visual.follow_music = False
            self.d.visual.last_action_time = pygame.time.get_ticks()
            self.d.visual.cy += 1
        elif key == curses.KEY_RIGHT:
            self.d.visual.follow_music = False
            self.d.visual.last_action_time = pygame.time.get_ticks()
            self.d.visual.selection.recalculate_cy = True
            self.d.visual.selection.column = None
            self.d.visual.selection.tool = None
            if self.d.visual.selection.pos is None:
                self.d.visual.selection.pos = 0
            else:
                self.d.visual.selection.pos = min(self.d.visual.selection.pos + 1, len(self.tacts) - 1)
        elif key == curses.KEY_LEFT:
            self.d.visual.follow_music = False
            self.d.visual.last_action_time = pygame.time.get_ticks()
            self.d.visual.selection.recalculate_cy = True
            self.d.visual.selection.column = None
            self.d.visual.selection.tool = None
            if self.d.visual.selection.pos is None:
                self.d.visual.selection.pos = 0
            else:
                self.d.visual.selection.pos = max(self.d.visual.selection.pos - 1, 0)
        elif key in (ord('i'), ord('I')):
            self.d.mode = "insert"
            if self.d.visual.selection.pos is not None:
                self.d.visual.selection.column = 0
                self.d.visual.selection.tool = 0
        elif key in (ord('c'), ord('C')):
            self.compile(0.0)
        elif key in (ord('p'), ord('P')):
            self.d.music.playing = not self.d.music.playing
            if self.d.music.playing:
                if self.d.music.track is None:
                    self.log("Trak is not compiled yet [press 'c' to compile]", c.log.info)
                    self.d.music.playing = False
                else:
                    self.d.music.time_start = pygame.time.get_ticks()
                    self.d.music.track.play()
            else:
                self.d.music.track.stop()
        elif key in (ord('g'), ord("G")): # gamma
            # update_tone_pitch
            def gamma_string(s):
                if not s.strip():
                    return {}
                a = s.split(';')
                b = list(map(lambda x: x.split("->"), a))
                c = dict(b)
                return c
            s = ";".join(map(lambda x: x[0] + "->" + x[1], self.configs.tone_pitch.items()))
            p = self.get_input(gamma_string, info_string="Enter new gamma: (in format 'A->A#;C->C#;G->F#', using only C C# D D# E F F# G G# A A# B)", start_string=s)
            if p is not None:
                self.configs.tone_pitch = p
        elif key in (ord('r'), ord("R")): # rythm
            # update_tone_pitch
            def get_rythm(s):
                a = s.split('/')
                a = tuple(map(int, a))
                if len(a) != 2 or min(a) < 1:
                    raise Exception("Error: too many '/' or one of values is zero, or less than zero")
                return a
            tact_size = self.configs.tact_size
            tact_split = self.configs.tact_split
            p = self.get_input(get_rythm, info_string="Enter new rythm (tact size) in format A/B (like 3/4 or 4/4)", start_string=f"{tact_split}/{tact_size}")
            if p is not None:
                self.configs.tact_size = p[0]
                self.configs.tact_split = p[1]
        elif key in (ord('v'), ord("V")): # speed [velocity] of music
            p = self.get_input(int, info_string="Enter new temp: (beats per second, integer)", start_string=str(self.configs.bps))
            if p is not None:
                self.configs.bps = p
        elif key in (ord('t'), ord('T')):
            self.tool_panel()

    def events_insert(self, key):
        if key == curses.KEY_RIGHT:
            self.d.visual.selection.recalculate_cy = True
            self.d.visual.selection.end_pos = None
            if self.d.visual.selection.pos is None:
                self.d.visual.selection.pos = 0
            if self.d.visual.selection.column is None:
                self.d.visual.selection.column = 0
            if self.d.visual.selection.tool is None:
                self.d.visual.selection.tool = 0

            self.d.visual.selection.column += 1
            if self.d.visual.selection.column >= self.tacts[self.d.visual.selection.pos].length:
                if self.d.visual.selection.pos + 1 < len(self.tacts):
                    self.d.visual.selection.pos += 1
                    self.d.visual.selection.column = 0
                else:
                    self.d.visual.selection.column -= 1 # restore
        elif key == curses.KEY_LEFT:
            self.d.visual.selection.recalculate_cy = True
            self.d.visual.selection.end_pos = None
            if self.d.visual.selection.pos is None:
                self.d.visual.selection.pos = 0
            if self.d.visual.selection.column is None:
                self.d.visual.selection.column = 0
            if self.d.visual.selection.tool is None:
                self.d.visual.selection.tool = 0

            self.d.visual.selection.column -= 1
            if self.d.visual.selection.column < 0:
                if self.d.visual.selection.pos - 1 >= 0:
                    self.d.visual.selection.pos -= 1
                    self.d.visual.selection.column = self.tacts[self.d.visual.selection.pos].length - 1
                else:
                    self.d.visual.selection.column += 1 # restore
        elif key == 400: # right + shift
            if self.d.visual.selection.pos is not None:
                self.d.visual.selection.recalculate_cy = True
                if self.d.visual.selection.end_pos is None:
                    self.d.visual.selection.end_pos = self.d.visual.selection.pos
                self.d.visual.selection.end_pos = min(self.d.visual.selection.end_pos + 1, len(self.tacts)-1)
                self.d.visual.selection.column = None
                self.d.visual.selection.tool = None
        elif key == 391: # left + shift
            if self.d.visual.selection.pos is not None:
                self.d.visual.selection.recalculate_cy = True
                if self.d.visual.selection.end_pos is None:
                    self.d.visual.selection.end_pos = self.d.visual.selection.pos
                self.d.visual.selection.end_pos = max(self.d.visual.selection.end_pos-1, 0)
                self.d.visual.selection.column = None
                self.d.visual.selection.tool = None
        elif key == 444: # right + ctrl
            if self.d.visual.selection.pos is not None:
                self.d.visual.selection.recalculate_cy = True
                self.save_action()
                if self.d.visual.selection.end_pos is None:
                    self.d.visual.selection.end_pos = self.d.visual.selection.pos
                self.d.visual.selection.column = None
                self.d.visual.selection.tool = None
                a, b = self.d.visual.selection.pos, self.d.visual.selection.end_pos
                a, b = min(a, b), max(a, b)
                if b + 1 < len(self.tacts):
                    self.tacts.insert(a, self.tacts.pop(b + 1))
                    self.d.visual.selection.pos += 1
                    self.d.visual.selection.end_pos += 1
        elif key == 443: # left + ctrl
            if self.d.visual.selection.pos is not None:
                self.d.visual.selection.recalculate_cy = True
                self.save_action()
                if self.d.visual.selection.end_pos is None:
                    self.d.visual.selection.end_pos = self.d.visual.selection.pos
                self.d.visual.selection.column = None
                self.d.visual.selection.tool = None
                a, b = self.d.visual.selection.pos, self.d.visual.selection.end_pos
                a, b = min(a, b), max(a, b)
                if a - 1 >= 0:
                    self.tacts.insert(b, self.tacts.pop(a - 1))  # b  not  b + 1 becoude a < b
                    self.d.visual.selection.pos -= 1
                    self.d.visual.selection.end_pos -= 1
        elif key == curses.KEY_UP:
            self.d.visual.selection.recalculate_cy = True
            self.d.visual.selection.end_pos = None
            if self.d.visual.selection.pos is None:
                self.d.visual.selection.pos = 0
            if self.d.visual.selection.column is None:
                self.d.visual.selection.column = 0
            if self.d.visual.selection.tool is None:
                self.d.visual.selection.tool = 0
            self.d.visual.selection.tool -= 1
            if self.d.visual.selection.tool < 0:
                self.d.visual.selection.tool = 0
        elif key == curses.KEY_DOWN:
            self.d.visual.selection.recalculate_cy = True
            self.d.visual.selection.end_pos = None
            if self.d.visual.selection.pos is None:
                self.d.visual.selection.pos = 0
            if self.d.visual.selection.column is None:
                self.d.visual.selection.column = 0
            if self.d.visual.selection.tool is None:
                self.d.visual.selection.tool = 0
            self.d.visual.selection.tool += 1
            if self.d.visual.selection.tool >= len(self.configs.kernel.tools):
                self.d.visual.selection.tool = len(self.configs.kernel.tools) - 1
        elif key in (ord('`'), ord('`')):
            self.d.mode = "view"
        elif key == 8:  # backspace
            if (self.d.visual.selection.pos is not None
                        and self.d.visual.selection.column is not None
                        and self.d.visual.selection.tool is not None):
                self.d.visual.selection.recalculate_cy = True
                if self.tacts[self.d.visual.selection.pos].notes[self.d.visual.selection.tool][self.d.visual.selection.column] is not None:
                    s = self.tacts[self.d.visual.selection.pos].notes[self.d.visual.selection.tool][self.d.visual.selection.column].text
                    self.tacts[self.d.visual.selection.pos].notes[self.d.visual.selection.tool][self.d.visual.selection.column].text = s[:-1]
                    if not self.tacts[self.d.visual.selection.pos].notes[self.d.visual.selection.tool][self.d.visual.selection.column].text.strip():
                        self.tacts[self.d.visual.selection.pos].notes[self.d.visual.selection.tool][self.d.visual.selection.column] = None
        elif key == 127:  # ctrl+backspace: remove all text
            if (self.d.visual.selection.pos is not None
                        and self.d.visual.selection.column is not None
                        and self.d.visual.selection.tool is not None):
                self.d.visual.selection.recalculate_cy = True
                self.tacts[self.d.visual.selection.pos].notes[self.d.visual.selection.tool][self.d.visual.selection.column] = None
        elif key == 10:  # return key
            if (self.d.visual.selection.pos is not None
                        and self.d.visual.selection.column is not None
                        and self.d.visual.selection.tool is not None):
                self.d.visual.selection.recalculate_cy = True
                s = ""
                if self.tacts[self.d.visual.selection.pos].notes[self.d.visual.selection.tool][self.d.visual.selection.column] is not None:
                    s = self.tacts[self.d.visual.selection.pos].notes[self.d.visual.selection.tool][self.d.visual.selection.column].text
                res = self.get_input(lambda x: x.strip(), False, "edit note", start_string=s)
                if res is not None:
                    if self.tacts[self.d.visual.selection.pos].notes[self.d.visual.selection.tool][self.d.visual.selection.column] is None:
                        self.tacts[self.d.visual.selection.pos].notes[self.d.visual.selection.tool][self.d.visual.selection.column] = SynthesizerProjectNote(res)
                    else:
                        self.tacts[self.d.visual.selection.pos].notes[self.d.visual.selection.tool][self.d.visual.selection.column].text = res
        elif key == ord('\t'): # tab: insert column, if in end, insert tact
            if (self.d.visual.selection.pos is not None
                        and self.d.visual.selection.column is not None
                        and self.d.visual.selection.tool is not None):
                self.d.visual.selection.recalculate_cy = True
                if self.d.visual.selection.column >= self.tacts[self.d.visual.selection.pos].length - 1: # new tact
                    self.tacts.insert(self.d.visual.selection.pos+1, SynthesizerProjectTact(0.0, len(self.configs.kernel.tools)))
                    self.d.visual.selection.pos += 1
                    self.d.visual.selection.column = 0
                else: # insert column
                    self.tacts[self.d.visual.selection.pos].insert_column(self.d.visual.selection.column)
        elif key == 330: # delete key: delete column
            if (self.d.visual.selection.pos is not None
                        and self.d.visual.selection.column is not None
                        and self.d.visual.selection.tool is not None):
                self.d.visual.selection.recalculate_cy = True
                self.save_action()
                if self.d.visual.selection.column > 0:
                    self.tacts[self.d.visual.selection.pos].delete_column(self.d.visual.selection.column)
                    self.d.visual.selection.column -= 1
                else:
                    if self.tacts[self.d.visual.selection.pos].length > 1:
                        self.tacts[self.d.visual.selection.pos].delete_column(self.d.visual.selection.column)
                    else:
                        self.tacts.pop(self.d.visual.selection.pos)
                        if not self.tacts:
                            self.tacts = [SynthesizerProjectTact(0.0, len(self.configs.kernel.tools))]
                        self.d.visual.selection.pos = max(self.d.visual.selection.pos - 1, 0)
                        self.d.visual.selection.column = self.tacts[self.d.visual.selection.pos].length-1
        elif key == ord(' '): # next cell, if not exists, create
            self.d.visual.selection.recalculate_cy = True
            if self.d.visual.selection.pos is None:
                self.d.visual.selection.pos = 0
            if self.d.visual.selection.column is None:
                self.d.visual.selection.column = 0
            if self.d.visual.selection.tool is None:
                self.d.visual.selection.tool = 0

            self.d.visual.selection.column += 1
            if self.d.visual.selection.column >= self.tacts[self.d.visual.selection.pos].length:
                self.save_action()
                self.tacts[self.d.visual.selection.pos].insert_column(self.tacts[self.d.visual.selection.pos].length)
        elif key == ord(curses.ascii.ctrl('d')): # dublicate tact
            if self.d.visual.selection.pos is not None:
                self.d.visual.selection.recalculate_cy = True
                self.save_action()
                a, b = self.d.visual.selection.pos, self.d.visual.selection.end_pos
                if b is None:
                    b = a
                for t in range(max(a, b), min(a, b)-1,-1):
                    self.tacts.insert(b+1, copy.deepcopy(self.tacts[t]))
        elif key == ord(curses.ascii.ctrl('z')):
            self.d.visual.selection.recalculate_cy = True
            self.redo()
        elif key == ord(curses.ascii.ctrl('g')): # edit meta
            def meta_note(x):
                x = x.split(' ', 1)
                if x[0] == 'del':
                    s = x[1].strip()
                    if s not in self.tacts[self.d.visual.selection.pos].meta.keys():
                        raise Exception(f"Error: this tact doesn't have <{s}>")
                    return x[0], x[1].strip()
                elif x[0] == 'tone_pitch':
                    if not x[1].strip():
                        return x[0], {}
                    try:
                        a = x[1].split(';')
                        b = list(map(lambda y: y.split("->"), a))
                        c = dict(b)
                    except Exception as e:
                        raise Exception("tone_pitch must be in format like 'A->A#;C->C#;G->F#' (str(e))")
                    return x[0], c
                else:
                    raise Exception(f"Meta type <{x[0]}> not exists.")
                return x
            meta = self.get_input(meta_note, info_string="Edit meta: aviable 'tone_pitch'. to delete info use del <meta_name>")
            if meta is not None:
                if meta[0] == "del":
                    self.tacts[self.d.visual.selection.pos].meta.pop(meta[1])
                else:
                    self.tacts[self.d.visual.selection.pos].meta[meta[0]] = meta[1]                
        elif key == ord(curses.ascii.ctrl('t')):
            self.d.visual.selection.recalculate_cy = True
            if self.d.music.playing:
                self.d.music.track.stop()
            compilation_time = self.d.visual.selection.pos * self.configs.tact_size * 60.0 / self.configs.bps
            compilation_time -= 8.0
            self.d.music.track = None
            self.compile(compilation_time)
            self.d.music.playing = True
            if self.d.music.track is None: # strange position...
                self.log("Trak is not compiled yet [press 'c' in view mode to compile]", c.log.info)
                self.d.music.playing = False
            else:
                self.d.music.time_start = pygame.time.get_ticks() - 1000 * compilation_time
                self.d.music.track.play()
        elif chr(key) in string.printable:
            if (self.d.visual.selection.pos is not None
                        and self.d.visual.selection.column is not None
                        and self.d.visual.selection.tool is not None):
                self.d.visual.selection.recalculate_cy = True
                if self.tacts[self.d.visual.selection.pos].notes[self.d.visual.selection.tool][self.d.visual.selection.column] is None:
                    self.save_action()
                    self.tacts[self.d.visual.selection.pos].notes[self.d.visual.selection.tool][self.d.visual.selection.column] = SynthesizerProjectNote(chr(key))
                else:
                    self.save_action()
                    self.tacts[self.d.visual.selection.pos].notes[self.d.visual.selection.tool][self.d.visual.selection.column].text += chr(key)

    def tool_panel(self):
        # LONG FUNCTION :)
        v = jsd(
            selection=jsd(
                tool=0,
                column=1
            )
        )
        def moditify_code(x):
            #file = tempfile.NamedTemporaryFile(mode='w+t', delete=False)
            file = open("./tmp/tmp.c", "w")
            filename = file.name
            note = """struct __attribute__ ((packed)) note
            {
                int tool;
                int start;
                int end;
                float frequency;
                float volume;
            };""".replace("            ", "")
            file.write(f"{note}\n\nfloat {x.name}(float s, struct note *note, float rnd)\n{{{x.code}}}")
            file.close()
            if os.name == "posix":
                subprocess.run(['$EDITOR', filename], shell=True)
            else:
                err = subprocess.run("micro -version", shell=True).returncode
                if err == 0: # found 'micro' (text editor) [only for my usage in windows]
                    curses.endwin()
                    subprocess.run(['powershell', '-c',f'Start-Process micro {filename} -Wait -NoNewWindow'], shell=True)
                    sc.refresh()
                else:
                    subprocess.run([f'powershell', '-c', 'Notepad.exe', filename, " | Out-Null"], shell=True)
            try:
                with open(filename) as file:
                    code = file.read()
            except FileNotFoundError:
                return None
            # restore code?
            fn_pos = code.find(x.name)
            pos1 = code.find('{', fn_pos)
            pos2 = code.rfind('}')
            code = code[pos1+1:pos2]
            x.code = code
            os.remove(filename)
        def save_tool(x):
            # request for filename
            def path_string(x):
                if not os.path.exists(os.path.dirname(x)):
                    raise Exception(f"Path <{os.path.dirname(x)}> not exists")
                return x
            p = self.get_input(path_string, info_string="Enter path to file (for export into)")
            if p is None:
                return
            # to save
            s = x.to_string()
            with open(p, "w") as file:
                file.write(s)
        def rename_tool(x):
            s = self.get_input(name_request_string, info_string="Enter name of tool, another tool's name to copy, <del> to delete")
            if s is None:
                return None
            if s.startswith("new name:"):
                name = s[s.find(':')+1:].strip()
                x.name = name
            elif s.startswith("copy this tool to:"):
                name = s[s.find(':')+1:].strip()
                try:
                    idx = list(map(lambda x: x.name, self.configs.kernel.tools)).index(name)
                except Exception as e:
                    return None
                self.configs.kernel.tools[idx] = x.copy()
                self.configs.kernel.tools[idx].name = name
            elif s == "WARNING: Delete this tool":
                name = x.name
                try:
                    idx = list(map(lambda x: x.name, self.configs.kernel.tools)).index(name)
                    self.configs.kernel.tools.pop(idx)
                    for t in self.tacts:
                        for i in range(len(t.notes)-1,-1,-1):
                            if t.notes[i].tool == idx:
                                t.notes.pop(i)
                except Exception as e:
                    ...
        def update_tacts_after_new_tool():
            for t in self.tacts:
                t.notes.append([None] * t.length)
        def swap_tools(tid1, tid2):
            self.configs.kernel.tools[tid1], self.configs.kernel.tools[tid2] = self.configs.kernel.tools[tid2], self.configs.kernel.tools[tid1]
            for t in self.tacts:
                t.notes[tid2], t.notes[tid1] = t.notes[tid1], t.notes[tid2]
        def name_request_string(x):
            x = x.strip().replace(" ", "_")
            if not x.strip():
                raise Exception("Enter not empty string (left and right spaces will be cut)")
            if x == "del":
                return "WARNING: Delete this tool"
            if x in list(map(lambda x: x.name, self.configs.kernel.tools)):
                return f"copy this tool to: {x}"
            return f"new name: {x}"
        def new_name_string(x):
            x = x.strip().replace(" ", "_")
            if not x.strip():
                raise Exception("Enter not empty string (left and right spaces will be cut)")
            if x in list(map(lambda x: x.name, self.configs.kernel.tools)):
                raise Exception(f"This name is smilar to existing ({x})")
            return x
        def in_float_01(x):
            x = float(x)
            if x < 0 or x > 1.0:
                raise Exception("volume must be from 0.0 to 1.0")
            return x
        def in_float_positive(x):
            x = float(x)
            if x <= 0.0:
                raise Exception("Legato mode must be more than 0")
            return x
        rows = {
            "name": lambda x: x.name,
            "code": lambda x: "<edit>",
            "mute": lambda x: x.configs.mute,
            "volume": lambda x: x.configs.volume,
            "legato_mod": lambda x: x.configs.legato_mod,
            "use stereo": lambda x: x.configs.stereo,
            "export": lambda x: "<export>",
        }
        rows_keys = list(rows.keys())
        rows_edit = {
            "name": lambda x: rename_tool(x),
            "code": lambda x: moditify_code(x),
            "mute": lambda x: setattr(x.configs, 'mute', not x.configs.mute),
            "volume": lambda x: setattr(x.configs, "volume", f) if (f := self.get_input(in_float_01, info_string="Enter volume of tool")) is not None else None,
            "legato_mod": lambda x: setattr(x.configs, "legato_mod", f) if (f := self.get_input(in_float_positive, info_string="Enter legato mod of tool")) is not None else None,
            "use stereo": lambda x: setattr(x.configs, 'stereo', not x.configs.stereo),
            "export": lambda x: save_tool(x),
        }
        def new_tool():
            # select - Load or new
            sel = 0
            s = ["create new tool", "load from file", "create from wave file"]
            waiting = True
            sc.hline(self.h // 2 - 1, 0, '-', self.w)
            st = f"select how to create new tool:"
            addstr(self.h // 2 - 1, self.w // 2 - len(st) // 2, st, c.path.unfocus)
            sc.hline(self.h // 2, 0, ' ', self.w)
            sc.hline(self.h // 2 + 1, 0, '-', self.w)
            while waiting:
                # draw state
                sc.hline(self.h // 2, 0, ' ', self.w)
                res = -(sum(map(len, s)) + 3 * len(s)) // 2
                for cnt, i in enumerate(s):
                    addstr(self.h // 2, self.w // 2 + res, i, c.path.unfocus if sel == cnt else c.base)
                    res += len(i)
                    if cnt != len(s) - 1:
                        addstr(self.h // 2, self.w // 2 + res, " | ", c.base)
                        res += 3
                sc.refresh()
                # read key press
                while True:
                    key = sc.getch()
                    if key == -1:
                        break
                    elif key == curses.KEY_RESIZE:
                        curses.resize_term(*sc.getmaxyx())
                        sc.clear()
                        sc.refresh()
                    elif key == 27:
                        return
                    elif key == 10: # confirm
                        waiting = False
                        break
                    elif key == curses.KEY_RIGHT:
                        sel = min(sel+1, len(s)-1)
                    elif key == curses.KEY_LEFT:
                        sel = max(sel-1, 0)
            if sel == 0:
                base_of_code = """
                    float dr;
                    float v = note->volume;
                    float k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
                    v *= fmax(0.01f, k);
                    dr = sin(s * note->frequency / 44100.0f * 3.1415926);
                    return v*dr;
                """.replace("            ", "")
                name = self.get_input(new_name_string, required=False, info_string="Enter name of tool")
                if name is None:
                    return
                code = f"\n    /*Enter code here to generate sample 's' from note 'note' (rnd is white noise from -1 to 1)*/{base_of_code}"
                t = SynthesizerTool(name, code)
                self.configs.kernel.tools.append(t)
                update_tacts_after_new_tool()
            elif sel == 1:
                def path_string(x):
                    if not os.path.exists(x):
                        raise Exception(f"Path <{x}> not exists")
                    return x
                filename = self.get_input(path_string, info_string="Enter path to file (to load from)")
                if filename is None:
                    return
                try:
                    with open(filename, "r") as file:
                        s = file.read()
                    t = SynthesizerTool.from_string(s)
                    self.configs.kernel.tools.append(t)
                    update_tacts_after_new_tool()
                except Exception as e:
                    self.log(str(e),c.base)
                    return
            elif sel == 2:
                def path_string(x):
                    if not os.path.exists(x):
                        raise Exception(f"Path <{x}> not exists")
                    return x
                name = self.get_input(new_name_string, info_string="Enter name of tool")
                if name is None:
                    return
                filename = self.get_input(path_string, info_string="Enter path to music (mp3/wav/ogg/etc) file (to create from)")
                if filename is None:
                    return
                try:
                    t = SynthesizerTool.from_wave(lambda x: self.log(x, c.log.info), name, filename)
                    self.configs.kernel.tools.append(t)
                    update_tacts_after_new_tool()
                except Exception as e:
                    self.log(str(e),c.base)
                    return
        def draw():
            nonlocal v, rows
            # draw tools table
            sc.clear()
            table = [list(rows.keys())]
            for t in self.configs.kernel.tools:
                table.append([])
                for fn in rows.values():
                    table[-1].append(str(fn(t)))
            # draw table
            width = list(map(lambda x: max(len(s[x]) for s in table), range(len(rows))))
            width_sum = sum(width)
            width = list(map(lambda x: (x * self.w) // width_sum, width))
            for y, r in enumerate(table):
                x = 0
                for row in range(len(rows)):
                    color = c.base
                    if v.selection.tool == y - 1 and v.selection.column == row:
                        color = c.path.unfocus
                    w = width[row]
                    s = f"{r[row]:{w-1}}|"[:w]
                    addstr(y, x, s, color)
                    x += width[row]
                    addstr(y, x-1, "|", c.base)
            s = "-"*self.w
            y = len(self.configs.kernel.tools)
            color = (c.base if v.selection.tool != y else c.path.unfocus)
            addstr(y + 1, 0, s, color)
            addstr(y + 1, self.w // 2 - len("new-tool"), "new-tool", color)

        while True:
            self.resize()
            draw()
            while True:
                key = sc.getch()
                if key == -1:
                    break
                elif key == curses.KEY_RESIZE:
                    curses.resize_term(*sc.getmaxyx())
                    sc.clear()
                    sc.refresh()
                elif key == 27:
                    return
                elif key in (ord('t'), ord('T')):
                    return
                elif key == 10:  # confirm
                    if v.selection.tool == len(self.configs.kernel.tools):
                        new_tool()
                    else:
                        rows_edit[rows_keys[v.selection.column]](self.configs.kernel.tools[v.selection.tool])
                elif key == curses.KEY_LEFT:
                    v.selection.column -= 1
                    v.selection.column = max(v.selection.column, 0)
                elif key == curses.KEY_RIGHT:
                    v.selection.column += 1
                    v.selection.column = min(v.selection.column, len(rows)-1)
                elif key == curses.KEY_UP:
                    v.selection.tool -= 1
                    v.selection.tool = max(v.selection.tool, 0)
                elif key == curses.KEY_DOWN:
                    v.selection.tool += 1
                    # no -1 for 'new tool button'
                    v.selection.tool = min(v.selection.tool, len(self.configs.kernel.tools))
                elif key in (ord('w'), ord('W')):
                    if v.selection.tool != 0 and v.selection.tool != len(self.configs.kernel.tools):
                        swap_tools(v.selection.tool - 1, v.selection.tool)
                        v.selection.tool -= 1
                elif key in (ord('s'), ord('S')):
                    if v.selection.tool < len(self.configs.kernel.tools) - 1:
                        swap_tools(v.selection.tool, v.selection.tool + 1)
                        v.selection.tool += 1

    def generate_generator_tones(self):
        # load configuration parameters
        tone_pitch = self.configs.tone_pitch
        tact_size = self.configs.tact_size
        tact_split = self.configs.tact_split
        tempo_multipler = 60.0 / tact_split / self.configs.bps

        r = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        # start time
        t = 0.0
        # remove empty notes
        for i in self.tacts:
            for n in i.notes:
                for ii in range(len(n)):
                    if n[ii] is not None and not n[ii].text.strip():
                        n[ii] = None
        # for all notes:
        vapp = [1.0] * len(self.configs.kernel.tools)
        for tact_id, tact in enumerate(self.tacts):
            try:
                # read META
                if "tone_pitch" in tact.meta.keys():
                    tone_pitch = tact.meta.tone_pitch
                # compile notes
                for tool, notes in enumerate(tact.notes):
                    if not self.configs.kernel.tools[tool].configs.mute:
                        # add all notes
                        prev_len, prev_volume = 1.0, 1.0
                        tt = t
                        for note in filter(lambda x: x is not None and x.text.strip(), notes):
                            # get instrument id [tool]
                            content = note.text
                            vv = vapp[tool]
                            vl = 1.0
                            if content[-1] == '+': # acsent + long
                                vv *= 1.5
                                vl *= 2.0
                                content = content[:-1] # acsent
                            elif content[-1] == '*':
                                vv *= 1.5
                                content = content[:-1]
                            elif content[-1] == 'v': # no acsent
                                vv *= 0.5
                                content = content[:-1]
                            if content[0] == '-':
                                tt -= prev_len
                                content = content[1:]
                            # parse content
                            a = content.split('/')
                            f, l, v = "A", prev_len, prev_volume
                            if len(a) >= 1:
                                f = a[0]
                            if len(a) >= 2 and a[1]:
                                l = eval(a[1].replace(":", "/"))
                            if len(a) >= 3 and a[2]:
                                tt = t + eval(a[2].replace(":", "/"))
                            if len(a) >= 4 and a[3]:
                                v = eval(a[3].replace(":", "/"))
                            # calculate frequency
                            k = 0
                            while k < len(f) and not f[k].isdigit():
                                k += 1
                            nt = f[:k]
                            if nt.startswith("@"): # becare (not make tone pitch)
                                nt = nt[1:]
                            else:
                                nt = tone_pitch.get(nt, nt)
                            nt = r.index(nt)
                            z = int(f[k:]) - 4
                            fq = 523.25 * pow(2, z + nt / 12)

                            volume_pitch = self.configs.kernel.tools[tool].configs.volume
                            legato_mod = self.configs.kernel.tools[tool].configs.legato_mod * vl
                            self.x.add(GeneratorTone(tool, tt * tempo_multipler, l * legato_mod * tempo_multipler, v * vv * volume_pitch, fq))
                            # add note's meta
                            note.meta = jsd(time = tt * tempo_multipler, length = l * tempo_multipler)
                            prev_len, prev_volume = l, v
                            tt += l
            except Exception as e:
                self.log(f"Error: {e}", c.log.error)
                self.d.visual.selection.pos = tact_id
                self.d.visual.selection.column = None
                self.d.visual.selection.tool = None
                self.d.visual.recalculate_cy = True
                return False
            t += tact_size * tact_split
        return True

    def compile(self, compilation_start_time=0.0):
        if self.d.music.track is not None:
            self.d.music.playing = False
            self.d.music.track.stop()
        used_time = -time.time()
        self.log("compilation start...", c.log.info)
        self.draw()
        sc.refresh()

        # generate tones

        self.x.inputs.clear()
        res = self.generate_generator_tones()
        if not res:
            self.log("compilation terminated.", c.log.error)
            return
        if not self.x.inputs:
            self.log("Error: Empty notes (or all tools are muted.) Nothing to compile", c.log.error)
            return
        # apply compilation_start_time
        if compilation_start_time > 0:
            self.x.adjust_start_time(compilation_start_time)
        # generate kernel code
        with open("source/kernel_template.cl") as file:
            code = file.read()
        # create kernel:
        function_code = ""
        switch_code = ""
        # generate code
        switch_code += ""
        for id, t in enumerate(self.configs.kernel.tools):
            switch_code += f"case {id}: res += {t.name}(s, notes + n, rnd); break;\n"
            function_code += f"float {t.name}(float s, struct note *note, float rnd){{ {t.code} }}\n\n"
        # insert before kernel all
        code = code.replace("<TOOLS_FUNCTION>", function_code)
        code = code.replace("<TOOLS_SWITCH>", switch_code)
        with open("source/kernel.cl", "w") as file:
            file.write(code)
        raw = self.x.compile(self.log)
        # export track
        raw = np.tanh(raw)
        raw *= 32767.0
        raw = raw.astype(dtype=np.int16)
        raw = np.column_stack((raw, raw))
        # export sound
        raw = raw.copy(order='C')
        self.d.music.track = pygame.sndarray.make_sound(raw)
        # log end
        used_time += time.time()
        self.log(f"compiled. Used time: {used_time:.3f} s, {raw.shape[0]/1e6:.1f}M samples.", c.log.info)
        return raw
    def export_to_glsl(self, filename):
        self.x.inputs.clear()
        res = self.generate_generator_tones()
        if not res:
            self.log("compilation terminated", c.log.error)
            return
        if not self.x.inputs:
            self.log("Error: Empty notes (or all tools are muted.) Nothing to compile", c.log.error)
            return
        if True:
            # parameters
            split_time = 1.0
            notes_on_split = 16
            # create array_code
            length = int(2 + max(map(lambda i: i.time + i.length, self.x.inputs)) / split_time)
            array_define = "#define T(" + ",".join(map(lambda x: f"a{x},b{x},c{x},d{x},e{x}", range(1, notes_on_split+1))) + ")"
            array_define += ",".join(map(lambda x: f"Xnote(a{x},b{x},c{x},d{x},e{x})", range(1, notes_on_split+1)))
            array_define += "\n#define Z 0."
            array_code = [array_define, f"Xnote array[{length*notes_on_split}] = Xnote[]("]
            # sort data
            self.x.inputs.sort(key=lambda x: x.time)
            logged_error = 0
            values = [[] for i in range(length)]
            f = lambda x: f"{int(x + 0.5)}.0" if '.' not in f"{x:.6g}" else f"{x:.6g}"
            # fill array
            for n in self.x.inputs:
                l = int(n.time / split_time)
                r = int(1 + (n.time + n.length) / split_time)
                for i in range(l, r + 1):
                    values[i].append(f"{n.tool},{f(n.time)},{f(n.time + n.length)},{f(n.frequency)},{f(n.volume)}")
            for i in range(length):
                if len(values[i]) > notes_on_split:
                    data = values[i][:notes_on_split]
                    if not logged_error:
                        self.log("Error: too many notes, to get full result increase notes_on_split value.")
                        logged_error = 1
                else:
                    data = values[i] + ['-1,Z,Z,Z,Z'] * (notes_on_split - len(values[i]))
                array_code.append(f"T({','.join(data)}),")
            array_code[-1] = array_code[-1].rstrip(',')
            array_code.append(");")
            array_code = "\n".join(array_code)
        # generate kernel code
        with open("source/shadertoy_export.glsl") as file:
            code = file.read()
        # create kernel:
        function_code = ""
        switch_code = ""
        # generate code
        switch_code += ""
        for id, t in enumerate(self.configs.kernel.tools):
            fc = t.code
            # apply some easy 'openCL kernel' to 'GLSL' rules
            fc = fc.replace("->", ".")
            # add function
            switch_code += f"case {id}: res += {t.name}(s * 44100.0, array[beat * notes_on_split + n], rnd); break;\n"
            function_code += f"float {t.name}(float s, in Xnote note, float rnd){{ {fc} }}\n\n"
        # insert before kernel all
        code = code.replace("<TOOLS_FUNCTION>", function_code)
        code = code.replace("<TOOLS_SWITCH>", switch_code)
        code = code.replace("<MAIN_ARRAY>", array_code)
        with open(filename, "w") as file:
            file.write(code)

    def resize(self):
        self.h, self.w = sc.getmaxyx()
        self.log_w = self.w // 2
        self.hl = min(15, max(7, self.w // 5))
        self.ht = self.h - self.hl

    def init_d(self):
        self.d = jsd(
            mode="view",
            log=[],
            last_save_file=None,
            music=jsd(
                track=None,
                draw_time=0.0,
                playing=False,
                time_start=0,
            ),
            visual=jsd(
                cy=0,
                follow_music=True,
                follow_music_time=0,
                last_action_time=0.0,
                selection=jsd(
                    pos=None,
                    column=None,
                    tool=None,
                    end_pos=None,
                    recalculate_cy=False,
                )
            ),
            redo=jsd(
                arr=[],
                length=100,
            )
        )

    def run(self):
        self.init_d()
        self.configs = jsd(
            tone_pitch={},
            tact_size=4,
            tact_split=4,
            bps=60,
            kernel=jsd(
                tools=[]
            ),
        )
        self.configs.kernel.tools.append(SynthesizerTool(name="PianoSolo", code="""
                float freq[] = {
                    1.0,
                    0.5,
                    0.2,
                    0.05,
                    0.1,
                    0.0025,
                    0.001
                };
                float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
                v *= fmax(0.01f, k);
                
                float res = 0.0, dr;
                for (int fqid = 0; fqid < sizeof(freq) / sizeof(*freq); ++fqid)
                {
                    float f = note->frequency * (fqid + 1);
                    float fv = freq[fqid];
                    dr = sin(s * f / 44100.0f * 0.5 * 3.1415926 * 2.0);
                    res += fv*v*dr;
                }
                return res;
        """.replace(" "*12,"")))
        self.configs.kernel.tools.append(SynthesizerTool(name="PianoBass", code="""
                float freq[] = {
                    0.5,
                    0.6,
                    0.05,
                    0.7,
                    0.05,
                    0.25,
                    0.15,
                    0.8,
                    0.015,
                    0.005,
                    0.015,
                    0.1,
                    0.015,
                    0.005,
                    0.015,
                    0.6,
                };
                float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
                v *= fmax(0.01f, k);
                
                float res = 0.0, dr;
                for (int fqid = 0; fqid < sizeof(freq) / sizeof(*freq); ++fqid)
                {
                    float f = note->frequency * (fqid + 1) * 0.125;
                    float fv = freq[fqid];
                    dr = sin(s * f / 44100.0f * 0.5 * 3.1415926 * 2.0);
                    res += fv*v*dr;
                }
                return res;
        """.replace(" "*8,"")))
        self.configs.kernel.tools.append(SynthesizerTool(name="Drum", code="""
            float dr;
            float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
            v *= fmax(0.01f, k);
            return v * rnd;
        """.replace(" "*8,"")))
        self.tacts = [SynthesizerProjectTact(0.0, len(self.configs.kernel.tools))]
        self.resize()

        
        while True:
            self.resize()
            self.draw()
            if not self.events():
                return
