import string
from collections import defaultdict
import shlex
import json
import string as literals
import os
import random
import re
import pathlib
import numpy
import pygame
import time
import math
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

class jsd(dict):
    def __init__(self, *args, **items):
        if items and not args:
            super(jsd, self).__init__(items)
        else:
            super(jsd, self).__init__(*args)

    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, name, value):
        self[name] = value
        return self

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

    def compile(self):
        # sort data
        self.inputs.sort(key=lambda x: x.time)

        # generate buffers
        result_length = int(44100 * max(map(lambda i: i.time + i.length, self.inputs)))
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
        self.api_function(result, result_length, input_tools, input_times, input_lengths, input_frequencies, input_volumes, input_len)

        # return
        return result


class SynthesizerProjectTone:
    def __init__(self, tool, frequency, time, length, volume):
        self.tool = tool
        self.frequency = frequency
        self.time = time
        self.length = length
        self.volume = volume


class SynthesizerProjectTact:
    def __init__(self, time):
        self.time = time
        self.notes: [SynthesizerProjectTone] = []

    @property
    def length(self):
        cnt = defaultdict(int)
        for i in self.notes:
            cnt[i.tool] += 1
        return max(cnt.values(), default=0) + 2 # 2 - fictive notes (in start and in the end)


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
    def from_wave(log_fn, name, file):
        # read file
        sound = pygame.mixer.Sound(file)
        y = pygame.sndarray.array(sound)
        # convert y to float64 in [-1.0, 1.0]
        old_type = y.dtype
        y = y.astype('float64')
        # normalize y
        y = (y - np.min(y)) / (np.max(y) - np.min(y)) * 2.0 - 1.0
        # make one chanel from two
        if len(y.shape) == 2 and y.shape[1] == 2:
            y = (y[:,0] + y[:,1]) * 0.5
        # multiply y with window (important part)
        window = np.zeros(y.shape, y.dtype)
        for i in range(window.shape[0]):
            x = i / window.shape[0]
            window[i] = math.sin(math.pi * x)
        y *= window
        # generate wave frequency information
        discrete = 1/44100  # interval of y
        a = np.fft.fft(y)[:y.shape[0]//2]
        f = np.fft.fftfreq(y.shape[0], d=discrete)[:y.shape[0]//2]
        # find maximum waves
        mod = np.abs(a)
        mod = np.column_stack((f, mod))
        # remove some first frequencies (constant shifts)
        mod = mod[2:]
        # sort other data
        mod = mod[mod[:,1].argsort()[::-1]]
        # find base frequency:
        base_frequency = mod[0][0] # max volume frequency
        # select max frequencies
        notes_count = min(2000, len(mod))
        selection = {}
        for i in range(notes_count):
            selection[mod[i][0] / base_frequency] = mod[i][1]
        # normalize selected amplitudes
        selection_sum = sum(selection.values())
        for i in selection:
            selection[i] /= selection_sum
        prc = np.sum(mod[:notes_count-1,1]) / np.sum(mod[:,1])
        log_fn(f"Used {notes_count} frequencies. (from {len(mod)}), quality: {prc*100:.1f}% , base: {base_frequency}")
        # generate code for file
        frq = ",".join(map(str, selection.keys()))
        amp = ",".join(map(str, selection.values()))
        code = f"""
            float frq[] = {{
                {frq}
            }};
            float amp[] = {{
                {amp}
            }};
            
            float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
            v *= fmax(0.01f, k);
            
            float res = 0.0, dr;
            for (int i = 0; i < {len(selection)}; ++i)
            {{
                float f = note->frequency * (frq[i] + 1);
                float fv = amp[i];
                dr = sin(s * f / 44100.0f * 0.5 * 3.1415926 * 2.0);
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

    def draw_tacts(self):
        line_height = 1+len(self.configs.kernel.tools)*2
        line_width = 5

        mus_y = math.inf
        sel_y = math.inf
        x, y = 0, -self.d.visual.cy
        for tact_id, i in enumerate(self.tacts):
            nx, ny = (x + i.length * line_width) % self.w, y + (x + i.length * line_width) // self.w * line_height
            # if visible
            if y <= -line_height <= ny or y <= self.ht+line_height <= ny or -line_height <= y <= self.ht+line_height:
                cnt = defaultdict(int)
                # draw notes
                for note in i.notes:
                    cnt[note.tool] += 1
                    px, py = (x + cnt[note.tool] * line_width) % self.w, y + (x + cnt[note.tool] * line_width) // self.w * line_height
                    is_playing = self.d.music.draw_time > note.time and (self.d.music.draw_time - note.time) < note.length
                    dy = note.tool * 2 + 1
                    if py + dy < self.ht:
                        color = c.gen.note.playing if is_playing else (c.gen.note.selected if tact_id == self.d.visual.selection.pos else c.gen.note.base)
                        addstr(py+dy, px, '|' + str(int(note.frequency)), color)
                # /draw notes
            # [get playing...]
            min_y, max_y = math.inf, -math.inf
            for cnt, note in enumerate(i.notes, 1):
                px, py = (x + cnt * line_width) % self.w, y + (x + cnt * line_width) // self.w * line_height
                min_y = min(min_y, py+self.d.visual.cy)
                max_y = max(max_y, py+self.d.visual.cy)
                if self.d.music.draw_time > note.time and (self.d.music.draw_time - note.time) < note.length:
                    mus_y = min(mus_y, py+self.d.visual.cy)
            if tact_id == self.d.visual.selection.pos:
                sel_y = (min_y + max_y) // 2
            # move to next note
            x, y = nx, ny
            if self.w - x < self.w // 2:
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

        # draw line
        sc.hline(self.ht, 0, '-', self.w)
        # draw low log panel
        for pos, _ in enumerate(self.d.log, 1):
            line, color = _
            addstr(self.ht + pos, 1, line[:self.log_w], color)
        # draw low info panel
        sc.vline(self.ht+1, self.log_w, '|', self.hl-1)
        addstr(self.ht+1, self.log_w + 2, 'mode:'+self.d.mode, c.base)


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
            elif self.d.mode == 'view':
                self.events_view(key)

    def events_view(self, key):
        if key == curses.KEY_UP:
            self.d.visual.follow_music = False
            self.d.visual.last_action_time = pygame.time.get_ticks()
            self.d.visual.cy -= 1
        if key == curses.KEY_DOWN:
            self.d.visual.follow_music = False
            self.d.visual.last_action_time = pygame.time.get_ticks()
            self.d.visual.cy += 1
        if key == curses.KEY_RIGHT:
            self.d.visual.follow_music = False
            self.d.visual.last_action_time = pygame.time.get_ticks()
            self.d.visual.selection.recalculate_cy = True
            if self.d.visual.selection.pos is None:
                self.d.visual.selection.pos = 0
            self.d.visual.selection.pos += 1
            if self.d.visual.selection.pos >= len(self.tacts):
                self.d.visual.selection.pos = len(self.tacts) - 1
        if key == curses.KEY_LEFT:
            self.d.visual.follow_music = False
            self.d.visual.last_action_time = pygame.time.get_ticks()
            self.d.visual.selection.recalculate_cy = True
            if self.d.visual.selection.pos is None:
                self.d.visual.selection.pos = 0
            self.d.visual.selection.pos -= 1
            if self.d.visual.selection.pos < 0:
                self.d.visual.selection.pos = 0
        if key in (ord('c'), ord('C')):
            self.compile()
        if key in (ord('p'), ord('P')):
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
        if key in (ord('t'), ord('T')):
            self.tool_panel()

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
                    raise Exception(f"Path <{os.path.basename(x)}> not exists")
                return x
            p = get_input(path_string, info_string="Enter path to file (for export into)")
            if p is None:
                return
            # to save
            s = x.to_string()
            with open(p, "w") as file:
                file.write(s)
        def rename_tool(x):
            s = get_input(name_request_string, info_string="Enter name of tool, another tool's name to copy, <del> to delete")
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
        def swap_tools(tid1, tid2):
            self.configs.kernel.tools[tid1], self.configs.kernel.tools[tid2] = self.configs.kernel.tools[tid2], self.configs.kernel.tools[tid1]
            for t in self.tacts:
                for note in t.notes:
                    if note.tool == tid2:
                        note.tool = tid1
                    elif note.tool == tid1:
                        note.tool = tid2
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
            "volume": lambda x: setattr(x.configs, "volume", f) if (f := get_input(in_float_01, info_string="Enter volume of tool")) is not None else None,
            "legato_mod": lambda x: setattr(x.configs, "legato_mod", f) if (f := get_input(in_float_positive, info_string="Enter legato mod of tool")) is not None else None,
            "use stereo": lambda x: setattr(x.configs, 'stereo', not x.configs.stereo),
            "export": lambda x: save_tool(x),
        }
        def get_input(validate, required=False, info_string=""):
            s = ""
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
                    elif key == 8: # backspace
                        s = s[:-1]
                    elif key == 10: # confirm
                        if no_error:
                            waiting = False
                            break
                    elif chr(key) in string.printable:
                        s += chr(key)
            try:
                return validate(s)
            except Exception as e:
                return None
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
                name = get_input(new_name_string, required=False, info_string="Enter name of tool")
                if name is None:
                    return
                code = f"\n    /*Enter code here to generate sample 's' from note 'note' (rnd is white noise from -1 to 1)*/{base_of_code}"
                t = SynthesizerTool(name, code)
                self.configs.kernel.tools.append(t)
            elif sel == 1:
                def path_string(x):
                    if not os.path.exists(x):
                        raise Exception(f"Path <{x}> not exists")
                    return x
                filename = get_input(path_string, info_string="Enter path to file (to load from)")
                if filename is None:
                    return
                try:
                    with open(filename, "r") as file:
                        s = file.read()
                    t = SynthesizerTool.from_string(s)
                    self.configs.kernel.tools.append(t)
                except Exception as e:
                    self.log(str(e),c.base)
                    return
            elif sel == 2:
                def path_string(x):
                    if not os.path.exists(x):
                        raise Exception(f"Path <{x}> not exists")
                    return x
                name = get_input(new_name_string, info_string="Enter name of tool")
                if name is None:
                    return
                filename = get_input(path_string, info_string="Enter path to music (mp3/wav/ogg/etc) file (to create from)")
                if filename is None:
                    return
                try:
                    t = SynthesizerTool.from_wave(lambda x: self.log(x, c.log.info), name, filename)
                    self.configs.kernel.tools.append(t)
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

    def create(self, what, dt=0.25, X=False):
        lm = 1
        fqcorr = 0.5

        def tact(time=None):
            self.tacts.append(SynthesizerProjectTact(time))

        def add(t, fq, l=1.0, volume=1.0, group=0):
            if what == 'm' and fq <= 300:
                group = 1
            self.tacts[-1].notes.append(SynthesizerProjectTone(group, fq, t*dt, l*dt, volume))
            return t + l

        def addc(t, ch, l=1):
            for cc, i in enumerate(sorted(ch)):
                ovh = l * 0.05 * cc
                add(t + ovh, i, l - ovh, volume=2.0 / len(ch))
            return t + l

        def mx(fq, oct):
            return fq * pow(2.0, oct + 1)

        def bt(t, l=1):
            v = 1.0
            self.tacts[-1].notes.append(SynthesizerProjectTone(2, -1.0, t*dt, dt*l*0.5, v))
            self.x.add(GeneratorTone(2, t*dt, dt*l*lm*0.5,v,-1.0))
            return t + l

        # notes

        C = 261.63  # do
        C0 = 277.18  # do  #
        D = 293.33  # re
        D0 = 311.13  # re  #
        E = 329.23  # mi
        F = 349.23  # fa
        F0 = 369.99  # fa  #
        G = 392.00  # sol
        G0 = 415.30  # sol #
        A = 440.00  # la
        A0 = 466.16  # la  #
        B = 493.88  # si

        # chords

        _Am = [mx(A, -2),
               mx(E, -1),
               mx(A, -1),
               mx(C, 0),
               mx(E, 0)]
        _Em = [mx(E, -2),
               mx(B, -2),
               mx(E, -1),
               mx(G, -1),
               mx(B, -1),
               mx(E, 0)]
        _E = [mx(E, -2),
               mx(B, -2),
               mx(E, -1),
               mx(G0, -1),
               mx(B, -1),
               mx(E, 0)]
        _B7 = [mx(B, -2),
              mx(D0, -1),
              mx(A, -1),
              mx(B, -1),
              mx(F0, 0)]
        _C = [mx(C, -1),
              mx(E, -1),
              mx(G, -1),
              mx(C, 0),
              mx(E, 0)]
        _D = [mx(D, -1),
               mx(A, -1),
               mx(D, 0),
               mx(F0, 0)]
        _Dm = [mx(D, -1),
               mx(A, -1),
               mx(D, 0),
               mx(E, 0)]
        _G = [mx(G, -2),
              mx(B, -2),
              mx(D, -1),
              mx(G, -1),
              mx(G, 0)]

        # gen track
        def tsoy():
            et = 0
            def skip():
                nonlocal et
                for i in range(4):
                    tact()
                    add(et, mx(A, 1), l=1.5)
                    et += 0.025
                    add(et, mx(F, 1), l=1.5)
                    et += 0.025
                    add(et, mx(C, 1), l=1.5)
                    et += 0.025
                    add(et, mx(A, 0), l=1.5)
                    et += 0.025
                    add(et, mx(D, 0), l=1.5)

                    tact()
                    et += 1 - 0.025 * 4

                    add(et, mx(D, 0), l=1.5)
                    et += 0.025
                    add(et, mx(A, 0), l=1.5)
                    et += 0.025
                    add(et, mx(C, 1), l=1.5)
                    et += 0.025
                    add(et, mx(F, 1), l=1.5)
                    et += 0.025
                    add(et, mx(A, 1), l=1.5)

                    tact()
                    et += 1 - 0.025 * 4

                    add(et, mx(A, 1), l=1.5)
                    et += 0.025
                    add(et, mx(F, 1), l=1.5)
                    et += 0.025
                    add(et, mx(C, 1), l=1.5)
                    et += 0.025
                    add(et, mx(A, 0), l=1.5)
                    et += 0.025
                    add(et, mx(D, 0), l=1.5)

                    tact()
                    et += 1 - 0.025 * 4

                    add(et, mx(D, 0), l=1.5)
                    et += 0.025
                    add(et, mx(A, 0), l=1.5)
                    et += 0.025
                    add(et, mx(C, 1), l=1.5)
                    et += 0.025
                    add(et, mx(F, 1), l=1.5)
                    et += 0.025
                    add(et, mx(C, 2), l=1.5)

                    et += 1 - 0.025 * 4

            def beat(t, ch, l=1):
                global et
                mult = 2.0
                for i in range(2):
                    tact()
                    addc(t + 0 * l + 8 * l * i, ch, l*mult)
                    addc(t + 1 * l + 8 * l * i, ch, l*mult)
                    bt(t + 2 * l + 8 * l * i, l)
                    addc(t + 3 * l + 8 * l * i, ch, l*mult)
                    addc(t + 4 * l + 8 * l * i, ch, l*mult)
                    addc(t + 5 * l + 8 * l * i, ch, l*mult)
                    bt(t + 6 * l + 8 * l * i, l)
                addc(t + 7 * l + 8 * l, ch, l*mult)
                return t + 16 * l

            # TRACK

            skip()

            for i in range(2):
                et = beat(et, _Am)
                et = beat(et, _C)
                et = beat(et, _Dm)
                et = beat(et, _G)

            et = beat(et, _Dm)
            et = beat(et, _Am)

            skip()

            for i in range(2):
                et = beat(et, _Am)
                et = beat(et, _C)
                et = beat(et, _Dm)
                et = beat(et, _G)

            et = beat(et, _Dm)
            et = beat(et, _Am)

            skip()

        def metal1():
            et = 0
            def beat2(t, ch1, ch2, ch3, l=1):
                global et
                # play notes
                tact()
                add(t+l*0, ch1[0], l*6)
                add(t+l*1, ch1[-3], l)
                add(t+l*2, ch1[-2], l)
                add(t+l*3, ch1[-1], l)
                add(t+l*4.0, ch1[-4], l*0.5)
                add(t+l*4.5, ch1[-1], l*0.5)
                add(t+l*5.0, ch1[-2], l*0.5)
                add(t+l*5.5, ch1[-3], l*0.5)
                add(t+l*6, ch2[0], l*3)
                add(t+l*6, ch2[-1], l*3)
                add(t+l*7.0, ch2[0], l*0.5)
                add(t+l*7.5, ch2[-1], l*0.5)
                add(t+l*8.0, ch2[-2], l*0.5)
                add(t+l*8.5, ch2[-3], l*0.5)
                add(t+l*9, ch3[0], l*3)
                add(t+l*9, ch3[-1], l*1.0)
                add(t+l*10.0, ch3[-2], l*0.5)
                add(t+l*10.5, ch3[-3], l*0.5)
                add(t+l*11.0, mx(G,  -2), l*0.5)
                add(t+l*11.5, mx(F0, -2), l*0.5)
                return t + 4 * 3 * l

            def beat22(t, ch1, ch2, ch3, l=1):
                global et
                # play notes
                tact()
                add(t+l*0, ch1[0], l*6)
                add(t+l*1, ch1[-3], l)
                add(t+l*2, ch1[-2], l)
                add(t+l*3, ch1[-1], l)
                add(t+l*4.0, ch1[-4], l*0.5)
                add(t+l*4.5, ch1[-1], l*0.5)
                add(t+l*5.0, ch1[-2], l*0.5)
                add(t+l*5.5, ch1[-3], l*0.5)
                add(t+l*6, ch2[0], l*3)
                add(t+l*6, ch2[-1], l*3)
                add(t+l*7.0, ch2[0], l*0.5)
                add(t+l*7.5, ch2[-1], l*0.5)
                add(t+l*8.0, ch2[-2], l*0.5)
                add(t+l*8.5, ch2[-3], l*0.5)
                add(t+l*9, ch3[0], l*3)
                add(t+l*9, ch3[-1], l*3)
                add(t+l*10, ch3[ -1], l*0.5)
                add(t+l*11, ch3[ -2], l*0.5)
                return t + 2 * 6 * l

            def beat23(t, ch1, ch2, ch3, l=1):
                global et
                # play notes
                tact()
                add(t+l*0, ch1[0], l*3)
                add(t+l*1, ch1[1], l)
                add(t+l*2, ch1[-1], l)
                add(t+l*2, ch1[-3], l)
                add(t+l*3, ch2[0], l*3)
                add(t+l*3, ch2[1], l*3)
                add(t+l*3, ch2[-1], l*3)
                add(t+l*3, ch2[-2], l*3)
                add(t+l*4.0, ch2[0], l*0.5)
                add(t+l*4.5, ch2[-1], l*0.5)
                add(t+l*5, ch2[-2], l)

                add(t+l*6, ch3[0], l*6)
                add(t+l*6, ch3[-1], l*3)
                add(t+l*7, ch3[-3], l)
                add(t+l*8, ch3[-2], l)
                add(t+l*9, ch3[-1], l)
                add(t+l*10, ch3[-2], l)
                add(t+l*11, ch3[-3], l)

                add(t+l*12, ch3[0], l*6)
                add(t+l*13, ch3[-3], l)
                add(t+l*14, ch3[-2], l)
                add(t+l*15, ch3[-1], l)
                add(t+l*16, ch3[-2], l)
                add(t+l*17.0, mx(G,-2), l*0.5)
                add(t+l*17.5, mx(F0,-2), l)
                return t + 3 * 6 * l

            def beat(t, ch, l=1):
                global et
                # play notes
                addc(t, ch, l*4)
                return t + 4 * l

            # TRACK
            for i in range(3):
                for j in range(2):
                    et = beat2(et, _Em, _D, _C)
                et = beat22(et, _Em, _D, _C)
                et = beat23(et, _G, _B7, _Em)


            et = beat(et, _C, l=2)
            et = beat(et, _Am, l=2)
            for i in range(2):
                et = beat(et, _D,l=0.5)
                et = beat(et, _D,l=0.25)
                et = beat(et, _D,l=0.25)
                et = beat(et, _D,l=0.25)
                et = beat(et, _D,l=0.25)
                et = beat(et, _D,l=0.5)
                et = beat(et, _D,l=0.5)
                et = beat(et, _D,l=0.5)
                et = beat(et, _C,l=2)
                et = beat(et, _Am,l=2)
            et = beat(et, _D)
            et = beat(et, _Em)
            et = beat(et, _Em)
            et += 4

            for j in range(3):
                et = beat2(et, _Em, _D, _C)
            et = beat2(et, _G, _B7, _Em)


            et = beat(et, _C, l=2)
            et = beat(et, _Am, l=2)
            for i in range(2):
                et = beat(et, _D,l=0.5)
                et = beat(et, _D,l=0.25)
                et = beat(et, _D,l=0.25)
                et = beat(et, _D,l=0.25)
                et = beat(et, _D,l=0.25)
                et = beat(et, _D,l=0.5)
                et = beat(et, _D,l=0.5)
                et = beat(et, _D,l=0.5)
                et = beat(et, _C,l=2)
                et = beat(et, _Am,l=2)
            et = beat(et, _D)
            et = beat(et, _Em)
            et = beat(et, _Em)
            et += 4

            for i in range(2):
                for j in range(3):
                    et = beat2(et, _Em, _D, _C)
                et = beat2(et, _G, _B7, _Em)


            et = beat(et, _C, l=2)
            et = beat(et, _Am, l=2)
            for i in range(4):
                et = beat(et, _D,l=0.5)
                et = beat(et, _D,l=0.25)
                et = beat(et, _D,l=0.25)
                et = beat(et, _D,l=0.25)
                et = beat(et, _D,l=0.25)
                et = beat(et, _D,l=0.5)
                et = beat(et, _D,l=0.5)
                et = beat(et, _D,l=0.5)
                et = beat(et, _C,l=2)
                et = beat(et, _Am,l=2)
            et = beat(et, _D)
            et = beat(et, _Em,l=2)
            et = beat(et, _Em,l=4)

        def river():
            #    DO   DO#    RE   RE#   MI   FA   FA#   SO   SO#  LA   LA#    SI
            r = ['0', '0#', '1', '1#', '2', '3', '3#', '4', '4#', '5', '5#', '6']
            def note(z, x, t, l):
                if z < 0 or z == 0 and x < '4':
                    group = 1
                else:
                    group = 0
                add(t, 523.25 * pow(2, z + r.index(x) / 12), l, 1.0, group)

            t = 0
            tact(t)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)

            note(1, '5',  t+0.0, 1)
            note(1, '4#', t+1.0, 1)
            note(1, '5',  t+2.0, 1)
            note(1, '4#', t+3.0, 1)

            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)

            note(1, '5',  t+4.0, 1)
            note(1, '2',  t+5.0, 1)
            note(1, '5',  t+6.0, 1)
            note(1, '1',  t+7.0, 1+3.0)

            t += 12
            tact(t)

            note(0, '5', t-1.0, 0.5)
            note(1, '0#', t-0.5, 0.5)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)

            note(1, '5',  t+0.0, 1)
            note(1, '4#', t+1.0, 1)
            note(1, '5',  t+2.0, 1)
            note(1, '4#', t+3.0, 1)

            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)

            note(1, '5',  t+4.0, 1)
            note(1, '2',  t+5.0, 1)
            note(1, '5',  t+6.0, 1)
            note(1, '1',  t+7.0, 1+4)

            t += 12
            tact(t)

            note(0, '5', t-1.0, 0.5)
            note(1, '0#', t-0.5, 0.5)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(1, '5',  t+0.0, 1)
            note(1, '4#', t+1.0, .5)
            note(1, '5',  t+1.5, 1)
            note(0, '5',  t+2.5, .5)
            note(1, '4#',  t+3.0, .5)
            note(1, '5',  t+3.5, 1)
            note(0, '5',  t+4.5, .5)
            note(1, '2',  t+5.0, .5)
            note(1, '5',  t+5.5, 1)

            note(0, '5',  t+6.5, .5)
            note(1, '1',  t+7.0, .5)
            note(0, '5',  t+7.5, .5)

            t += 8
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-1, '4#', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '2', t+6.0, 1)

            note(0, '6',  t-0.2, 0.4)
            note(1, '0#',  t+0.0, 1)
            note(1, '1',  t+1.0, 1)
            note(1, '2',  t+2.0, 1)
            note(0, '5',  t+2.0, 1)
            note(1, '0#',  t+3.0, 1)
            note(0, '4#',  t+4.0, 3)
            note(0, '6',  t+4.0, 3)

            t += 8
            tact(t)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)

            note(0, '5', t-1.0, 0.5)
            note(0, '4#', t-0.5, 0.5)
            note(0, '5',  t+0.0, 2.5)
            note(0, '2', t+2.5, 0.5)
            note(0, '5',  t+3.0, 0.5)
            note(0, '6', t+3.5, 0.5)
            note(1, '0#', t+4.0, 3)

            t += 8
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-1, '2', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '4#', t+6.0, 1)

            note(1, '0#', t-1.0, 0.5)
            note(1, '1', t-0.5, 0.5)
            note(1, '2',  t+0.0, 3)
            note(1, '1',  t+3.0, 0.5)
            note(1, '0#', t+3.5, 0.5)
            note(0, '6', t+4.0, 3)

            t += 8
            tact(t)

            note(0, '5', t-0.4, 0.4)
            note(1, '0#', t-0.2, 0.4)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(1, '5',  t+0.0, 1)
            note(1, '4#', t+1.0, .5)
            note(1, '5',  t+1.5, 1)
            note(0, '5',  t+2.5, .5)
            note(1, '4#',  t+3.0, .5)
            note(1, '5',  t+3.5, 1)
            note(0, '5',  t+4.5, .5)
            note(1, '2',  t+5.0, .5)
            note(1, '5',  t+5.5, 1)

            note(0, '5',  t+6.5, .5)
            note(1, '1',  t+7.0, .5)
            note(0, '5',  t+7.5, .5)

            t += 8
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-2, '5', t+3.0, 1)
            note(-1, '2', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '2', t+6.0, 1)

            note(0, '6',  t-0.2, 0.4)
            note(1, '0#',  t+0.0, 1)
            note(1, '1',  t+1.0, 1)
            note(1, '2',  t+2.0, 1)
            note(2, '0#',  t+3.0, 1)
            note(1, '6',  t+4.0, 1)
            note(1, '2',  t+5.0, 1)
            note(1, '6',  t+5.8, 0.4)
            note(2, '0#',  t+6.0, 0.4)
            note(1, '6',  t+6.2, 0.8)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            t += 8.0
            tact(t)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(1, '5',  t+0.0, 3)
            note(1, '2',  t+0.0, 3)

            note(0, '5',  t+3.0, 0.5)
            note(0, '6',  t+3.5, 0.5)
            note(1, '0#',  t+4.0, 1)
            note(0, '2',  t+5.0, 1)
            note(0, '5',  t+6.0, 1)
            note(1, '0#',  t+7.0, .5)
            note(1, '1',  t+7.5, .5)

            t += 8.0
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-2, '5', t+3.0, 1)
            note(-1, '2', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '2', t+7.0, 1)

            note(1, '2',  t+0.0, 1)
            note(0, '2',  t+1.0, 1)
            note(1, '0#',  t+2.0, 1)
            note(1, '1',  t+3.0, 0.5)
            note(1, '0#',  t+3.5, 0.5)
            note(0, '6',  t+4.0, 2)

            note(1, '5',  t+6.0, 0.5)
            note(1, '6',  t+6.5, 0.5)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            t += 8.0
            tact(t)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)
            note(-1, '3#', t+3.0, 1)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(1, '5',  t+0.0, 0.5)
            note(0, '5',  t+0.5, 0.5)
            note(1, '2',  t+1.0, 0.5)
            note(0, '5',  t+1.5, 0.5)
            note(1, '5',  t+2.0, 0.5)
            note(1, '6',  t+2.5, 0.5)
            note(1, '5',  t+3.0, 0.5)
            note(1, '4#',  t+3.5, 0.5)
            note(1, '5',  t+4.0, 0.5)
            note(0, '5',  t+4.5, 0.5)
            note(1, '2',  t+5.0, 0.5)
            note(0, '5',  t+5.5, 0.5)
            note(1, '5',  t+6.0, 0.5)
            note(1, '6',  t+6.5, 0.5)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            t += 8.0
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-2, '5', t+3.0, 1)
            note(-1, '2', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '2', t+7.0, 1)

            note(1, '5',  t+0.0, 0.5)
            note(1, '6',  t+0.5, 0.5)
            note(2, '0#',  t+1.0, 0.5)
            note(2, '1',  t+1.5, 0.5)
            note(2, '2',  t+2.0, 0.5)
            note(2, '0#',  t+2.5, 0.5)
            note(1, '6',  t+3.0, 0.5)
            note(1, '5',  t+3.5, 0.5)
            note(1, '4#',  t+4.0, 1)
            note(0, '6',  t+5.0, 1)
            note(1, '5',  t+6.0, 0.5)
            note(1, '6',  t+6.5, 0.5)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            t += 8.0
            tact(t)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)
            note(-1, '3#', t+3.0, 1)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(1, '5',  t+0.0, 0.5)
            note(0, '5',  t+0.5, 0.5)
            note(1, '2',  t+1.0, 0.5)
            note(0, '5',  t+1.5, 0.5)
            note(1, '5',  t+2.0, 0.5)
            note(1, '6',  t+2.5, 0.5)
            note(1, '5',  t+3.0, 0.5)
            note(1, '4#',  t+3.5, 0.5)
            note(1, '5',  t+4.0, 0.5)
            note(0, '5',  t+4.5, 0.5)
            note(1, '2',  t+5.0, 0.5)
            note(0, '5',  t+5.5, 0.5)
            note(1, '5',  t+6.0, 0.5)
            note(1, '6',  t+6.5, 0.5)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            t += 8.0
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-2, '5', t+3.0, 1)
            note(-1, '2', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '2', t+7.0, 1)

            note(1, '5',  t+0.0, 0.5)
            note(1, '6',  t+0.5, 0.5)
            note(2, '0#',  t+1.0, 0.5)
            note(2, '1',  t+1.5, 0.5)
            note(2, '2',  t+2.0, 0.5)
            note(2, '0#',  t+2.5, 0.5)
            note(1, '6',  t+3.0, 0.5)
            note(1, '5',  t+3.5, 0.5)
            note(1, '4#',  t+4.0, 1)
            note(0, '6',  t+5.0, 1)
            note(1, '5',  t+6.0, 0.5)
            note(1, '5',  t+6.5, 0.25)
            note(1, '6',  t+6.75, 0.25)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            #>> SECOND PAGE

            t += 8.0
            tact(t)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)
            note(-1, '3#', t+3.0, 1)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(1, '5',  t+0.0, 0.5)
            note(0, '5',  t+0.5, 0.5)
            note(1, '2',  t+1.0, 0.5)
            note(0, '5',  t+1.5, 0.5)
            note(1, '5',  t+2.0, 0.75)
            note(1, '6',  t+2.75, 0.25)
            note(1, '5',  t+3.0, 0.5)
            note(1, '4#',  t+3.5, 0.5)
            note(1, '5',  t+4.0, 0.5)
            note(0, '5',  t+4.5, 0.5)
            note(1, '2',  t+5.0, 0.5)
            note(0, '5',  t+5.5, 0.5)
            note(1, '5',  t+6.0, 0.75)
            note(1, '6',  t+6.75, 0.25)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            t += 8.0
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-2, '5', t+3.0, 1)
            note(-1, '2', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '2', t+7.0, 1)

            note(1, '5',  t+0.0, 0.5)
            note(1, '6',  t+0.5, 0.5)
            note(2, '0#',  t+1.0, 0.5)
            note(2, '1',  t+1.5, 0.5)
            note(2, '2',  t+2.0, 0.5)
            note(2, '0#',  t+2.5, 0.5)
            note(1, '6',  t+3.0, 0.5)
            note(1, '5',  t+3.5, 0.5)
            note(1, '4#',  t+4.0, 1)
            note(0, '6',  t+5.0, 1)
            note(1, '5',  t+6.0, 0.75)
            note(1, '6',  t+6.75, 0.25)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            t += 8.0
            tact(t)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)
            note(-1, '3#', t+3.0, 1)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(1, '5',  t+0.0, 0.5)
            note(0, '5',  t+0.5, 0.5)
            note(1, '2',  t+1.0, 0.5)
            note(0, '5',  t+1.5, 0.5)
            note(1, '5',  t+2.0, 0.75)
            note(1, '6',  t+2.75, 0.25)
            note(1, '5',  t+3.0, 0.5)
            note(1, '4#',  t+3.5, 0.5)
            note(1, '5',  t+4.0, 0.5)
            note(0, '5',  t+4.5, 0.5)
            note(1, '2',  t+5.0, 0.5)
            note(0, '5',  t+5.5, 0.5)
            note(1, '5',  t+6.0, 0.5)
            note(1, '6',  t+6.5, 0.5)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            t += 8.0
            tact(t)

            # second line

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-2, '5', t+3.0, 1)
            note(-1, '2', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '2', t+6.0, 1+4)

            note(1, '5',  t+0.0, 0.5)
            note(1, '6',  t+0.5, 0.5)
            note(2, '0#',  t+1.0, 0.5)
            note(2, '1',  t+1.5, 0.5)
            note(2, '2',  t+2.0, 0.5)
            note(2, '0#',  t+2.5, 0.5)
            note(1, '6',  t+3.0, 0.5)
            note(1, '5',  t+3.5, 0.5)
            note(1, '4#',  t+4.0, 1)
            note(0, '6',  t+5.0, 1)
            note(0, '4#',  t+6.0, 1)
            note(0, '2',  t+7.0, 1+3)

            # SECOND PART (C)

            t += 11
            tact(t)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(0, '5', t-1.0, 0.5)
            note(1, '0#', t-0.5, 0.5)
            note(1, '5',  t+0.0, 1)
            note(1, '4#', t+1.0, .5)
            note(1, '5',  t+1.5, 1)
            note(0, '5',  t+2.5, .5)
            note(1, '4#',  t+3.0, .5)
            note(1, '5',  t+3.5, 1)
            note(0, '5',  t+4.5, .5)
            note(1, '2',  t+5.0, .5)
            note(1, '5',  t+5.5, 1)

            note(0, '5',  t+6.5, .5)
            note(1, '1',  t+7.0, .5)
            note(0, '5',  t+7.5, .5)

            t += 8
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-1, '4#', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '2', t+6.0, 1)

            note(0, '6',  t-0.2, 0.4)
            note(1, '0#',  t+0.0, 1)
            note(1, '1',  t+1.0, 1)
            note(1, '2',  t+2.0, 1)
            note(0, '5',  t+2.0, 1)
            note(1, '0#',  t+3.0, 1)
            note(0, '4#',  t+4.0, 3)
            note(0, '6',  t+4.0, 3)

            t += 8
            tact(t)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 3)
            note(-1, '1', t+4.0, 1)
            note(0, '2', t+5.0, 2)
            note(0, '2', t+7.0, 1)

            note(0, '5', t-1.0, 0.5)
            note(0, '4#', t-0.5, 0.5)
            note(0, '5',  t+0.0, 2.5)
            note(0, '2',  t+0.0, 2.5)
            note(0, '2', t+2.5, 0.5)
            note(0, '5',  t+3.0, 0.5)
            note(0, '6', t+3.5, 0.5)
            note(1, '0#', t+4.0, 0.5)
            note(0, '2', t+4.5, 0.5)
            note(0, '5',  t+5.0, 0.5)
            note(0, '6', t+5.5, 0.5)
            note(1, '0#', t+6.0, 0.5)
            note(0, '2',  t+6.5, 0.5)
            note(1, '0#', t+7.0, 0.5)
            note(1, '1', t+7.5, 0.5)

            t += 8
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-2, '5', t+3.0, 1)
            note(-1, '5', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '2', t+6.0, 2)

            note(1, '2', t+0.0, 0.5)
            note(0, '2', t+0.5, 0.5)
            note(1, '0#', t+1.0, 0.5)
            note(1, '1', t+1.5, 0.5)
            note(1, '2', t+2.0, 0.5)
            note(0, '2', t+2.5, 0.5)
            note(1, '1', t+3.0, 0.5)
            note(1, '0#', t+3.5, 0.5)
            note(0, '6', t+4.0, 0.5)
            note(0, '2', t+4.5, 0.5)
            note(1, '1', t+5.0, 0.5)
            note(1, '0#', t+5.5, 0.5)
            note(0, '6', t+6.0, 1)
            note(0, '4#', t+7.0, 1)

            t += 8
            tact(t)

            note(0, '5', t-0.4, 0.4)
            note(1, '0#', t-0.2, 0.4)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(1, '5',  t+0.0, 1)
            note(1, '4#', t+1.0, .5)
            note(1, '5',  t+1.5, 1)
            note(0, '5',  t+2.5, .5)
            note(1, '4#',  t+3.0, .5)
            note(1, '5',  t+3.5, 1)
            note(0, '5',  t+4.5, .5)
            note(1, '2',  t+5.0, .5)
            note(1, '5',  t+5.5, 1)

            note(0, '5',  t+6.5, .5)
            note(1, '1',  t+7.0, .5)
            note(0, '5',  t+7.5, .5)

            t += 8
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-2, '5', t+3.0, 1)
            note(-1, '2', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '2', t+6.0, 1)

            note(0, '6',  t-0.2, 0.4)
            note(1, '0#',  t+0.0, 1)
            note(1, '1',  t+1.0, 1)
            note(1, '2',  t+2.0, 1)
            note(2, '0#',  t+3.0, 1)
            note(1, '6',  t+4.0, 1)
            note(1, '2',  t+5.0, 1)
            note(1, '6',  t+5.8, 0.4)
            note(2, '0#',  t+6.0, 0.4)
            note(1, '6',  t+6.2, 0.8)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            t += 8
            tact(t)

            # FOURTH LINE SECOND PAGE SECOND TACT

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 2)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(1, '5',  t+0.0, 3)
            note(1, '2',  t+0.0, 3)
            note(0, '5',  t+3.0, 0.5)
            note(0, '6', t+3.5, 0.5)
            note(1, '0#', t+4.0, 0.5)
            note(0, '2', t+4.5, 0.5)
            note(0, '5',  t+5.0, 0.5)
            note(0, '6', t+5.5, 0.5)
            note(1, '0#', t+6.0, 0.5)
            note(0, '2',  t+6.5, 0.5)
            note(1, '0#', t+7.0, 0.5)
            note(1, '1', t+7.5, 0.5)

            t += 8
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-2, '5', t+3.0, 1)
            note(-2, '2', t+4.0, 1)
            note(-2, '6', t+5.0, 1)
            note(-1, '4#', t+6.0, 1)
            note(-2, '2', t+7.0, 1)

            note(1, '2', t+0.0, 0.5)
            note(0, '2', t+0.5, 0.5)
            note(1, '0#', t+1.0, 0.5)
            note(1, '1', t+1.5, 0.5)
            note(1, '2', t+2.0, 0.5)
            note(0, '2', t+2.5, 0.5)
            note(1, '1', t+3.0, 0.5)
            note(1, '0#', t+3.5, 0.5)
            note(0, '6', t+4.0, 0.5)
            note(0, '2', t+4.5, 0.5)
            note(1, '1', t+5.0, 0.5)
            note(1, '0#', t+5.5, 0.5)

            note(1, '5', t+6.0, 0.5)
            note(1, '6', t+6.5, 0.5)
            note(1, '5', t+7.0, 0.5)
            note(1, '4#', t+7.5, 0.5)

            # LAST LINE
            t += 8.0
            tact(t)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)
            note(-1, '3#', t+3.0, 1)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(1, '4#',  t+0.0, 0.2)
            note(1, '5',  t+0.2, 0.3)
            note(0, '5',  t+0.5, 0.5)
            note(1, '2',  t+1.0, 0.5)
            note(0, '5',  t+1.5, 0.5)
            note(1, '5',  t+2.0, 0.5)
            note(1, '5',  t+2.5, 0.25)
            note(1, '6',  t+2.75, 0.25)
            note(1, '5',  t+3.0, 0.5)
            note(1, '4#',  t+3.5, 0.5)
            note(1, '5',  t+4.0, 0.5)
            note(0, '5',  t+4.5, 0.5)
            note(1, '2',  t+5.0, 0.5)
            note(0, '5',  t+5.5, 0.5)
            note(1, '5',  t+6.0, 0.5)
            note(1, '5',  t+6.5, 0.25)
            note(1, '6',  t+6.75, 0.25)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            t += 8.0
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-2, '5', t+3.0, 1)
            note(-1, '2', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '2', t+7.0, 1)

            note(1, '5',  t+0.0, 0.5)
            note(1, '6',  t+0.5, 0.5)
            note(2, '0#',  t+1.0, 0.5)
            note(2, '1',  t+1.5, 0.5)
            note(2, '2',  t+2.0, 0.5)
            note(2, '0#',  t+2.5, 0.3)
            note(1, '6',  t+2.8, 0.2) # (c)
            note(2, '0#',  t+3.0, 0.2) # (c)
            note(1, '6',  t+3.2, 0.3)
            note(1, '5',  t+3.5, 0.5)
            note(1, '4#',  t+4.0, 0.5)
            note(0, '6',  t+4.5, 0.5)
            note(1, '2',  t+5.0, 0.5)
            note(0, '6',  t+5.5, 0.5)
            note(1, '5',  t+6.0, 0.5)
            note(1, '5',  t+6.5, 0.25)
            note(1, '6',  t+6.75, 0.25)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            # THIRD PAGE
            t += 8.0
            tact(t)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)
            note(-1, '3#', t+3.0, 1)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(1, '4#',  t+0.0, 0.2)
            note(1, '5',  t+0.2, 0.3)
            note(0, '5',  t+0.5, 0.5)
            note(1, '2',  t+1.0, 0.5)
            note(0, '5',  t+1.5, 0.5)
            note(1, '5',  t+2.0, 0.5)
            note(1, '5',  t+2.5, 0.25)
            note(1, '6',  t+2.75, 0.25)
            note(1, '5',  t+3.0, 0.5)
            note(1, '4#',  t+3.5, 0.5)
            note(1, '5',  t+4.0, 0.5)
            note(0, '5',  t+4.5, 0.5)
            note(1, '2',  t+5.0, 0.5)
            note(0, '5',  t+5.5, 0.5)
            note(1, '5',  t+6.0, 0.5)
            note(1, '5',  t+6.5, 0.25)
            note(1, '6',  t+6.75, 0.25)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            t += 8.0
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-2, '5', t+3.0, 1)
            note(-1, '2', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '2', t+7.0, 1)

            note(1, '5',  t+0.0, 0.5)
            note(1, '6',  t+0.5, 0.5)
            note(2, '0#',  t+1.0, 0.5)
            note(2, '1',  t+1.5, 0.5)
            note(2, '2',  t+2.0, 0.5)
            note(2, '0#',  t+2.5, 0.3)
            note(1, '6',  t+2.8, 0.2) # (c)
            note(2, '0#',  t+3.0, 0.2) # (c)
            note(1, '6',  t+3.2, 0.3)
            note(1, '5',  t+3.5, 0.5)
            note(1, '4#',  t+4.0, 0.5)
            note(0, '6',  t+4.5, 0.5)
            note(1, '2',  t+5.0, 0.5)
            note(0, '6',  t+5.5, 0.5)
            note(1, '5',  t+6.0, 0.5)
            note(1, '5',  t+6.5, 0.25)
            note(1, '6',  t+6.75, 0.25)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            # SECOND LINE
            t += 8.0
            tact(t)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)
            note(-1, '3#', t+3.0, 1)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(1, '5',  t+0.0, 0.5)
            note(0, '5',  t+0.5, 0.5)
            note(1, '2',  t+1.0, 0.5)
            note(0, '5',  t+1.5, 0.5)
            note(1, '5',  t+2.0, 0.5)
            note(1, '6',  t+2.5, 0.5)
            note(1, '5',  t+3.0, 0.5)
            note(1, '4#',  t+3.5, 0.5)
            note(1, '5',  t+4.0, 0.5)
            note(0, '5',  t+4.5, 0.5)
            note(1, '2',  t+5.0, 0.5)
            note(0, '5',  t+5.5, 0.5)
            note(1, '5',  t+6.0, 0.5)
            note(1, '5',  t+6.5, 0.25)
            note(1, '6',  t+6.75, 0.25)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            t += 8.0
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-2, '5', t+3.0, 1)
            note(-1, '2', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '2', t+7.0, 1)

            note(1, '5',  t+0.0, 0.5)
            note(1, '6',  t+0.5, 0.5)
            note(2, '0#',  t+1.0, 0.5)
            note(2, '1',  t+1.5, 0.5)
            note(2, '2',  t+2.0, 0.5)
            note(2, '0#',  t+2.5, 0.5)
            note(1, '6',  t+3.0, 0.5)
            note(1, '5',  t+3.5, 0.5)
            note(1, '4#',  t+4.0, 1)
            note(0, '6',  t+5.0, 1)
            note(1, '5',  t+6.0, 0.5)
            note(1, '5',  t+6.5, 0.25)
            note(1, '6',  t+6.75, 0.25)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            # THIRD LINE
            t += 8.0
            tact(t)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 1)
            note(-1, '3#', t+3.0, 1)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(1, '5',  t+0.0, 0.5)
            note(0, '5',  t+0.5, 0.5)
            note(1, '2',  t+1.0, 0.5)
            note(0, '5',  t+1.5, 0.5)
            note(1, '5',  t+2.0, 0.5)
            note(1, '5',  t+2.5, 0.25)
            note(1, '6',  t+2.75, 0.25)
            note(1, '5',  t+3.0, 0.5)
            note(1, '4#',  t+3.5, 0.5)
            note(1, '5',  t+4.0, 0.5)
            note(0, '5',  t+4.5, 0.5)
            note(1, '2',  t+5.0, 0.5)
            note(0, '5',  t+5.5, 0.5)
            note(1, '5',  t+6.0, 0.5)
            note(1, '5',  t+6.5, 0.25)
            note(1, '6',  t+6.75, 0.25)
            note(1, '5',  t+7.0, 0.5)
            note(1, '4#',  t+7.5, 0.5)

            t += 8.0
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 1)
            note(-2, '5', t+3.0, 1)
            note(-1, '2', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '2', t+6.0, 2)

            note(1, '5',  t+0.0, 0.5)
            note(1, '6',  t+0.5, 0.5)
            note(2, '0#',  t+1.0, 0.5)
            note(2, '1',  t+1.5, 0.5)
            note(2, '2',  t+2.0, 0.5)
            note(2, '0#',  t+2.5, 0.5)
            note(1, '6',  t+3.0, 0.5)
            note(1, '5',  t+3.5, 0.5)
            note(1, '4#',  t+4.0, 1)
            note(0, '6',  t+5.0, 1)
            note(0, '4#',  t+6.0, 1)
            note(0, '2',  t+7.0, 1)

            # END PART...
            t += 8
            tact(t)

            note(0, '5', t-0.4, 0.4)
            note(1, '0#', t-0.2, 0.4)

            note(-1, '3#', t+0.0, 4)
            note(0, '0#', t+0.0, 4)
            note(-1, '3#', t+4.0, 1)
            note(0, '1', t+5.0, 1)
            note(0, '3#', t+6.0, 1)
            note(-1, '3#', t+7.0, 1)

            note(1, '5',  t+0.0, 1)
            note(1, '4#',  t+1.0, 1)
            note(1, '5',  t+2.0, 1)
            note(1, '4#',  t+3.0, 1)
            note(1, '5',  t+4.0, 1)
            note(1, '0#',  t+4.0, 1)
            note(1, '2',  t+5.0, 1)
            note(1, '5',  t+6.0, 1)
            note(1, '1',  t+7.0, 1)

            t += 8
            tact(t)

            note(-1, '2', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '5', t+2.0, 2)
            note(0, '2', t+4.0, 4)
            note(0, '4#', t+4.0, 4)

            note(1, '0#',  t+0.0, 1)
            note(1, '1',  t+1.0, 1)
            note(1, '2',  t+2.0, 1)
            note(1, '0#',  t+3.0, 1)
            note(0, '6',  t+4.0, 2)

            note(0, '5',  t+4.0, 1)
            note(0, '4#',  t+4.0, 1)

            t += 8
            tact(t)

            note(-2, '2', t+0.0, 1)
            note(-1, '0#', t+1.0, 3)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 2)

            note(0, '0#',  t+0.0, 2)
            note(0, '2',  t+0.2, 1.8)
            note(0, '5',  t+0.4, 1.6)
            note(0, '2',  t+2.0, 1)
            note(0, '5',  t+3.0, 0.5)
            note(0, '6',  t+3.5, 0.5)
            note(1, '0#',  t+4.0, 1)
            note(0, '2',  t+5.0, 1)
            note(0, '5',  t+6.0, 1)
            note(1, '0#',  t+7.0, 0.5)
            note(1, '1',  t+7.5, 0.5)

            t += 8
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 2)
            note(-1, '2', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '4#', t+6.0, 2)

            note(1, '2',  t+0.0, 1)
            note(0, '2',  t+1.0, 1)
            note(1, '0#',  t+2.0, 1)
            note(1, '1',  t+3.0, 0.5)
            note(1, '0#',  t+3.5, 0.5)
            note(0, '6',  t+4.0, 3)

            t += 8
            tact(t)

            note(0, '5', t-1.0, 0.5)
            note(1, '0#', t-0.5, 0.5)

            note(-1, '3#', t+0.0, 1)
            note(0, '0#', t+1.0, 1)
            note(0, '3#', t+2.0, 2)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '2', t+6.0, 1)
            note(-1, '1', t+7.0, 1)

            note(1, '5',  t+0.0, 1)
            note(1, '4#',  t+1.0, 1)
            note(1, '5',  t+2.0, 1)
            note(1, '4#',  t+3.0, 1)
            note(1, '0#',  t+4.0, 2)
            note(1, '2',  t+4.2, 0.8)
            note(1, '5',  t+4.4, 1.6)
            note(1, '2',  t+5.0, 1)
            note(1, '5',  t+6.0, 1)
            note(1, '1',  t+7.0, 0.8)

            t += 8
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 2)
            note(-1, '2', t+4.0, 1)
            note(-1, '6', t+5.0, 1)
            note(0, '4#', t+6.0, 2)

            note(0, '6',  t-0.2, 0.4)
            note(1, '0#',  t+0.2, 0.8)
            note(1, '1',  t+1.0, 1)
            note(1, '2',  t+2.0, 1)
            note(2, '0#',  t+3.0, 1)
            note(1, '6',  t+4.0, 3)
            note(1, '2',  t+4.0, 3)

            t += 8
            tact(t)

            note(0, '5', t-1.0, 0.5)
            note(0, '4#', t-0.5, 0.5)

            note(-2, '3#', t+0.0, 1)
            note(-1, '0#', t+1.0, 1)
            note(-1, '3#', t+2.0, 2)
            note(-1, '1', t+4.0, 1)
            note(-1, '5', t+5.0, 1)
            note(0, '1', t+6.0, 2)

            note(0, '5',  t+0.0, 3)
            note(0, '2',  t+0.0, 3)
            note(0, '5',  t+3.0, 0.5)
            note(0, '6',  t+3.5, 0.5)
            note(1, '0#',  t+4.0, 1)
            note(0, '2',  t+5.0, 1)
            note(0, '5',  t+6.0, 1)
            note(1, '0#',  t+7.0, 0.5)
            note(1, '1',  t+7.5, 0.5)

            t += 8
            tact(t)

            note(-2, '5', t+0.0, 1)
            note(-1, '2', t+1.0, 1)
            note(0, '0#', t+2.0, 2)
            note(-2, '2', t+4.0, 1)
            note(-2, '6', t+5.0, 1)
            note(-1, '4#', t+6.0, 2)

            note(1, '2',  t+0.0, 1)
            note(0, '2',  t+1.0, 1)
            note(0, '5',  t+2.0, 1)
            note(1, '1',  t+3.0, 0.5)
            note(1, '0#',  t+3.5, 0.5)
            note(0, '6',  t+4.0, 2)
            note(0, '2',  t+6.0, 2)

            # last tact
            t += 8
            tact(t)

            note(-2, '3#', t+0.0, 1)
            note(-1, '0#', t+1.0, 1)
            note(-1, '3#', t+2.0, 2+8)

            note(0, '5',  t+0.0, 1)
            note(-1, '5',  t+1.0, 1)
            note(0, '0#',  t+2.0, 1)
            note(0, '3#',  t+3.0, 1)
            note(0, '5',  t+4.0, 8)

        def whispers():
            # configure tools:
            self.configs.kernel.tools.clear()
            self.configs.kernel.tools.append(SynthesizerTool(name="Electro_Soprano", code="""
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
            """.replace(" " * 12, "")))
            self.configs.kernel.tools.append(SynthesizerTool(name="Violin", code="""
                    float freq[] = {
                        0.2,
                        0.6,
                        0.05,
                        0.8,
                        0.05,
                        0.025,
                        0.0125,
                        0.5,
                        0.0,
                        0.026,
                        0.0,
                        0.1,
                        0.0,
                        0.015,
                        0.0,
                        0.4,
                    };
                    float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
                    v *= fmax(0.01f, k);
                    
                    float res = 0.0, dr;
                    for (int fqid = 0; fqid < sizeof(freq) / sizeof(*freq); ++fqid)
                    {
                        float f = note->frequency * (fqid + 1) * 0.25;
                        float fv = freq[fqid];
                        dr = sin(s * f / 44100.0f * 0.5 * 3.1415926 * 2.0);
                        res += fv*v*dr;
                    }
                    return res;
            """.replace(" " * 12, "")))
            self.configs.kernel.tools.append(SynthesizerTool(name="Alto", code="""
                    float freq[] = {
                        0.25,
                        0.4,
                        0.05,
                        0.6,
                        0.05,
                        0.25,
                        0.15,
                        0.8,
                        0.015,
                        0.005,
                        0.015,
                        0.3,
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
                        res += fv*v*(smoothstep(-0.3, 0.3, dr)*2.0-1.0);
                    }
                    return res;
            """.replace(" " * 12, "")))
            self.configs.kernel.tools.append(SynthesizerTool(name="Cello", code="""
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
                        res += fv*v*(smoothstep(-0.2, 0.2, dr)*2.0-1.0);
                    }
                    return res;
            """.replace(" " * 12, "")))
            self.configs.kernel.tools.append(SynthesizerTool(name="Bass", code="""
                    float freq[] = {
                        0.2,
                        0.5,
                        0.05,
                        1.0,
                        0.05,
                        0.025,
                        0.0125,
                        0.3,
                    };
                    float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
                    v *= fmax(0.01f, k);
                    
                    float res = 0.0, dr;
                    for (int fqid = 0; fqid < sizeof(freq) / sizeof(*freq); ++fqid)
                    {
                        float f = note->frequency * (fqid + 1) * 0.25;
                        float fv = freq[fqid];
                        dr = sin(s * f / 44100.0f * 0.5 * 3.1415926 * 2.0);
                        res += fv*v*(smoothstep(-0.1, 0.1, dr) * 2.0 - 1.0);
                    }
                    return res;
            """.replace(" " * 12, "")))
            self.configs.kernel.tools.append(SynthesizerTool(name="Drum", code="""
                float dr;
                float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
                v *= fmax(0.01f, k);
                return v * rnd;
            """.replace(" " * 12, "")))

            self.configs.kernel.tools[0].configs.legato_mod = 2.0
            self.configs.kernel.tools[1].configs.legato_mod = 1.5
            self.configs.kernel.tools[2].configs.legato_mod = 3.0
            self.configs.kernel.tools[3].configs.legato_mod = 3.0
            self.configs.kernel.tools[4].configs.legato_mod = 3.0
            self.configs.kernel.tools[5].configs.legato_mod = 0.5

            self.configs.kernel.tools[0].configs.volume = 0.2
            self.configs.kernel.tools[1].configs.volume = 0.2
            self.configs.kernel.tools[2].configs.volume = 0.12
            self.configs.kernel.tools[3].configs.volume = 0.1
            self.configs.kernel.tools[4].configs.volume = 0.07
            self.configs.kernel.tools[5].configs.volume = 0.2


            t = 0
            ddt = 16   #   4/4
            time_speed = 0.2


            #    DO   DO#    RE   RE#   MI   FA   FA#   SO   SO#  LA   LA#    SI
            r = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
            def tone2(x):
                if x == "F":
                    return "F#"
                if x == "C":
                    return "C#"
                return x

            def mytact(s):
                nonlocal t
                # for all lines
                self.tacts.append(SynthesizerProjectTact(t))
                prev_num = -1
                vapp = [1.0] * len(self.configs.kernel.tools)
                for line in map(str.strip, s.split('\n')):
                    if line and line.startswith("volume"):
                        vapp = eval("(" + line[line.find('=')+1:] + ")")
                    if line and line[0].isdigit():
                        # get instrument id [num]
                        num, content = line.split('.', 1)
                        num = int(num)
                        if num < prev_num:
                            t += ddt # new tact
                            self.tacts.append(SynthesizerProjectTact(t))
                        prev_num = num

                        tt = t
                        # add all notes
                        prev_len, prev_volume = 1.0, 1.0
                        for note in content.split():
                            vv = vapp[num]
                            if note[-1] == '*':
                                vv *= 1.5
                                note = note[:-1]
                            elif note[-1] == 'v':
                                vv *= 0.5
                                note = note[:-1]
                            elif note[-1] == '-':
                                tt -= prev_len
                                note = note[:-1]
                            # parse note
                            a = note.split('/')
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
                            while k < len(f) and f[k].isalpha():
                                k += 1
                            nt = f[:k]
                            nt = tone2(nt)
                            nt = r.index(nt)
                            z = int(f[k:]) - 4
                            fq = 523.25 * pow(2, z + nt / 12)
                            add(tt * time_speed, fq, l * time_speed, v*vv, num)
                            prev_len, prev_volume = l, v
                            tt += l
                t += ddt

            with open("track/whispers", "r") as f:
                txt = f.read()
            mytact(txt)

        what = 'w'
        if what == 't':
            tact()
            lm = 1.25
            tsoy()
        elif what == 'm':
            tact()
            lm = 2.0
            metal1()
        elif what == 'r':
            tact()
            lm = 4.0
            river()
        else: # 'w'
            whispers()

        return

    def compile(self):
        if self.d.music.track is not None:
            self.d.music.playing = False
            self.d.music.track.stop()
        used_time = -time.time()
        self.log("compilation start...", c.log.info)
        self.draw()
        sc.refresh()
        # generate tones
        self.x.inputs.clear()
        for i in self.tacts:
            for note in i.notes:
                if not self.configs.kernel.tools[note.tool].configs.mute:
                    volume_pitch = self.configs.kernel.tools[note.tool].configs.volume
                    legato_mod = self.configs.kernel.tools[note.tool].configs.legato_mod
                    self.x.add(GeneratorTone(note.tool, note.time, note.length * legato_mod, note.volume * volume_pitch, note.frequency))
        if not self.x.inputs:
            self.log("Error: Empty notes (or all tools are muted.) Nothing to compile", c.log.error)
            return
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
        raw = self.x.compile()
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
        return

    def resize(self):
        self.h, self.w = sc.getmaxyx()
        self.log_w = self.w // 2
        self.hl = min(15, max(7, self.w // 5))
        self.ht = self.h - self.hl

    def run(self):

        self.d = jsd(
            mode="view",
            log = [],
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
                    recalculate_cy=False,
                )
            )
        )
        self.configs = jsd(
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
            float dr;
            //float v = note->volume, k = 1.0f - (float)(s - note->start) / 44100.0f;//(float)(note->end - note->start);
            float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
            v *= fmax(0.01f, k);
            dr = sin(s * note->frequency / 44100.0f * 0.5 * 3.1415926 * 2.0);
            return v*(smoothstep(-0.3, 0.3, dr)*2.0-1.0);
        """.replace(" "*8,"")))
        self.configs.kernel.tools.append(SynthesizerTool(name="Drum", code="""
            float dr;
            float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
            v *= fmax(0.01f, k);
            return v * rnd;
        """.replace(" "*8,"")))
        self.tacts = []
        self.resize()

        # INIT?

        tt = choice('rtm')
        self.configs.kernel.tools[0].configs.legato_mod = {'t': 1.25, 'm': 2.0, 'r': 4.0}[tt]
        self.configs.kernel.tools[1].configs.legato_mod = {'t': 1.25, 'm': 2.0, 'r': 4.0}[tt]
        self.create(tt,dt=0.25*1.5)
        self.log("created music: " + tt, c.log.info)

        while True:
            self.resize()
            self.draw()
            if not self.events():
                return
