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
    def __init__(self, instrument, frequency, time, length, volume):
        self.instrument = instrument
        self.frequency = frequency
        self.time = time
        self.length = length
        self.volume = volume


class SynthesizerProject:
    def __init__(self, api_function):
        self.x = Generator(api_function)
        self.rw, self.lw = 0, 0
        self.w, self.h = 0, 0
        self.d = jsd()
        self.tones: [SynthesizerProjectTone] = []


    def draw(self):
        sc.clear()
        self.tones.sort(key=lambda x: x.time)
        self.d.visual.draw_time = (pygame.time.get_ticks() - self.d.time_start) / 1000.0
        self.draw_tones()

    def draw_tones(self):
        for i in self.tones:
            ...
        return
        addstr(
            rows * (self.d.visual.chanels + 1) + tone_chanel - self.d.visual.cy,
            self.lw + int_xpos,
            ll,
            c.gen.note.selected
            if selected else
            (c.gen.note.a if tone_id % 2 == 0 else c.gen.note.b)
        )
        sc.chgat(y, self.lw + x, 1, curses.color_pair(c.gen.timeline))

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

    def create(self, what, dt=0.25):
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
            [0.25, 1.0],
            [0.125, 3.0]
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


        def addcc(t, fq, l=1.0, volume=1.0):
            for ffq, v in sndvlm:
                f = fq * ffq
                v *= volume
                #self.x.add_note([t * dt, f, v, t * dt + dt * l * lm, f, 0], 1, MODE_LINEAR)
                self.x.add(GeneratorTone(t*dt, dt*l*lm,v,f))
            return t + l

        def add(t, fq, l=1.0, volume=1.0):
            self.tones.append(SynthesizerProjectTone(0, fq, t, l, volume))
            return addcc(t, fq, l, volume)

        def addc(t, ch, l=1):
            for cc, i in enumerate(sorted(ch)):
                ovh = l * 0.05 * cc
                addcc(t + ovh, i, l - ovh, volume=2.0 / len(ch))
            return t + l

        def mx(fq, oct):
            return fq * pow(2.0, oct + 1)

        def bt(t, l=1):
            #for i in range(42):
            #    f = 5550 + i * 116.1251261261261
            #self.x.add_note([t * dt, 0.0, 1.0, t * dt + dt * l * lm * 0.5, 0.0, 0], 1, MODE_NOISE)
            #self.x.add(GeneratorTone(t*dt, dt*l*lm*0.5,5.0,112525951259179.12512951251))
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
            track_time=0.0,
            visual=jsd(
                selection=jsd(
                    pos=None
                )
            ),
            time_start=0
        )
        self.tones = []
        self.d.time_start = pygame.time.get_ticks()

        self.create('r')
        t = -time.time()
        raw = self.x.compile()
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

        while True:
            self.resize()
            self.draw()
            self.events()
