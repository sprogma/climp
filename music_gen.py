import wave
import librosa
import mutagen.mp3
import pygame
import os
import math
import numpy as np
from random import randint, choice, shuffle
from threading import Thread, Lock


class ProgramTrack:
    def __init__(self):
        self.freq = ProgramTrackFreq()
        self.raw = ProgramTrackRaw()
        self.sound = None