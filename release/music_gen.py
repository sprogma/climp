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


class SynthesizerProjectTone:
    def __init__(self, instrument, frequency, time, length, volume, group):
        self.instrument = instrument
        self.frequency = frequency
        self.time = time
        self.length = length
        self.volume = volume
        # meta
        self.group = group


class SynthesizerProjectTact:
    def __init__(self, time):
        self.time = time
        self.notes: [SynthesizerProjectTone] = []

    @property
    def length(self):
        cnt = defaultdict(int)
        for i in self.notes:
            cnt[i.group] += 1
        return max(cnt.values(), default=0) + 2 # 2 - fictive notes (in start and in the end)


class SynthesizerTool:
    def __init__(self, name, code=""):
        self.name = name
        self.code = code


class SynthesizerProject:
    def __init__(self, api_function):
        self.x = Generator(api_function)
        self.rw, self.lw = 0, 0
        self.w, self.h = 0, 0
        self.d = jsd()
        self.configs = jsd()
        self.tacts: [SynthesizerProjectTact] = []

    def draw(self):
        sc.clear()
        self.tacts.sort(key=lambda x: x.time or -1)
        self.d.draw_time = (pygame.time.get_ticks() - self.d.time_start) / 1000.0
        self.draw_tacts()

    def draw_tacts(self):
        line_height = 1+self.d.max_groups*2
        line_width = 5

        mus_y = math.inf
        x, y = 0, -self.d.visual.cy
        for i in self.tacts:
            nx, ny = (x + i.length * line_width) % self.w, y + (x + i.length * line_width) // self.w * line_height
            # if visible
            if y <= -line_height <= ny or y <= self.h+line_height <= ny or -line_height <= y <= self.h+line_height:
                cnt = defaultdict(int)
                # draw notes
                for note in i.notes:
                    cnt[note.group] += 1
                    px, py = (x + cnt[note.group] * line_width) % self.w, y + (x + cnt[note.group] * line_width) // self.w * line_height
                    is_playing = self.d.draw_time > note.time and (self.d.draw_time - note.time) < note.length
                    dy = note.group * 2 + 1
                    addstr(py+dy, px, '|' + str(int(note.frequency)), 2 if is_playing else 0)
                # /draw notes
            # [get playing...]
            for cnt, note in enumerate(i.notes, 1):
                px, py = (x + cnt * line_width) % self.w, y + (x + cnt * line_width) // self.w * line_height
                if self.d.draw_time > note.time and (self.d.draw_time - note.time) < note.length:
                    mus_y = min(mus_y, py+self.d.visual.cy)
            # move to next note
            x, y = nx, ny
            if self.w - x < self.w // 2:
                y += line_height
                x = 0
        if self.d.visual.follow_music and mus_y != math.inf:
            if self.d.visual.cy < mus_y - self.h * 2 // 3:
                self.d.visual.cy = mus_y - self.h // 3

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
                self.d.visual.cy -= 1
            if key == curses.KEY_DOWN:
                self.d.visual.cy += 1

    def create(self, what, dt=0.25, X=False):
        lm = 1
        fqcorr = 0.5

        MODE_LINEAR = 0
        MODE_NOISE = 1

        sndvlm = [
            [4.0, 0.3],
            [3.0, 0.05],
            [2.0, 0.5],
            [1.0, 1.0],
            [0.5, 1.0],
            #[0.25, 1.0],
            #[0.125, 3.0]
        ]
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

        if X:
            sndvlm = [
                0.1,
                0.03,
                0.003,
                0.07,
                0.004,
                0.02,
                0.027,
                0.013,
                0.008,
                0.0079,
                0.0076,
                0.0075,
                0.0005,
                0.004
            ]

        def tact(time=None):
            self.tacts.append(SynthesizerProjectTact(time))

        def addcc(t, fq, l=1.0, volume=1.0):
            EPS = 0.001
            ar = [0.5 * i for i in range(16)]
            ar2 = [1.0 * i for i in range(16)]
            if self.tacts[-1].time is not None:
                nt = self.tacts[-1].time
                if any(map(lambda x: abs(x - (t - nt)) < EPS, ar)):
                    if any(map(lambda x: abs(x - (t - nt)) < EPS, ar2)):
                        ...
                    else:
                        volume *= 0.9
                else:
                    volume *= 0.8
            if X:
                for i in range(len(sndvlm)):
                    f = fq * (i + 1) * fqcorr
                    v = sndvlm[i]*volume
                    self.x.add(GeneratorTone(t * dt, dt*l*lm, v * 0.4 / 2.0 ** i, f))
                for i in range(3):
                    f = fq / 2 ** i
                    v = 0.3*volume
                    self.x.add(GeneratorTone(t * dt, dt*l*lm, v * 0.4 / 2.0 ** i, f))
                return t + l
            for ffq, v in sndvlm:
                f = fq * ffq
                v *= volume
                #self.x.add_note([t * dt, f, v, t * dt + dt * l * lm, f, 0], 1, MODE_LINEAR)
                self.x.add(GeneratorTone(t*dt, dt*l*lm,v,f))
            return t + l

        def add(t, fq, l=1.0, volume=1.0, group=0):
            if what == 'm' and fq <= 300:
                group = 1
            self.tacts[-1].notes.append(SynthesizerProjectTone(0, fq, t*dt, l*dt, volume, group))
            return addcc(t, fq, l, volume)

        def addc(t, ch, l=1):
            for cc, i in enumerate(sorted(ch)):
                ovh = l * 0.05 * cc
                add(t + ovh, i, l - ovh, volume=2.0 / len(ch))
            return t + l

        def mx(fq, oct):
            return fq * pow(2.0, oct + 1)

        def bt(t, l=1):
            #for i in range(42):
            #    f = 5550 + i * 116.1251261261261
            #self.x.add_note([t * dt, 0.0, 1.0, t * dt + dt * l * lm * 0.5, 0.0, 0], 1, MODE_NOISE)
            #self.x.add(GeneratorTone(t*dt, dt*l*lm*0.5,5.0,112525951259179.12512951251))
            v = 1.0
            self.tacts[-1].notes.append(SynthesizerProjectTone(0, -1.0, t*dt, dt*l*lm*0.5, v, 1))
            self.x.add(GeneratorTone(t*dt, dt*l*lm*0.5,v,-1.0))
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


        tact()
        if what == 't':
            lm = 1.25
            tsoy()
        elif what == 'm':
            lm = 2.0
            metal1()
        else: # 'r'
            lm = 4.0
            river()

        return

    def compile(self):
        # generate kernel code
        with open("source/kernel_template.cl") as file:
            code = file.read()
        # create kernel:
        function_code = ""
        switch_code = ""
        # generate code
        switch_code += ""
        for id, t in enumerate(self.configs.kernel.tools):
            switch_code += f"case {id}: res += {t.name}(s, notes + n, rnd); break;"
            function_code += f"float {t.name}(float s, struct note *note, float rnd){{ {t.code} }}"
        # insert before kernel all
        code = code.replace("<TOOLS_FUNCTION>", function_code)
        code = code.replace("<TOOLS_SWITCH>", switch_code)
        with open("source/kernel.cl", "w") as file:
            file.write(code)
        print(code)
        print(f'{len(self.tacts)} notes...\n')
        raw = self.x.compile()
        print('ok')
        return raw

    def resize(self):
        self.h, self.w = sc.getmaxyx()

        self.lw = max(20, self.w // 5)
        self.rw = self.w - self.lw

    def run(self):

        self.d = jsd(
            mode="view",
            draw_time=0.0,
            time_start=0,
            visual=jsd(
                cy=0,
                follow_music=True,
                follow_music_time=0,
                selection=jsd(
                    pos=None,
                )
            ),
            max_groups=2
        )
        self.configs = jsd(
            kernel=jsd(
                tools=[]
            ),
        )
        self.configs.kernel.tools.append(SynthesizerTool(name="Piano", code="""
            float dr;
            if (note->frequency > 0)
            {
                //float v = note->volume, k = 1.0f - (float)(s - note->start) / 44100.0f;//(float)(note->end - note->start);
                float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
                v *= fmax(0.01f, k);
                dr = sin(s * note->frequency / 44100.0f * 0.5 * 3.1415926 * 2.0);
                return v*(smoothstep(-0.3, 0.3, dr)*2.0-1.0);
            }
            else
            {
                float v = note->volume, k = 1.0f - (float)(s - note->start) / (float)(note->end - note->start);
                v *= fmax(0.01f, k);
                return v * rnd;
            }"""))
        self.tacts = []
        self.create(choice('rtm'),dt=0.25*1.5)
        t = -time.time()
        raw = self.compile()
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
        self.d.time_start = pygame.time.get_ticks()

        while True:
            self.resize()
            self.draw()
            self.events()
