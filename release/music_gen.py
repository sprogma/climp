import wave
import librosa
import mutagen.mp3
import pygame
import os
import math
import numpy as np
from random import randint, choice, shuffle
from threading import Thread, Lock


class ProgramTrackFreq:
    def __init__(self):
        self.instruments = np.zeros((64, ), dtype=np.int32)
        self.notes = np.zeros((64, 3), dtype=np.float32)
        self.len = 0

    @property
    def alloc(self):
        return self.notes.shape[0]

    def add_note(self, pos, freq, volume, instrument):
        self.len += 1
        if self.len > self.alloc:
            if self.alloc < 32:
                self.notes.resize((64, 3))
                self.instruments.resize((64, ))
            else:
                self.notes.resize((int(self.alloc * 1.5), 3))
                self.instruments.resize((int(self.alloc * 1.5), ))
        self.notes[self.len - 1][0] = pos
        self.notes[self.len - 1][1] = freq
        self.notes[self.len - 1][2] = volume
        self.instruments[self.len - 1] = instrument

    def update(self):
        self.notes.resize((self.len, 3))
        idx = np.argsort(self.notes[:,0])
        self.notes = self.notes[idx]
        self.instruments = self.instruments[idx]
        print(self.notes)
        print(self.instruments)


class ProgramTrackInstrumentTone:
    def __init__(self, freq_add, freq_mul, volume):
        self.freq_add = freq_add
        self.freq_mul = freq_mul
        self.volume = volume


class ProgramTrackInstrument:
    def __init__(self, tones):
        self.tones : [ProgramTrackInstrumentTone] = tones


class ProgramTrack:
    def __init__(self):
        self.instruments : [ProgramTrackInstrument] = []
        self.freq = ProgramTrackFreq()
        self.raw = None
        self.sound = None

    def add_note(self, pos, freq, volume, instrument):
        self.freq.add_note(pos, freq, volume, instrument)

    def manage_instrument(self, instrument, data):
        self.instruments[instrument] = ProgramTrackInstrument(data)

    def ccall

x = ProgramTrack()
x.freq.add_note(0, 1, 1, 1)
x.freq.add_note(0.5, 1, 1, 1)
x.freq.add_note(-0.5, 1, 1, 1)
x.freq.update()
