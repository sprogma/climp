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
    def __init__(self, time, length, volume, frequency):
        self.time = time
        self.length = length
        self.volume = volume
        self.frequency = frequency

class Generator:
    def __init__(self, api_function):
        self.api_function = api_function
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
        input_times = np.zeros(input_len, dtype="float32")
        input_lengths = np.zeros(input_len, dtype="float32")
        input_frequencies = np.zeros(input_len, dtype="float32")
        input_volumes = np.zeros(input_len, dtype="float32")

        # set
        for n, i in enumerate(self.inputs):
            input_times[n] = self.inputs[n].time
            input_lengths[n] = self.inputs[n].length
            input_frequencies[n] = self.inputs[n].frequency
            input_volumes[n] = self.inputs[n].volume

        # call
        self.api_function(result, result_length, input_times, input_lengths, input_frequencies, input_volumes, input_len)

        # return
        return result


class ProjectNote:
    def __init__(self, instrument, frequency, time, length, volume=1.0):
        self.instrument = instrument
        self.freq = frequency
        self.time = time
        self.length = length
        self.volume = volume


class ProjectToneTemplateItem:
    def __init__(self, frequency, time_start, length, volume):
        self.freq = frequency
        self.time = time_start
        self.length = length
        self.volume = volume


class ProjectToneTemplate:
    def __init__(self, iterable: []):
        self.tones : [ProjectToneTemplateItem] = iterable

    def to_notes(self, tone):
        notes = []
        for i in self.tones:
            notes.append(ProjectNote(
                tone.instrument,
                tone.freq * i.freq.multiply + i.freq.shift,
                tone.time + tone.l * i.time.multiply + i.time.shift,
                tone.length * i.length.multiply + i.length.shift,
                tone.volume * i.volume.multiply + i.volume.shift,
            ))
        return notes


class ProjectTone:
    def __init__(self, instrument, tone_template, time, length, frequency=440.0, volume=1.0):
        self.template = tone_template
        self.time = time
        self.length = length
        self.instrument = instrument
        self.freq = frequency
        self.volume = volume


class TrackProject:
    def __init__(self, api_function):
        self.x = Generator(api_function)
        self.rw, self.lw = 0, 0
        self.w, self.h = 0, 0
        self.d = jsd()
        self.tones = [[], [], [], [], [], [], [], []]  # tones
        self.temps = []  # tone templates

    def draw(self):
        sc.clear()
        self.draw_tones()

    def correct_camera_to_tone(self, tone, tone_id, tone_chanel):
        rows = int(tone.time / self.d.visual.time_per_line) * (self.d.visual.chanels + 1) + tone_chanel

        # correct cy
        self.d.visual.cy = max(self.d.visual.cy, rows - (self.h - 10))
        self.d.visual.cy = min(self.d.visual.cy, rows - 10)

    def draw_tones(self):
        for chanel in self.tones:
            chanel.sort(key=lambda x: x.time)
        self.d.visual.draw_time = (pygame.time.get_ticks() - self.d.time_start) / 1000.0

        def draw_tone(tone, tone_id, tone_chanel, selected=False):
            ttime = tone.time
            ltime = tone.length
            # for each symbol
            rows = int(ttime / self.d.visual.time_per_line)
            ttime -= rows * self.d.visual.time_per_line
            while ltime > 0.00001: # ! eps*10
                block_len = ltime
                if ltime - 0.000001 > self.d.visual.time_per_line - ttime:
                    block_len = self.d.visual.time_per_line - ttime
                w_block_len = block_len / self.d.visual.time_per_line * self.rw

                if block_len > 0.000001: # if is not strange block
                    # draw tone line
                    xpos = ttime / self.d.visual.time_per_line * self.rw
                    llen = int(xpos + w_block_len + 0.5) - int(xpos + 0.5)
                    ll = f'{tone.template:{llen}}'
                    if len(ll) > llen:
                        ll = ll[:llen - 1] + '>'
                    int_xpos = int(xpos + 0.5)
                    addstr(
                        rows * (self.d.visual.chanels + 1) + tone_chanel - self.d.visual.cy,
                        self.lw + int_xpos,
                        ll,
                        c.gen.note.selected
                        if selected else
                        (c.gen.note.a if tone_id % 2 == 0 else c.gen.note.b)
                    )

                # next line
                ttime += block_len
                ltime -= block_len
                if ttime + 0.000001 > self.d.visual.time_per_line:
                    ttime -= self.d.visual.time_per_line
                    rows += 1

        def draw_time():
            t = self.d.visual.draw_time
            rows = int(t / self.d.visual.time_per_line)
            xpos = int((t - rows * self.d.visual.time_per_line) / self.d.visual.time_per_line * self.rw + 0.5)
            for i in range(self.d.visual.chanels):
                y = rows * (self.d.visual.chanels + 1) + i - self.d.visual.cy
                x = xpos
                if 0 <= x < self.rw and 0 <= y < self.h:
                    sc.chgat(y, self.lw + x, 1, curses.color_pair(c.gen.timeline))

        #draw lines

        for chanel_id, chanel in enumerate(self.tones):
            for i, tone in enumerate(chanel):
                draw_tone(tone, i, chanel_id)

        for i in range(0, self.h):
            if (i + self.d.visual.cy) % (self.d.visual.chanels + 1) == self.d.visual.chanels:
                addstr(i, self.lw, '_' * self.rw, c.gen.text)

        # draw selection
        draw_tone(self.tones[self.d.visual.selection.chanel][self.d.visual.selection.position],
                  self.d.visual.selection.position,
                  self.d.visual.selection.chanel, selected=True)

        # draw time
        draw_time()

    def move_selection_mod(self, direction):
        def get_x_dist(x1, x2, y1, y2):
            if y1 <= x1 <= y2 or y1 <= x2 <= y2 or x1 <= y1 <= x2 or x1 <= y2 <= x2:
                return -(min(x2, y2) - max(x1, y1)) * 0.001
            return min(abs(x1 - y1), abs(x2 - y2))
        selected_tone = self.tones[self.d.visual.selection.chanel][self.d.visual.selection.position]
        rows = int(selected_tone.time / self.d.visual.time_per_line)
        xpos = int((selected_tone.time - rows * self.d.visual.time_per_line) / self.d.visual.time_per_line * self.rw)
        xendpos = int((selected_tone.time + selected_tone.length - rows * self.d.visual.time_per_line) / self.d.visual.time_per_line * self.rw)
        rows = rows * (self.d.visual.chanels + 1) + self.d.visual.selection.chanel
        mind = float('inf')
        sel = None
        for chanel_id, chanel in enumerate(self.tones):
            for i, tone in enumerate(chanel):
                tone_rows = int(tone.time / self.d.visual.time_per_line)
                tone_xpos = int((tone.time - tone_rows * self.d.visual.time_per_line) / self.d.visual.time_per_line * self.rw)
                tone_xendpos = int((tone.time + tone.length - tone_rows * self.d.visual.time_per_line) / self.d.visual.time_per_line * self.rw)
                tone_rows = tone_rows * (self.d.visual.chanels + 1) + chanel_id
                xdist = get_x_dist(xpos, xendpos, tone_xpos, tone_xendpos)
                if xdist < 2 * abs(rows - tone_rows):
                    if (direction == -1 and tone_rows < rows) or \
                       (direction ==  1 and tone_rows > rows):
                        d = abs(rows - tone_rows) + xdist
                        if d < mind:
                            mind = d
                            sel = chanel_id, i
        if sel is not None:
            self.d.visual.selection.chanel = sel[0]
            self.d.visual.selection.position = sel[1]

    def events(self):
        key = 0
        while key != -1:
            key = sc.getch()
            if key == -1:
                break
            if key == curses.KEY_RESIZE:
                curses.resize_term(*sc.getmaxyx())
                sc.clear()
                sc.refresh()
            if key == curses.KEY_UP:
                self.move_selection_mod(-1)
                self.correct_camera_to_tone(self.tones[self.d.visual.selection.chanel][self.d.visual.selection.position],
                                            self.d.visual.selection.position,
                                            self.d.visual.selection.chanel)
            if key == curses.KEY_DOWN:
                self.move_selection_mod(1)
                self.correct_camera_to_tone(self.tones[self.d.visual.selection.chanel][self.d.visual.selection.position],
                                            self.d.visual.selection.position,
                                            self.d.visual.selection.chanel)
            if key == curses.KEY_RIGHT:
                self.d.visual.selection.position += 1
                if self.d.visual.selection.position >= len(self.tones[self.d.visual.selection.chanel]):
                    self.d.visual.selection.position = len(self.tones[self.d.visual.selection.chanel]) - 1
                self.correct_camera_to_tone(self.tones[self.d.visual.selection.chanel][self.d.visual.selection.position],
                                            self.d.visual.selection.position,
                                            self.d.visual.selection.chanel)
            if key == curses.KEY_LEFT:
                self.d.visual.selection.position -= 1
                if self.d.visual.selection.position < 0:
                    self.d.visual.selection.position = 0
                self.correct_camera_to_tone(self.tones[self.d.visual.selection.chanel][self.d.visual.selection.position],
                                            self.d.visual.selection.position,
                                            self.d.visual.selection.chanel)

    def create(self, what, dt=0.25):
        lm = 1
        fqcorr = 0.5

        MODE_LINEAR = 0
        MODE_NOISE = 1

        sndvlm = []
        sndvlm.append([1.0, 1.0])
        for i in range(1):
            sndvlm.append([2**i, 1.0/(i+1.0) + 0.5])
        for i in range(3):
            sndvlm.append([1/(2**i), 1.0/(i + 2.0) + 1.0])

        v = 0.5
        sss = sum(map(lambda x: x[1], sndvlm))
        sndvlm = list(map(lambda x: (x[0], v * x[1] / sss), sndvlm))

        print(sndvlm)

        z = [0]*100
        for i in sndvlm:
            z[int(math.log(i[0]+0.01, 2.0)*4.0 + 50)] += i[1] * 100000
        for p, i in enumerate(z):
            f = pow(2.0, (p-50)/4)
            print(f'{f:20.10f}', '#' * int(math.log(i + 0.1, 2.0)))


        def addcc(t, fq, l=1.0, volume=1.0):
            for ffq, v in sndvlm:
                f = fq * ffq
                v *= volume
                #self.x.add_note([t * dt, f, v, t * dt + dt * l * lm, f, 0], 1, MODE_LINEAR)
                self.x.add(GeneratorTone(t*dt, dt*l*lm,v,f))
            return t + l
            for i in range(28):
                f = fq * (i + 1) / 2.0
                v = volume * 4/28
                if i not in (1, 2, 4, 8, 16, 32):
                    v /= 1.1 ** i
                #self.x.add_note([t * dt, f, v, t * dt + dt * l * lm, f, 0], 1, MODE_LINEAR)
                self.x.add(GeneratorTone(t*dt, dt*l*lm,v,f))
            return t + l

        def add(t, fq, l=1.0, volume=1.0):
            self.tones[randint(0, 6)].append(ProjectTone(None, str(fq), t * dt, l * dt))
            return addcc(t, fq, l, volume)

        def addc(t, ch, l=1):
            for cc, i in enumerate(sorted(ch)):
                ovh = l * 0.05 * cc
                addcc(t + ovh, i, l - ovh, volume=2.0 / len(ch))
            self.tones[randint(0, 6)].append(ProjectTone(None, "ch"+str(ch[0]), t * dt, l * dt))
            return t + l

        def mx(fq, oct):
            return fq * pow(2.0, oct + 1)

        def bt(t, l=1):
            #for i in range(42):
            #    f = 5550 + i * 116.1251261261261
            #self.x.add_note([t * dt, 0.0, 1.0, t * dt + dt * l * lm * 0.5, 0.0, 0], 1, MODE_NOISE)
            #self.x.add(GeneratorTone(t*dt, dt*l*lm*0.5,5.0,112525951259179.12512951251))
            self.tones[7].append(ProjectTone(None, '###', t * dt, l * dt))
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
                    add(et, mx(A, 1), l=1.5)
                    et += 0.025
                    add(et, mx(F, 1), l=1.5)
                    et += 0.025
                    add(et, mx(C, 1), l=1.5)
                    et += 0.025
                    add(et, mx(A, 0), l=1.5)
                    et += 0.025
                    add(et, mx(D, 0), l=1.5)

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
            ddt = 1.5
            def note(z, x, t, l):
                add(t * ddt, 523.25 * pow(2, z + r.index(x) / 12), l * ddt, 1.0)

            t = 0

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

            note(-2, '3#', t+0.0, 1)
            note(-1, '0#', t+1.0, 1)
            note(-1, '3#', t+2.0, 2+8)

            note(0, '5',  t+0.0, 1)
            note(-1, '5',  t+1.0, 1)
            note(0, '0#',  t+2.0, 1)
            note(0, '3#',  t+3.0, 1)
            note(0, '5',  t+4.0, 8)


        if what == 't':
            lm = 1.0
            tsoy()
        elif what == 'm':
            lm = 2.0
            metal1()
        else: # 'r'
            lm = 4.0
            river()

        return

    def compile(self):
        print(f'{self.x.freq.len} notes...\n')
        self.x.compile()
        #self.x.sound.play(1)
        print('result length = ', self.x.raw.shape[0] / self.x.mixer.frequency, 's')
        print('ok')

    def resize(self):
        self.h, self.w = sc.getmaxyx()

        self.lw = max(20, self.w // 5)
        self.rw = self.w - self.lw

    def run(self):

        self.d = jsd(
            visual=jsd(
                cy=-1,
                chanels=8,
                time_per_line=4.0,
                scroll_step=3,
                draw_time=0.0,
                selection=jsd( # multiple selection is not implemented
                    chanel=2,
                    position=5,
                )
            ),
            time_start=0
        )
        self.tones = [[] for x in range(self.d.visual.chanels)]

        self.create('m', dt=0.5)
        self.compile()
        self.x.sound.play()
        self.d.time_start = pygame.time.get_ticks()

        #self.tones.append(ProjectTone(None, 'C#', 0, 0.0, 1.0, 440.0))
        #self.tones.append(ProjectTone(None, 'A#', 0, 1.0, 1.0, 440.0))
        #self.tones.append(ProjectTone(None, 'Am', 1, 2.0, 1.0, 440.0))
        #self.tones.append(ProjectTone(None, 'A', 0, 2.0, 2.0, 440.0))
        #self.tones.append(ProjectTone(None, 'Am', 1, 4.0, 3.0, 440.0))
        #self.tones.append(ProjectTone(None, 'C', 0, 5.0, 1.0, 440.0))
        #self.tones.append(ProjectTone(None, 'Em', 0, 6.0, 2.0, 440.0))

        while True:
            self.resize()
            self.draw()
            self.events()





climplib = ctypes.cdll.LoadLibrary(r"D:\C\git\climp\bin\Windows\climp.dll")  # './bin/Windows/climp.dll'
climplib.kernel.argtypes = [
    np.ctypeslib.ndpointer(dtype=np.float32, ndim=1, flags='C_CONTIGUOUS'),  # res
    ctypes.c_size_t,
    np.ctypeslib.ndpointer(dtype=np.float32, ndim=1, flags='C_CONTIGUOUS'),  # notes
    np.ctypeslib.ndpointer(dtype=np.float32, ndim=1, flags='C_CONTIGUOUS'),  # notes
    np.ctypeslib.ndpointer(dtype=np.float32, ndim=1, flags='C_CONTIGUOUS'),  # notes
    np.ctypeslib.ndpointer(dtype=np.float32, ndim=1, flags='C_CONTIGUOUS'),  # notes
    ctypes.c_size_t,
]
climplib.kernel.restype = ctypes.c_int



c = TrackProject(climplib.kernel)
c.create('r')

t = -time.time()
raw = c.x.compile()
t += time.time()
print(f"Used Time: {t}s.")

raw = np.tanh(raw)
raw *= 32767.0
raw = raw.astype(dtype=np.int16)
raw = np.column_stack((raw, raw))
# export sound
raw = raw.copy(order='C')

pygame.init()

sound = pygame.sndarray.make_sound(raw)
sound.play()
while 1:
    ...