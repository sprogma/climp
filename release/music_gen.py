class ProgramTrackFreq:
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


class ProgramTrackInstrumentTone:
    def __init__(self, freq_add, freq_mul, volume):
        self.freq_add = freq_add
        self.freq_mul = freq_mul
        self.volume = volume


class ProgramTrackInstrument:
    def __init__(self, tones):
        self.tones : [ProgramTrackInstrumentTone] = tones


class ProgramTrack:
    def __init__(self, api_function):
        self.api_function = api_function

        self.instruments : [ProgramTrackInstrument] = []
        self.freq = ProgramTrackFreq()
        self.raw = None
        self.sound = None

        self.mixer = jsd(
            frequency=44100,
        )

    def add_note(self, iterable, instrument, mode):
        self.freq.add_note(*iterable, instrument, mode)

    def manage_instrument(self, instrument, data):
        self.instruments[instrument] = ProgramTrackInstrument(data)

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


class ProjectTaburlature:
    def __init__(self, api_function):
        self.t = ProgramTrack(api_function)

    def run(self):


        MODE_LINEAR = 0
        MODE_FAST = 1

        # x = ProgramTrack(clib.kernel)

        m = ProjectTaburlature(clib.kernel)

        m.run()

        print(f'{x.freq.len} notes...\n')
        x.compile()
        x.sound.play(-1)
        print('result length = ', x.raw.shape[0] / x.mixer.frequency, 's')
        print('ok')

        while True:
            ...

        exit(0)
        dt = 0.25

        def add(t, fq, l=1.0, /, volume=1.0):
            for i in range(4):
                f = fq / pow(2, i * 3 / 12)
                x.add_note([t * dt, f, volume * 0.4 / 2.0 ** i, t * dt + dt * l, f, 0], 1, MODE_LINEAR)
            return t + l

        def addc(t, ch, l=1):
            for cc, i in enumerate(sorted(ch)):
                ovh = l * 0.05 * cc
                add(t + ovh, i, l - ovh, volume=2.0 / len(ch))
            return t + l

        def mx(fq, oct):
            return fq * pow(2.0, oct + 1)

        def bt(t, l=1):
            for i in range(26):
                f = 100 + i * 279
                add(t, f, l / 2, volume=5.0 / 64.0)
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
               mx(A, 0),
               mx(C, 1),
               mx(E, 1)]
        _C = [mx(C, -1),
              mx(E, -1),
              mx(G, 0),
              mx(C, 1),
              mx(E, 1)]
        _Dm = [mx(D, 0),
               mx(A, 0),
               mx(D, 1),
               mx(E, 1)]
        _G = [mx(G, -2),
              mx(B, -1),
              mx(D, 0),
              mx(G, 0),
              mx(G, 1)]

        # gen track
        et = 0

        def skip():
            global et
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

        print(f'{x.freq.len} notes...\n')
        x.compile()
        x.sound.play(-1)
        print('result length = ', x.raw.shape[0] / x.mixer.frequency, 's')
        print('ok')

        while True:
            ...
