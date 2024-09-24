import wave
import librosa
import mutagen.mp3
import pygame
import os
import math
import numpy as np
from mutagen.id3 import ID3, TIT2, TALB, TPE1, TCON, APIC
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from random import randint, choice, shuffle
from threading import Thread, Lock


log = lambda t, msg:None


EVENT_MUSIC_END = pygame.USEREVENT + 1
global_pygame_mutex = Lock()


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


def basic_sin_interpolation(t):
    # linear interpolation to sinus interpolation
    # range from 0 -> l: number b:
    def f_x(b, l):
        return int(math.asin(b / l) * l / math.pi * 2 * t + b * (1 - t) - 0.01)

    return f_x


def upgraded_sin_interpolation(b, l):
    # range from 0 -> l: number b:
    return int(((math.sin((b / l - 1 / 2) * math.pi) + 1) / 2) * l - 0.01)


def way_way_bass_boost_interpolation(b, l):
    # range from 0 -> l: number b:
    x = b / l
    return int((
                       (2680 / 351) * x ** 5 -
                       (6700 / 351) * x ** 4 +
                       (51137 / 3510) * x ** 3 -
                       (19411 / 7020) * x ** 2 +
                       (1519 / 2340) * x ** 1
               ) * l - 0.01)


def bass_boost_interpolation_pow4(b, l):
    # range from 0 -> l: number b:
    x = 1 - b / l
    return int((
                       1 - (-1.066666666666 / 16 * (x - 2) ** 4 + 1.066666666666666)
               ) * l - 0.01)


def bass_boost_interpolation_pow2(b, l):
    # range from 0 -> l: number b:
    x = 1 - b / l
    return int((
                       1 - (-1.3333333333 / 4 * (x - 2) ** 2 + 1.33333333333333)
               ) * l - 0.01)


def bass_boost_interpolation_pow_soft1(b, l):
    # range from 0 -> l: number b:
    x = b / l
    return int((
            (x ** (3/2) + x) / 2
               ) * l - 0.01)


def bass_boost_interpolation_pow_soft2(b, l):
    # range from 0 -> l: number b:
    x = b / l
    return int((
            (x ** (5/4) + x) / 2
               ) * l - 0.01)


class Music:
    def __init__(self, path):
        self.sound = pygame.mixer.Sound(path)
        self.path = path
        self.freq = None
        self.array = None
        self.info = None

    def post_init(self):
        self.freq = pygame.mixer.get_init()[0]
        self.array = pygame.sndarray.array(self.sound)

        self.info = jsd({
            'title': os.path.basename(self.path),
            'album': "Unknown album",
            'artist': "Unknown artist",
            'autor': "Unknown autor",
            'content': "Unknown content",
            'length': -1
        })

        # update information
        self.get_info()

    def get_info(self):
        ext = os.path.splitext(self.path)[1]

        if ext == ".flac":
            try:
                audio = FLAC(self.path)
            except mutagen.flac.FLACNoHeaderError:
                audio = {}
        elif ext == ".mp3":
            try:
                audio = MP3(self.path)
            except mutagen.mp3.HeaderNotFoundError:
                audio = {}
        else:
            self.info = jsd({
                'title': os.path.basename(self.path),
                'album': "Unknown album",
                'artist': "Unknown artist",
                'autor': "Unknown autor",
                'content': "Unknown content",
                'length': self.samples / self.freq
            })
            return

        title = os.path.basename(self.path)
        if ext == ".flac" and 'title' in audio:
            title = audio['title'][0]
        elif ext == ".mp3" and 'TIT2' in audio:
            title = audio['TIT2'].text[0].replace("/", ",")

        album = "Unknown album"
        if ext == ".flac" and 'album' in audio:
            album = audio['album'][0]
        elif ext == ".mp3" and 'TALB' in audio:
            album = audio['TALB'].text[0].replace("/", ",")

        artist = "Unknown artist"
        if ext == ".flac" and 'artist' in audio:
            artist = audio['artist'][0]
        elif ext == ".mp3" and 'TPE1' in audio:
            artist = audio['TPE1'].text[0].replace("/", ",")

        autor = "Unknown autor"
        if ext == ".flac" and 'composer' in audio:
            array = audio['composer'][0].split(" ")
            autor = array[len(array) - 1]
        elif ext == ".mp3" and 'TCOM' in audio:
            array = audio['TCOM'].text[0].split(" ")
            autor = array[len(array) - 1]

        content = "Unknown content"
        if ext == ".mp3" and 'TCON' in audio:
            content = audio['TCON'].text[0].replace("/", ",")

        self.info = jsd({
            'title': title,
            'album': album,
            'artist': artist,
            'autor': autor,
            'content': content,
            'length': self.samples / self.freq
        })

    @property
    def samples(self):
        return self.array.shape[0]

    def update_sound(self):
        self.array = self.array.copy(order='C')
        self.sound = pygame.sndarray.make_sound(self.array)

        log('info', 'sound updated')

    def stop(self):
        self.sound.stop()

    def fadeout(self, time_ms):
        self.sound.fadeout(time_ms)

    def play(self, loops=0):
        self.sound.play(loops)

    def update_and_play(self, loops=0):
        self.update_sound()
        self.play(loops)

    def save(self, filename):

        sfile = wave.open(filename, 'w')
        # set the parameters
        sfile.setframerate(self.freq)
        sfile.setnchannels(2)
        sfile.setsampwidth(2)

        # write raw PyGame sound buffer to wave file
        self.array = self.array.copy(order='C')
        sfile.writeframesraw(self.array)

        sfile.close()

        log('info', f'music "{self.info.title}" saved as "{filename}".')


class MutableMusic(Music):
    def __init__(self, path):
        super().__init__(path)

        self.temp = None
        self.beats = None

    def update_temp(self):
        y, sr = librosa.load(self.path, sr=self.freq)
        # D_harmonic, D_percussive = librosa.decompose.hpss(y, sr=sr)
        self.temp, self.beats = librosa.beat.beat_track(y=y, sr=sr)
        self.beats = librosa.frames_to_time(self.beats, sr=sr)
        self.beats = list(map(lambda x: int(self.freq * x), self.beats))
        log('info', f"Temp updated. found: temp={self.temp} beats=arr[length={len(self.beats)}]")

    def bass(self, tact, f_x):
        if tact is None:
            tact = [True]

        pp = np.zeros((self.samples, 2), dtype=self.array.dtype)

        beats = []
        for i in range(len(self.beats)):
            if tact[i % len(tact)]:
                beats.append(self.beats[i])

        for i in range(-1, len(beats) - 1):
            c, nex = (0 if i == -1 else beats[i]), beats[i + 1]
            l = nex - c
            for b in range(l):
                pp[c + b] = self.array[c + f_x(b, l)]

        c, nex = beats[-1], self.samples
        l = nex - c
        for b in range(l):
            pp[c + b] = self.array[c + f_x(b, l)]

        self.array = pp
        log('info', f"Bass applied")

    def reverse_temp(self):
        b = [0] + self.beats + [len(self.array)]
        for i in range(len(b) - 1):
            c, nex = b[i], b[i + 1]
            self.array[c:nex] = self.array[nex - 1:(None if c == 0 else c - 1):-1]
        log('info', 'reverse using temp completed')

    def reverse(self):
        self.array = self.array[::-1]
        log('info', 'reverse completed')

    def echo(self, *in_pairs):
        if len(in_pairs) % 2 != 0:
            log('error', 'parameters must be pairs. (even count of parameters)')
            return
        pairs = []
        for i in range(0, len(in_pairs), 2):
            pairs.append((in_pairs[i], in_pairs[i + 1]))
            if in_pairs[i] <= 0:
                log('error', 'all shifts of echo must be positive. (could be negative)')
                return
        pairs.insert(0, (0, 1))
        sm = sum(map(lambda x: abs(x[1]), pairs)) # sum of amplitudes
        mx = max(map(lambda x: x[0], pairs)) # max of shift
        # apply
        z = list(self.array.shape)
        l = z[0]
        z[0] += int(self.freq * mx)
        arr = np.zeros(z, dtype='float32')

        for i in pairs:
            sh = int(i[0] * self.freq)
            arr[sh:sh + l] += self.array * i[1] / sm

        self.array = arr.astype(self.array.dtype)

    def jackal(self, id):
        self.scaling(id, log_bool=False)
        self.scaling(1 / id, log_bool=False)
        log('info', f"Jackal applied")

    def smooth_jackal(self, id):  # TODO: this function.
        self.array = self.array
        exit(179057)

    def distortion(self, id, log_bool=True):
        min_value = np.iinfo(self.array.dtype).min
        max_value = np.iinfo(self.array.dtype).max
        if len(self.array.shape) == 2 and self.array.shape[1] == 2:
            for i in range(self.samples):
                self.array[i] = np.minimum(np.full(2, max_value, dtype=np.float64), np.maximum(np.full(2, min_value, dtype=np.float64), self.array[i].astype(np.float64) * id)).astype(self.array.dtype)
        else:
            for i in range(self.samples):
                self.array[i] = min(max_value, max(min_value, self.array[i]))
        if log_bool:
            log('info', f"Distortion applied")

    def scaling(self, id, log_bool=True):
        id = 1 / id

        pp = np.zeros((int(self.samples * id), 2), dtype=self.array.dtype)

        for i in range(int(self.samples * id)):
            pp[i] = self.array[int(i / id)]
        self.array = pp
        if log_bool:
            log('info', f"Speeding applied")

    def speeding(self, id, log_bool=True):
        block_size = 1024 * 4
        block_shift = 1024 * 4

        #### TO FRQ
        array = self.array.astype("complex64")

        # destroy stereo
        if len(array.shape) == 2:
            array = (array[:, 0] * 0.5 + array[:, 1] * 0.5)

        nnodes = (array.shape[0] - block_size) // block_shift

        datarray = np.zeros((nnodes, block_size), dtype="complex64")

        for i in range(block_size // 2 // block_shift, nnodes):
            # get slice
            subarray = array[block_shift * i - block_size // 2: block_shift * i + block_size // 2]
            if subarray.shape[0] != block_size:
                c = np.zeros((block_size,), dtype="complex64")
                c[:subarray.shape[0]] += subarray
                subarray = c
            # get info
            datarray[i] = np.fft.fft(subarray)

        #### UPDATE

        block_shift = int(block_shift / id)

        #### TO RAW

        new_array = np.zeros(datarray.shape[0] * block_shift, dtype=np.float32)

        # fill array
        for i in range(datarray.shape[0]):
            # load
            data = datarray[i]
            # compress
            cdata = np.zeros((block_shift,), "complex64")
            for ii in range(cdata.shape[0]):
                cdata[ii] = data[int(ii * block_size / block_shift)]
            # ifft
            new_array[i * block_shift:(i + 1) * block_shift] = list(map(lambda x: x.real, np.fft.ifft(cdata)))

        # clip array
        for i in range(new_array.shape[0]):
            new_array[i] = min(32767, max(-32768, new_array[i]))
        # duplicate row
        new_array = np.repeat(new_array[:, np.newaxis], 2, axis=1)
        # cast array
        new_array = new_array.astype("int16")
        new_array = new_array.copy(order='C')

        self.array = new_array

        if log_bool:
            log('info', f"Speeding applied")

    def accurate_speeding(self, id, log_bool=True):
        block_size = 1024 * 4
        block_shift = 1024 * 4
        click_denoise_radius = 64

        #### TO FRQ
        array = self.array.astype("complex64")

        # destroy stereo
        if len(array.shape) == 2:
            array = (array[:, 0] * 0.5 + array[:, 1] * 0.5)

        nnodes = (array.shape[0] - block_size) // block_shift

        datarray = np.zeros((nnodes, block_size), dtype="complex64")

        for i in range(block_size // 2 // block_shift, nnodes):
            # get slice
            subarray = array[block_shift * i - block_size // 2: block_shift * i + block_size // 2]
            if subarray.shape[0] != block_size:
                c = np.zeros((block_size,), dtype="complex64")
                c[:subarray.shape[0]] += subarray
                subarray = c
            # get info
            datarray[i] = np.fft.fft(subarray)

        #### UPDATE

        block_shift = int(block_shift / id)

        #### TO RAW

        new_array = np.zeros(datarray.shape[0] * block_shift, dtype=np.float32)

        # fill array
        for i in range(datarray.shape[0]):
            # load
            data = datarray[i]
            # compress
            cdata = np.zeros((block_shift,), "complex64")
            for ii in range(cdata.shape[0]):
                cdata[ii] = data[int(ii * block_size / block_shift)]
            # ifft
            new_array[i * block_shift:(i + 1) * block_shift] = list(map(lambda x: x.real, np.fft.ifft(cdata)))

        # clip array
        for i in range(new_array.shape[0]):
            new_array[i] = min(32767, max(-32768, new_array[i]))

        # update bound values:
        for i in range(block_shift, new_array.shape[0], block_size):
            # select -d - d
            s = i - click_denoise_radius
            e = i + click_denoise_radius
            vs = new_array[s]
            ve = new_array[e]
            for d in range(s, e):
                # replace value to remove clicks
                t = (d - s) / (e - s)
                new_array[d] = min(32767, max(-32768, int(vs * (1 - t) + ve * t)))

        # duplicate row
        new_array = np.repeat(new_array[:, np.newaxis], 2, axis=1)
        # cast array
        new_array = new_array.astype("int16")
        new_array = new_array.copy(order='C')

        self.array = new_array

        if log_bool:
            log('info', f"Accurate Speeding applied")

    def pitching(self, id, log_bool=True):
        # use the most accurate way instead of the fastest.
        if id > 1.0:
            self.speeding(1/id, log_bool=False)
            self.scaling(id, log_bool=False)
        else:
            self.scaling(id, log_bool=False)
            self.speeding(1/id, log_bool=False)
        if log_bool:
            log('info', f"Accurate Pitching applied")

    def fast_pitching(self, id, log_bool=True):
        # use the fastest way instead of more accurate.
        if id > 1.0:
            self.scaling(id, log_bool=False)
            self.speeding(1/id, log_bool=False)
        else:
            self.speeding(1/id, log_bool=False)
            self.scaling(id, log_bool=False)
        if log_bool:
            log('info', f"Fast Pitching applied")

    def accurate_pitching(self, id, log_bool=True):
        # use the most accurate way instead of the fastest.
        if id > 1.0:
            self.accurate_speeding(1/id, log_bool=False)
            self.scaling(id, log_bool=False)
        else:
            self.scaling(id, log_bool=False)
            self.accurate_speeding(1/id, log_bool=False)
        if log_bool:
            log('info', f"Accurate Accurate Pitching applied")

    def accurate_fast_pitching(self, id, log_bool=True):
        # use the fastest way instead of more accurate.
        if id > 1.0:
            self.scaling(id, log_bool=False)
            self.accurate_speeding(1/id, log_bool=False)
        else:
            self.accurate_speeding(1/id, log_bool=False)
            self.scaling(id, log_bool=False)
        if log_bool:
            log('info', f"Accurate Fast Pitching applied")


FUNCTIONS = {
    # support
    'get-temp': lambda mus: mus.update_temp(),
    # change
    'scale': lambda mus, x: mus.scaling(float(x)),
    'jackal': lambda mus, x: mus.jackal(float(x)),
    'distortion': lambda mus, x: mus.distortion(float(x)),
    'speeding': lambda mus, x: mus.speeding(float(x)),
    'aspeeding': lambda mus, x: mus.accurate_speeding(float(x)),
    'pitching': lambda mus, x: mus.pitching(float(x)),
    'fpitching': lambda mus, x: mus.fast_pitching(float(x)),
    'apitching': lambda mus, x: mus.accurate_pitching(float(x)),
    'afpitching': lambda mus, x: mus.accurate_fast_pitching(float(x)),
    'echo': lambda mus, *args: mus.echo(*list(map(float, args))),
    'reverse': lambda mus: mus.reverse(),
    'reverse-temp': lambda mus: mus.reverse_temp(),
    # saving
    'update': lambda mus: (mus.update_sound(), mus.get_info()),
    'save': lambda mus: mus.save(),
}


class Album:
    MODE_NO_REPEAT = 0
    MODE_REPEAT = 1
    MODE_REPEAT_ONE = 2

    def __init__(self):
        self.name: str = "unnamed album"
        self.list: [MutableMusic] = []

        self.chanel = pygame.mixer.Channel(0)
        self.chanel.set_endevent(EVENT_MUSIC_END)

        self.playing = None
        self.freq = None
        self.ignore_next_event = 0

        self.paused = False
        self.time = 0
        self.time_prev = 0

        self.cf = jsd({
            "fadeout": 100,  # ms
            "play_mode": Album.MODE_REPEAT,
            "shuffle": False,
        })

    def __len__(self):
        return self.list.__len__()

    def __iter__(self):
        return self.list.__iter__()

    def __getitem__(self, item):
        return self.list.__getitem__(item)

    def __setitem__(self, item, val):
        return self.list.__setitem__(item, val)

    @property
    def curr(self):
        if self.playing is None:
            return None
        return self.list[self.playing]

    def start(self):
        self.chanel.play(self[self.playing].sound)
        self.paused = False
        self.time = 0
        self.time_prev = pygame.time.get_ticks()
        log('info', f"Playing {self.curr.info.title}")

    def pause(self):
        self.paused = True
        if self.list:
            self.chanel.pause()
            t = pygame.time.get_ticks()
            self.time += t - self.time_prev

    def unpause(self):
        self.paused = False
        if self.list:
            self.chanel.unpause()
            self.time_prev = pygame.time.get_ticks()

    def pause_or_unpause(self):
        if self.paused:
            self.unpause()
        else:
            self.pause()

    def fadeout(self, timeout):
        self.chanel.fadeout(timeout)
        self.paused = True

    def stop(self):
        if self.chanel.get_busy():
            self.ignore_next_event += 1
        self.chanel.stop()
        self.paused = True

    def next(self):
        if self.playing is None:
            if len(self.list) > 0:
                self.playing = 0
                self.start()
        elif len(self.list) == 0:
            self.playing = None
        elif self.cf.play_mode == Album.MODE_NO_REPEAT:
            if self.playing == len(self.list) - 1:
                self.playing = None
                self.stop()
            else:
                self.playing += 1
                self.start()
        elif self.cf.play_mode == Album.MODE_REPEAT:
            if self.playing == len(self.list) - 1:
                self.playing = 0
                self.start()
            else:
                self.playing += 1
                self.start()
        elif self.cf.play_mode == Album.MODE_REPEAT_ONE:
            self.start()

    def get_progress(self):
        if self.curr is None:
            return 0, 0
        return self.time / 1000.0, self.curr.info['length']

    def add(self, mus_path: str):
        was_paused = not self.paused

        with global_pygame_mutex:

            if was_paused:
                self.pause()

            try:
                mus: MutableMusic = MutableMusic(mus_path)
            except Exception as e:
                log("error", f"error: {e}")
                if was_paused:
                    self.unpause()
                return

            if was_paused:
                self.unpause()


        mus.post_init()
        log("info", f"loaded music: {mus.info.title}")
        self.list.append(mus)
        if not self.paused:  # start play music
            if len(self.list) == 1:  # if it is first new music.
                self.playing = 0
                self.start()

    def remove(self, mus_id):
        if not 0 <= mus_id < len(self.list):
            log('error', f'index to remove is out of bounds (must 0 <= {mus_id} < (len(album)={len(self.list)}) )')
            return
        if mus_id < self.playing:
            self.playing -= 1
            self.list.pop(mus_id)
        elif mus_id == self.playing:
            self.stop()
            if len(self.list) > 1:
                self.next()
                self.stop()
                if self.playing == mus_id:
                    self.list.pop(mus_id)
                    self.playing = None
                else:
                    self.list.pop(mus_id)
                    if self.playing > mus_id:
                        self.playing -= 1
                    self.start()
            else:
                self.list.pop(mus_id)
                self.playing = None
        else:
            self.list.pop(mus_id)

    def move_up(self, mus_id):
        if mus_id == 0:
            return
        if mus_id - 1 == self.playing:
            self.list[mus_id], self.list[mus_id - 1] = self.list[mus_id - 1], self.list[mus_id]
            self.playing += 1
        elif mus_id == self.playing:
            self.list[mus_id], self.list[mus_id - 1] = self.list[mus_id - 1], self.list[mus_id]
            self.playing -= 1
        else:
            self.list[mus_id], self.list[mus_id - 1] = self.list[mus_id - 1], self.list[mus_id]

    def move_down(self, mus_id):
        if mus_id == len(self.list) - 1:
            return
        if mus_id + 1 == self.playing:
            self.list[mus_id], self.list[mus_id + 1] = self.list[mus_id + 1], self.list[mus_id]
            self.playing -= 1
        elif mus_id == self.playing:
            self.list[mus_id], self.list[mus_id + 1] = self.list[mus_id + 1], self.list[mus_id]
            self.playing += 1
        else:
            self.list[mus_id], self.list[mus_id + 1] = self.list[mus_id + 1], self.list[mus_id]

    def shuffle(self):
        t = self.list[self.playing]
        shuffle(self.list)
        self.playing = 0
        for c, i in enumerate(self.list):
            if i is t:
                idd = c
                break
        else:
            self.stop()
            return
        self.list[0], self.list[idd] = self.list[idd], self.list[0]

    def play_next(self):
        self.stop()
        self.next()

    def play_from(self, mus_id):
        if mus_id is None:
            log('error', f'no music is played, can not replay it.')
            return
        if not 0 <= mus_id < len(self.list):
            log('error', f'index to play is out of bounds (must 0 <= {mus_id} < (len(album)={len(self.list)}) )')
            return
        self.stop()
        self.playing = mus_id
        if self.cf.shuffle:
            self.shuffle()
        self.start()
        return

    def update(self):
        if not self.paused:
            t = pygame.time.get_ticks()
            self.time += t - self.time_prev
            self.time_prev = t
        if self.curr is not None and self.time > self.curr.info['length'] * 1000 + 5000.0:  # may be some error
            self.stop()
            self.next()
        for i in pygame.event.get():
            if i.type == EVENT_MUSIC_END:
                if self.ignore_next_event > 0:
                    self.ignore_next_event -= 1
                else:
                    self.next()