import math
import random


class ProgramExportTrackFreq:
    def __init__(self):
        self.notes = np.zeros((64, 6), dtype=np.float32)
        self.tools = np.zeros((64,), dtype=np.int32)
        self.modes = np.zeros((64,), dtype=np.int32)
        self.len = 0

    @property
    def alloc(self):
        return self.notes.shape[0]

    def add_note(self, pos, freq, volume, pos2, freq2, volume2, instrument, mode):
        self.len += 1
        if self.len > self.alloc:
            if self.alloc < 32:
                self.notes.resize((64, 6))
                self.tools.resize((64, ))
                self.modes.resize((64, ))
            else:
                new_len = int(self.alloc * 1.5)
                self.notes.resize((new_len, 6))
                self.tools.resize((new_len, ))
                self.modes.resize((new_len, ))
        self.notes[self.len - 1][0] = pos
        self.notes[self.len - 1][1] = pos2
        self.notes[self.len - 1][2] = freq
        self.notes[self.len - 1][3] = freq2
        self.notes[self.len - 1][4] = volume
        self.notes[self.len - 1][5] = volume2
        self.tools[self.len - 1] = instrument
        self.modes[self.len - 1] = mode

    def update(self):
        self.notes.resize((self.len, 6))
        idx = np.argsort(self.notes[:,0])
        self.notes = self.notes[idx]
        self.tools = self.tools[idx]
        self.modes = self.modes[idx]


class ProgramExportTrackInstrumentTone:
    def __init__(self, freq_add, freq_mul, volume):
        self.freq_add = freq_add
        self.freq_mul = freq_mul
        self.volume = volume


class ProgramExportTrackInstrument:
    def __init__(self, tones):
        self.tones : [ProgramExportTrackInstrumentTone] = tones


class ProgramExportTrack:
    def __init__(self, api_function):
        self.api_function = api_function

        self.instruments : [ProgramExportTrackInstrument] = []
        self.freq = ProgramExportTrackFreq()
        self.raw = None
        self.sound = None

        self.mixer = jsd(
            frequency=44100,
        )

    def add_note(self, iterable, instrument, mode):
        self.freq.add_note(*iterable, instrument, mode)

    def manage_instrument(self, instrument, data):
        self.instruments[instrument] = ProgramExportTrackInstrument(data)

    def compile(self):
        self.freq.update()

        # get info
        samples = int(max(self.freq.notes[:self.freq.len,1]) * self.mixer.frequency)

        # send c code signals

        result = np.zeros((samples,), dtype=np.float32)

        self.api_function(
            result,
            result.shape[0],
            self.freq.notes,
            self.freq.tools,
            self.freq.modes,
            self.freq.len,
            self.mixer.frequency
        )

        # set result data

        self.raw = result
        self.raw = np.tanh(self.raw)
        self.raw *= 32767.0
        self.raw = self.raw.astype(dtype=np.int16)
        self.raw = np.column_stack((self.raw, self.raw))

        # export sound


        self.raw = self.raw.copy(order='C')
        self.sound = pygame.sndarray.make_sound(self.raw)


class ProjectNote:
    def __init__(self, instrument, frequency, time, length, volume=1.0):
        self.i = instrument
        self.f = frequency
        self.t = time
        self.l = length
        self.v = volume


class ProjectToneTemplateItem:
    def __init__(self, frequency, time_start, length, volume):
        self.f = frequency
        self.t = time_start
        self.l = length
        self.v = volume

class ProjectToneTemplate:
    def __init__(self, iterable: []):
        self.tones : [ProjectToneTemplateItem] = iterable

    def to_notes(self, tone):
        notes = []
        for i in self.tones:
            notes.append(ProjectNote(
                tone.i,
                tone.f * i.f.multiply + i.f.shift,
                tone.t + tone.l * i.t.multiply + i.t.shift,
                tone.l * i.l.multiply + i.l.shift,
                tone.v * i.v.multiply + i.v.shift,
            ))
        return notes

class ProjectTone:
    def __init__(self, tone_template, instrument, frequency, time, length, volume=1.0):
        self.template = tone_template
        self.i = instrument
        self.f = frequency
        self.t = time
        self.l = length
        self.v = volume


class ProjectTimeInfo:
    def __init__(self):
        ...


class TrackProject:
    def __init__(self, api_function):
        self.x = ProgramExportTrack(api_function)
        self.rw, self.lw = 0, 0
        self.w, self.h = 0, 0
        self.d = jsd()
        self.tones = []  # tones
        self.temps = []  # tone templates

    def draw(self):
        sc.clear()
        self.draw_tones()

    def draw_tones(self):
        # draw tones
        line = []
        for i in range(len(self.tones)):
            # add to line
            line.append((self.tones[i].time, self.tones[i].length, i))
        line.sort()
        # draw notes

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
            if key == curses.KEY_RIGHT:
                self.focus = Application.FOCUS_RIGHT
            if key == curses.KEY_LEFT:
                self.focus = Application.FOCUS_LEFT
            else:
                if self.mode == MODE_EXPLORER:
                    self.events_explorer(key)
                elif self.mode == MODE_CONSOLE:
                    self.events_console(key)

    def create(self, what):
        dt = 0.25
        lm = 1
        fqcorr = 0.5

        MODE_LINEAR = 0
        MODE_NOISE = 1

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

        def add(t, fq, l=1.0, /, volume=1.0):
            for i in range(len(sndvlm)):
                f = fq * (i + 1) * fqcorr
                v = sndvlm[i]
                self.x.add_note([t * dt, f, v, t * dt + dt * l * lm, f, 0], 1, MODE_LINEAR)
            for i in range(3):
                f = fq / 2 ** i
                v = 0.3
                self.x.add_note([t * dt, f, v, t * dt + dt * l * lm, f, 0], 1, MODE_LINEAR)
            return t + l
            for i in range(28):
                f = fq * (i + 1) / 2.0
                v = volume * 4/28
                if i not in (1, 2, 4, 8, 16, 32):
                    v /= 1.1 ** i
                self.x.add_note([t * dt, f, v, t * dt + dt * l * lm, f, 0], 1, MODE_LINEAR)
            return t + l

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
            self.x.add_note([t * dt, 0.0, 1.0, t * dt + dt * l * lm * 0.5, 0.0, 0], 1, MODE_NOISE)
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
                    add(et, mx(A, 1))
                    et += 0.025
                    add(et, mx(F, 1))
                    et += 0.025
                    add(et, mx(C, 1))
                    et += 0.025
                    add(et, mx(A, 0))
                    et += 0.025
                    add(et, mx(D, 0))

                    et += 1 - 0.025 * 4

                    add(et, mx(D, 0))
                    et += 0.025
                    add(et, mx(A, 0))
                    et += 0.025
                    add(et, mx(C, 1))
                    et += 0.025
                    add(et, mx(F, 1))
                    et += 0.025
                    add(et, mx(A, 1))

                    et += 1 - 0.025 * 4

                    add(et, mx(A, 1))
                    et += 0.025
                    add(et, mx(F, 1))
                    et += 0.025
                    add(et, mx(C, 1))
                    et += 0.025
                    add(et, mx(A, 0))
                    et += 0.025
                    add(et, mx(D, 0))

                    et += 1 - 0.025 * 4

                    add(et, mx(D, 0))
                    et += 0.025
                    add(et, mx(A, 0))
                    et += 0.025
                    add(et, mx(C, 1))
                    et += 0.025
                    add(et, mx(F, 1))
                    et += 0.025
                    add(et, mx(C, 2))

                    et += 1 - 0.025 * 4

            def beat(t, ch, l=1):
                global et
                for i in range(2):
                    addc(t + 0 * l + 8 * l * i, ch, l)
                    addc(t + 1 * l + 8 * l * i, ch, l)
                    bt(t + 2 * l + 8 * l * i, l)
                    addc(t + 3 * l + 8 * l * i, ch, l)
                    addc(t + 4 * l + 8 * l * i, ch, l)
                    addc(t + 5 * l + 8 * l * i, ch, l)
                    bt(t + 6 * l + 8 * l * i, l)
                addc(t + 7 * l + 8 * l, ch, l)
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

        if what == 't':
            lm = 2.0
            tsoy()
        else:
            lm = 2.0
            metal1()

        print(f'{self.x.freq.len} notes...\n')
        self.x.compile()
        #self.x.sound.play(1)
        print('result length = ', self.x.raw.shape[0] / self.x.mixer.frequency, 's')
        print('ok')

        return self.x.sound

        while True:
            ...

    def resize(self):
        self.h, self.w = sc.getmaxyx()

        self.lw = max(30, self.w // 5)
        self.rw = self.w - self.lw

    def run(self):

        self.d.z = 0

        while True:
            self.resize()
            self.draw()
            self.events()
