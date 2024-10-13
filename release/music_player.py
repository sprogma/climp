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
import datetime
import numpy as np
from random import randint, choice
import curses
from curses.textpad import Textbox, rectangle
from threading import Thread, Lock
import ctypes

from music_gen import *

import music_class
import music_gen
#music_gen_path = pathlib.Path(__file__).parent.joinpath('./music_gen.py')
#with open(str(music_gen_path), 'r') as f:
#    exec(f.read())

FREQ = 44100
pygame.mixer.pre_init(FREQ)
pygame.init()

MODE_EXPLORER = 0
MODE_CONSOLE = 1
global_executor_hash = 0

EVENT_MUSIC_END = music_class.EVENT_MUSIC_END
jsd = music_class.jsd
Music = music_class.Music
MutableMusic = music_class.MutableMusic
Album = music_class.Album

""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
# TODO:
""" USE THIS ELEMENTS WITH SHADING
    ░
    ▒
    ▓
"""

"""
DRAW HELPER
"""

def lib_linkage():
    music_class.log = log
    music_gen.addstr = addstr
    music_gen.c = c
    music_gen.sc = sc
    music_gen.lsc = lsc
    music_gen.rsc = rsc
    music_gen.log = log
    music_gen.jsd = jsd


def log(t, string):
    app.log(string, t)




def addstr(y, x, string, color):
    try:
        sc.addstr(y, x, string, curses.color_pair(color))
    except curses.error as err:
        ...


def addch(y, x, string, color):
    try:
        sc.addch(y, x, string, curses.color_pair(color))
    except curses.error as err:
        ...


def select_color(group, focused, selected):
    return group['focus' if focused else 'unfocus']['selected' if selected else 'unselected']


def hhmmss(sec: float, max_sec: float):
    if max_sec < 60:
        return f'{sec:.2f}'
    elif max_sec < 60 * 60:
        return f'{int(sec / 60):02}:{sec - int(sec / 60) * 60:05.2f}'
    else:
        return f'{int(sec / 3600)}:{int(sec / 60) % 60:02}:{sec - int(sec / 60) * 60:05.2f}'


def generate_bar(progress, width):
    if progress >= 1.0:
        return width, ''
    s = ' ▏▎▍▌▋▊▉'[int((progress * width - int(progress * width)) * 8)]
    return int(progress * width), s


def generate_column(progress, height):
    if progress >= 1.0:
        return height, ''
    s = " ▁▂▃▄▅▆▇"[int((progress * height - int(progress * height)) * 8)]
    return int(progress * height), s


class ExecutorThread(Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs={}, *, daemon=None):

        self.worker = target(*args, **kwargs)

        self.built = True

        def function():
            self.result = self.worker.console_execute()
        super().__init__(group=group, target=function, name=name, daemon=daemon)


class Executor:
    def __init__(self, app, command, selected):
        global global_executor_hash
        self.hash = global_executor_hash = (global_executor_hash + 257) % 179
        self.app: Application = app
        self.command = command
        self.selected = selected
        self.d = jsd(
            loops=[],
            loops_ends=[],
            curr_function=None,
            function_args=[],
        )
        log('job', f'job got hash [{self.hash}]')

    def console_execute(self):
        s = self.command.strip()
        if not s:
            return True
        # check if it is function
        if s.startswith('&'):
            x = s.find('(')
            y = s.find('{')
            if x != -1 and (x < y or y == -1):
                ...
            elif y != -1 and (y < x or x == -1):
                name = s[1:y].strip()
                self.app.d.console.input_function = name
                if not s[y + 1:].strip().startswith('>>'):
                    keys = list(filter(lambda x: x, map(str.strip, s[y + 1:].split(','))))
                    self.app.d.console.functions[name] = []
                else:
                    keys = list(filter(lambda x: x, map(str.strip, s[y + 1:].split(','))))
                    if keys:
                        log('warn', f"if used >> mode, function arguments can't be changed. (ignore this: {', '.join(keys)})")

                self.app.d.console.function_keys[name] = keys
                return True
            else:
                log('error', 'invalid syntax for function definition/call. must be & <name> (...) to call, and & <name> {...} to declare & <name> {>>  ...} to add comands to end')
                return True

        if s.strip() == '}':
            self.app.d.console.input_function = None
        elif self.app.d.console.input_function is not None:
            self.app.d.console.functions[self.app.d.console.input_function].append(s)
        else:
            self.d.curr_function = None
            self.d.function_args = {}
            self.d.loops = []
            self.app.d.console.stop_execution = False
            try:
                res = self.console_execute_string(s)
            except Exception as e:
                log('error', f'at execution happened unknown error {e}.')
                return False
            if not res:
                return False
        return True

    def console_execute_string(self, string):
        # ----------------- function macro arguments
        if self.app.d.console.curr_function is not None:
            for key, value in zip(self.app.d.console.function_keys[self.app.d.console.curr_function], self.d.function_args[self.app.d.console.curr_function]):
                string = re.sub(r'\b' + key + r'\b', value, string)

        string = string.strip()
        if string.startswith('*'):
            lid = len(self.d.loops)
            wait_for_thread = None
            wait_for = None
            if string.startswith('*!'):
                try:
                    sub = re.search('\d+', string)[0]
                except Exception as e:
                    print(f"empty wait for statement. {e}")
                    return False
                idd = int(sub)
                for i in self.app.workers:
                    if i.built and i.worker.hash == idd:
                        wait_for = i.worker
                        wait_for_thread = i
                        break
                else:
                    log('warn', f'no job with id {idd} found, to wait for.')
                substr = string[2 + len(sub):]
            else:
                substr = string[1:]

            self.d.loops.append(0)
            self.d.loops_ends.append(0)
            ind = 0
            while ind < len(self.app.lists[self.app.d.list.album].list):
                self.d.loops[lid] = ind
                self.d.loops_ends[lid] = len(self.app.lists[self.app.d.list.album].list) - 1
                self.selected = ind
                if wait_for is not None:
                    while wait_for_thread.is_alive() and len(wait_for.d.loops) >= lid and self.d.loops[lid] >= wait_for.d.loops[lid]:
                        ...
                res = self.console_execute_string(substr)
                if not res:
                    log('error', f'error in loop at index {ind}')
                    return False
                ind += 1
            try:
                self.d.loops.pop(lid)
                self.d.loops_ends.pop(lid)
                if len(self.d.loops) != lid:
                    log('error', 'loop count after end of loop is corrupted. (it is compiler error)')
                    return False
            except Exception as e:
                log('error', f'loop count after end of loop is corrupted. (it is compiler error) {e}')
                return False
            return True

        if string.startswith('%'):
            try:
                rng = string[1:string.find('%', 1)].split('-')
                end = string.find('%', 1)
                lid = len(self.d.loops)
                self.d.loops.append(0)
                self.d.loops_ends.append(0)
                self.d.loops_ends[lid] = int(rng[1])
                for i in range(int(rng[0]), int(rng[1]) + 1):
                    self.d.loops[lid] = i
                    if 0 <= int(i) < len(self.app.lists[self.app.d.list.album].list):
                        self.selected = i
                    res = self.console_execute_string(string[end + 1:])
                    if not res:
                        log('error', f'error in loop at index {i}')
                        return False
                try:
                    self.d.loops.pop(lid)
                    self.d.loops_ends.pop(lid)
                    if len(self.d.loops) != lid:
                        log('error', 'loop count after end of loop is corrupted. (it is compiler error)')
                        return False
                except Exception as e:
                    log('error', f'loop count after end of loop is corrupted. (it is compiler error) {e}')
                    return False
                return True
            except Exception as e:
                log('error', f'invalid loop syntax. ({e}) valid example: "%1-3% udpate"  (update tracks from 1 to 3 (including 3))')
                return False

        # ----------------- loops macro indexes
        for cc, r in enumerate(self.d.loops):
            v = len(self.d.loops) - cc  # 1 for last loop
            string = re.sub(rf'@{v}\b', f'{r}', string)

        if '|' in string:
            sa, sb = string.split('|', 1)
            res = self.console_execute_string(sa)
            if not res:
                log('error', f'error in loop in block "{sa}"')
                return False
            res = self.console_execute_string(sb)
            if not res:
                log('error', f'error in loop in block "{sb}"')
            return res

        if string.startswith('&'):
            x = string.find('(')
            y = string.find('{')
            if x != -1 and (x < y or y == -1):
                name = string[1:x].strip()
                if name not in self.app.d.console.functions:
                    log('error', f'Unknown function: {name}')
                    return False
                # set params
                params = list(filter(lambda x: x, map(str.strip, string[x + 1:string.rfind(')')].split(','))))
                if len(params) != len(self.app.d.console.function_keys[name]):
                    need_params = self.app.d.console.function_keys[name]
                    log('warn', f'number of given parameters for "{name}" is not equal to number of needed parameters need: ({", ".join(need_params)})')
                    return False
                if name in self.d.function_args:
                    log('warn', f'recursion is not allowed (even paired (a -> b -> a ...))')
                    return False
                else:
                    self.d.function_args[name] = params
                for i in self.app.d.console.functions[name]:
                    self.app.d.console.curr_function = name
                    res = self.console_execute_string(i)
                    if not res:
                        return False
                return True
            elif y != -1 and (y < x or x == -1):
                log('warn', 'for now, you can not declare function in another function. It may be can changed in future...')
                return False
            else:
                log('error', 'invalid syntax for function definition/call. must be & <name> (...) to call, and & <name> {...} to declare & <name> {>>  ...} to add comands to end')
                return False

        if string.startswith('(') and string.endswith(')'):
            res = self.console_execute_string(string[1:-1])
            if not res:
                log('error', 'error in braces.')
            return True

        return self.console_execute_command(string)

    def console_execute_command(self, string: str):
        if self.app.d.console.stop_execution:
            self.app.d.console.stop_execution = False
            log('error', 'execution stopped. (keyboard interrupt.)')
            return False
        r = tuple(map(str.strip, string.split(maxsplit=1)))
        if not r:
            return True
        if len(r) == 2:
            cmd, args = r
        else:
            cmd, args = r[0], ''

        if cmd in GLOBAL_FUNCTIONS:
            try:
                GLOBAL_FUNCTIONS[cmd](self, *shlex.split(args))
            except Exception as e:
                log('error', f"Error at run of cmd-let {cmd}: {e}")
        else:
            if '(' in string:
                string = '&' + string
                res = self.console_execute_string(string)
                if res:
                    return True
            log('error', f"Unknown cmd-let: {cmd}")# (so checked if it is function.)")
        return True


class Application:
    FOCUS_LEFT = 0
    FOCUS_RIGHT = 1

    def __init__(self):
        self.mode = MODE_EXPLORER
        self.focus = Application.FOCUS_LEFT
        self.d = jsd()

        self.lw = None
        self.rw = None
        self.w = None
        self.h = None
        self.spectrogram = True
        self.workers: [ExecutorThread] = []

        self.lists: [Album] = []

    def get_help(self, string):
        if not string:
            self.get_help('help')
            # add main help
            log('info', f'use "help <page number>"  tos how pages from 1 to {len(GLOBAL_HELP)}')
            return
        elif string.strip().isdigit():
            # add main help
            log('info', f'showing page {int(string)}/{len(GLOBAL_HELP)}')
            log('info', GLOBAL_HELP[int(string) - 1])
            return
        elif string in GLOBAL_FUNCTIONS_HELP:
            log('info', GLOBAL_FUNCTIONS_HELP[string])
        else:
            log('error', f'not found help for this function ({string})')
            s = '; '.join(sorted(GLOBAL_FUNCTIONS.keys()))
            log('error', f'all existing functions:\n{s}')
            s = '; '.join(sorted(GLOBAL_FUNCTIONS_HELP.keys()))
            log('error', f'all available functions:\n{s}')

    def to_visible(self, cy, x, l, r, h):
        if x - 5 < cy:
            cy = max(l, x - 5)
        if x > cy + h - 5:
            cy = min(r - 1, x - h + 5)
        return cy

    def log(self, string, level='info'):
        # add to explorer
        expstring = string.replace("\n", ' \\\\ ')
        self.d.explorer.message = f'{expstring}'[:self.w - 3]
        self.d.explorer.message_level = c.log[level]
        # add to console
        for i in string.split('\n'):
            while len(i) > self.lw - 3:
                ii = i[:self.lw - 3]
                i = i[self.lw - 3:]
                self.d.console.data.append((ii, c.log[level]))
            self.d.console.data.append((i, c.log[level]))
        while len(self.d.console.data) > self.d.console.height:
            self.d.console.data.pop(0)

    def list_jobs(self):
        for i in self.workers:
            wk = i.worker
            a = wk.d.loops[:]
            b = wk.d.loops_ends[:]
            lp = zip(a, b)
            lp = map(lambda x: f'{x[0]}/{x[1]}', lp)
            s1 = f'[{wk.hash:3}] fn={wk.d.curr_function} loop=[{",".join(lp)}] cmd=['
            ww = self.lw - 3 - 1 - len(s1)
            if ww < len(wk.command):
                s2 = f'{wk.command[:ww - 3] + "..."}]'
            else:
                s2 = wk.command + ']'
            log('info', s1 + s2)
            print()

    def autocomplete(self):
        try:
            s = self.d.console.string
            ss = s
            q = False
            if s.count('"') % 2 == 1:
                s += '"'
                q = True
            if s.count("'") % 2 == 1:
                s += "'"
                q = True
            sh = shlex.split(s)
            if len(sh) <= 1:
                return
            s = sh.pop()
            ss = ss[:ss.rfind(s)]
            if q:
                ss = ss[:-1]
            s += '*'
            if pathlib.Path(s).is_absolute():
                res = list(pathlib.Path(pathlib.Path(s).anchor).glob(str(pathlib.Path(s).relative_to(pathlib.Path(s).anchor))))
            else:
                res = list(pathlib.Path(self.d.path).glob(s))
            if not res:
                return
            if sh[0] in ('l', 'load'):
                res.sort(key=lambda x: (0, str(x).lower()) if x.is_file() else (1, str(x).lower()))
            elif sh[0] in ('cd',):
                res.sort(key=lambda x: (0, str(x).lower()) if x.is_dir() else (1, str(x).lower()))
            else:
                res.sort(key=lambda x: str(x).lower())
            try:
                sh = [str(res[0].relative_to(self.d.path))]
            except Exception as e:
                sh = [str(res[0])]
            self.d.console.autocompleted = True
            self.d.console.string = ss + shlex.join(sh)
        except Exception as e:
            log('error', f'happen error at autocomplete ({e})')

    def load_track(self, pattern):
        if os.path.isfile(os.path.join(self.d.path, pattern)):
            if self.d.list.album is not None:
                self.lists[self.d.list.album].add(os.path.join(self.d.path, pattern))
        else:
            if pathlib.Path(pattern).is_absolute():
                r = list(pathlib.Path(pathlib.Path(pattern).anchor).glob(str(path.relative_to(pathlib.Path(pattern).anchor))))
            else:
                r = list(pathlib.Path(self.d.path).glob(pattern))
            if not r:
                for ext in ('.mp3', '.waw', '.flac', '.ogg', '.mid'):
                    if pathlib.Path(pattern).is_absolute():
                        r += list(pathlib.Path(pathlib.Path(pattern).anchor).glob(str(path.relative_to(pathlib.Path(pattern).anchor)) + ext))
                    else:
                        r += list(pathlib.Path(self.d.path).glob(pattern + ext))
            for f in r:
                self.load_track(f)
            if not r:
                log('error', f'not found "{pattern}" file.')

    def draw(self):
        sc.clear()
        if self.mode == MODE_EXPLORER:
            self.draw_explorer()
        elif self.mode == MODE_CONSOLE:
            self.draw_console()

    def events(self):
        ## every state:
        self.d.console.height = self.h - 5
        self.lists[self.d.list.album].update()
        # update threads
        for i in range(len(self.workers) - 1, -1, -1):
            if not self.workers[i].is_alive():
                # process ends/
                res = self.workers[i].worker
                if not self.workers[i].result:
                    log('error', "Error happened at job, execution stopped.")
                else:
                    log('job', f'job [{res.hash}] finished.')
                self.workers[i].join()
                self.workers.pop(i)
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

    def draw_explorer(self):
        self.draw_explorer_list()
        self.draw_lists()
        sc.hline(self.h - 1, 0, '-', self.w)
        addstr(self.h - 1, 0, f'{self.d.explorer.message:{self.w}}', self.d.explorer.message_level)

    def draw_explorer_list(self):
        # draw background
        addstr(0, 1, self.d.path, c.path['focus' if self.focus == Application.FOCUS_LEFT else 'unfocus'])
        sc.hline(1, 0, '-', self.lw)
        # draw data
        for line, i in enumerate(self.d.listdir[self.d.explorer.cy[self.d.path]:self.d.explorer.cy[self.d.path] + self.h - 4]):
            line += self.d.explorer.cy[self.d.path]
            s = f'{i.name:{self.lw - 3}}'[:self.lw - 3]  # 3 chars of padding
            if i.type == 'file':
                color = select_color(c.file, self.focus == Application.FOCUS_LEFT, line == self.d.explorer.selected[self.d.path])
            else:
                color = select_color(c.directory, self.focus == Application.FOCUS_LEFT, line == self.d.explorer.selected[self.d.path])
            addstr(2 + line - self.d.explorer.cy[self.d.path], 3, s, color)

    def events_explorer(self, key):
        if self.focus == Application.FOCUS_LEFT:
            self.events_explorer_list(key)
        else:
            self.events_lists_list(key)

    def events_explorer_list(self, key):
        if key == curses.KEY_UP:
            if self.d.explorer.selected[self.d.path] is None and self.d.listdir:
                self.d.explorer.selected[self.d.path] = len(self.d.listdir) - 1
            self.d.explorer.selected[self.d.path] -= 1
            if self.d.explorer.selected[self.d.path] < 0:
                self.d.explorer.selected[self.d.path] = 0
            self.d.explorer.cy[self.d.path] = self.to_visible(self.d.explorer.cy[self.d.path], self.d.explorer.selected[self.d.path], 0, len(self.d.listdir), self.h - 3)
        elif key == curses.KEY_DOWN:
            if self.d.explorer.selected[self.d.path] is None and self.d.listdir:
                self.d.explorer.selected[self.d.path] = 0
            self.d.explorer.selected[self.d.path] += 1
            if self.d.explorer.selected[self.d.path] > len(self.d.listdir) - 1:
                self.d.explorer.selected[self.d.path] = len(self.d.listdir) - 1
            self.d.explorer.cy[self.d.path] = self.to_visible(self.d.explorer.cy[self.d.path], self.d.explorer.selected[self.d.path], 0, len(self.d.listdir), self.h - 3)
        elif key == ord('\n'):  # curses.KEY_ENTER:
            if self.d.listdir[self.d.explorer.selected[self.d.path]].type == 'directory':
                if self.d.explorer.selected[self.d.path] is not None:
                    if os.path.isdir(os.path.join(self.d.path, self.d.listdir[self.d.explorer.selected[self.d.path]].name)):
                        self.d.path = os.path.abspath(os.path.normpath(os.path.join(self.d.path, self.d.listdir[self.d.explorer.selected[self.d.path]].name)))
                        self.listdir()
            else:
                if os.path.isfile(os.path.join(self.d.path, self.d.listdir[self.d.explorer.selected[self.d.path]].name)):
                    self.load_track(os.path.join(self.d.path, self.d.listdir[self.d.explorer.selected[self.d.path]].name))
        elif key == ord('\b'):  # curses.KEY_BACKSPACE:
            if os.path.isdir(os.path.join(self.d.path, '..')):
                self.d.path = os.path.abspath(os.path.normpath(os.path.join(self.d.path, '..')))
                self.listdir()
        elif key == ord('e') or key == ord('у'):
            self.mode = MODE_CONSOLE

    def draw_console(self):
        self.draw_console_list()
        self.draw_lists()

    def events_console(self, key):
        if self.focus == Application.FOCUS_LEFT:
            self.events_console_list(key)
        else:
            self.events_lists_list(key)

    def draw_console_list(self):
        # draw background
        addstr(0, 1, self.d.path, c.path['focus' if self.focus == Application.FOCUS_LEFT else 'unfocus'])
        sc.hline(1, 0, '-', self.lw)
        sc.vline(0, 1, '|', self.h)
        # draw data
        for line, i in enumerate(self.d.console.data):
            line += self.d.console.height - len(self.d.console.data)
            text, color = i
            addstr(2 + line, 2, text, color)
        addstr(self.h - 3, 2, "MP> " + self.d.console.string, c.console.text)

    def events_console_list(self, key):
        if key == 27:  # curses.KEY_ESCAPE
            self.mode = MODE_EXPLORER
        if key == ord('\b'):
            self.d.console.string = self.d.console.string[:-1]
        if key == curses.KEY_UP:
            if self.d.console.history:
                if self.d.console.history_position == 0:
                    self.d.console.string_saved = self.d.console.string
                self.d.console.string = self.d.console.history[self.d.console.history_position]
                self.d.console.history_position += 1
                if self.d.console.history_position > len(self.d.console.history) - 1:
                    self.d.console.history_position = len(self.d.console.history) - 1
        if key == curses.KEY_DOWN:
            if self.d.console.history:
                self.d.console.string = self.d.console.history[self.d.console.history_position]
                self.d.console.history_position -= 1
                if self.d.console.history_position < 0:
                    self.d.console.string = self.d.console.string_saved
                    self.d.console.history_position = 0
        if key == 0:
            self.d.console.string += '}'
        if key == 460:
            self.d.console.string += '"'
        if key == 530:
            self.d.console.string += "'"
        if key in range(0x110000) and chr(key) in literals.printable:
            s = chr(key)
            if s == '\n':
                # execute
                log('text', 'MP> ' + self.d.console.string)
                th = ExecutorThread(target=Executor,
                                    args=(self, self.d.console.string, self.d.list.selected[self.d.list.album]),
                                    daemon=True)
                self.d.console.history_position = 0
                self.d.console.history.insert(0, self.d.console.string)
                while len(self.d.console.history) > self.d.console.history_length:
                    self.d.console.history.pop()
                self.d.console.string = ''
                self.d.console.string_saved = ''

                self.workers.append(th)
                th.start()
            elif s == '\t':
                self.autocomplete()
            else:
                # insert character
                if (chr(key) == '\\' or chr(key) == '/') and self.d.console.autocompleted and self.d.console.string.rstrip()[-1] in ("'", '"'):
                    # if autocompleted, it can remove last quote.
                    self.d.console.string = self.d.console.string.rstrip()[:-1] + chr(key)
                else:
                    self.d.console.string += chr(key)
        while self.d.console.string and len(self.d.console.string) > self.lw - 6:
            log("warn", "too long string.")
            self.d.console.string = self.d.console.string[:-1]

    def clear_spectrogram(self):
        self.d.spectrogram.prev_pos = -1
        self.d.spectrogram.samples = None
        self.d.spectrogram.track_id = None
        self.d.spectrogram.last_maximum = 0.0
        self.d.spectrogram.last_maximum_position = 0
        self.d.spectrogram.music_avr_value = 0.0

    def get_spectrogram(self, track, position):
        # get need samples
        margin = self.d.spectrogram.margin
        width = self.d.spectrogram.width + 2 * margin

        samples = track.array[position - margin:position + width]
        samples = samples.astype(numpy.float32)

        if len(samples.shape) == 2:
            samples = samples[:, 0] + samples[:, 1]
        samples.resize(width)
        samples -= np.average(samples)

        # now, process fft
        samples = np.fft.fft(samples)

        # filter them

        samples = np.abs(samples[:width//2])  # + np.abs(samples[width//2:])

        samples = samples[int(width // 2 * self.d.spectrogram.remove_low_part):int(width // 2 * (1 - self.d.spectrogram.remove_high_part))]

        self.d.spectrogram.prev_pos = position
        self.d.spectrogram.samples = samples

        return samples

    def draw_spectrogram(self):
        track = self.lists[self.d.list.album].curr
        progress = self.lists[self.d.list.album].get_progress()

        position = int(progress[0] * track.freq)
        if self.d.spectrogram.track_id is None or self.d.spectrogram.track_id != id(track) or position < self.d.spectrogram.prev_pos:
            self.clear_spectrogram()  # it will set samples to None
            self.d.spectrogram.track_id = id(track)
        if self.d.spectrogram.samples is None or self.d.spectrogram.prev_pos + self.d.spectrogram.width < position:
            sp = self.get_spectrogram(track, position)
        else:
            sp = self.d.spectrogram.samples

        # generate data
        mdd = 0
        pmd = self.d.spectrogram.last_maximum # _decrease
        data = []
        avrd = []
        if not self.lists[self.d.list.album].paused:
            t = self.d.spectrogram.width / position if position else 1.0
            z = np.sort(sp)[::-1]
            self.d.spectrogram.music_avr_value = np.average(z[:z.shape[0] // 5]) * 1.5 * t + self.d.spectrogram.music_avr_value * (1 - t)
        for i in range(self.rw):
            s = i / self.rw
            ss = (i + 1) / self.rw
            if self.d.spectrogram.grid_power > 1.0:
                s = (pow(self.d.spectrogram.grid_power, s) - 1) / (self.d.spectrogram.grid_power - 1)
                ss = (pow(self.d.spectrogram.grid_power, ss) - 1) / (self.d.spectrogram.grid_power - 1)
            s = int(s * sp.shape[0])
            ss = int(ss * sp.shape[0])
            ss = max(s + 1, ss)
            val = np.sum(sp[s:ss])
            mdd = max(mdd, val)
            data.append(val)
            aval = np.average(sp[s:ss])
            avrd.append(aval)
        if mdd > pmd:
            self.d.spectrogram.last_maximum = mdd
            self.d.spectrogram.last_maximum_position = position
        else:
            if not self.lists[self.d.list.album].paused:
                t = pow(1.0 - self.d.spectrogram.last_maximum_decrease, (position - self.d.spectrogram.last_maximum_position) / track.freq)
                self.d.spectrogram.last_maximum = t * self.d.spectrogram.last_maximum + (1 - t) * mdd
            mdd = self.d.spectrogram.last_maximum
        if mdd > 0.0001:
            for i in range(len(data)):
                data[i] /= mdd
        # draw sp
        text = [[" " for x in range(self.rw - 1)] for y in range(self.d.spectrogram.height)]
        if self.d.spectrogram.colory:
            color = [0 for x in range(self.rw - 1)]
        for i in range(self.rw - 1):
            # get value to this column
            if self.d.spectrogram.colory:
                t = min(1.0, avrd[i] / self.d.spectrogram.music_avr_value)
                color[i] = int(t * COL_SPECTROGRAM_STEPS + 0.5)
            ch, s = generate_column(data[i], self.d.spectrogram.height)
            # set text
            for y in range(self.d.spectrogram.height):
                if y < ch:
                    text[y][i] = '█'
                elif y == ch:
                    text[y][i] = s

        if self.d.spectrogram.colory:
            t = 0
            for y in range(len(text)):
                for x in range(len(text[y])):
                    addch(self.h - 9 - y, self.lw + 1 + x, text[y][x], C_SPECTROGRAM + color[x])
        else:
            ss = list(map(lambda x: ''.join(x), text))
            for i in range(len(ss)):
                addstr(self.h - 9 - i, self.lw + 1, ss[i], c.base)

    def draw_lists(self):
        sc.vline(0, self.lw, '|', self.h)

        # -------------------- header
        x = 0
        if self.d.list.album != 0:
            addstr(0, self.lw + 1, '<', c.base)
        for it, i in enumerate(self.lists[self.d.list.album:]):
            it += self.d.list.album
            hs = f"|{i.name}|"[:self.rw - x - 2]
            addstr(0, self.lw + 2 + x, hs, select_color(c.album.header, self.focus == Application.FOCUS_RIGHT, self.d.list.album == it))
            x += len(hs) - 1
        sc.hline(1, self.lw, '-', self.rw)

        # -------------------- content
        a = self.lists[self.d.list.album]
        for line, i in enumerate(a[self.d.list.cy[self.d.list.album]:self.d.list.cy[self.d.list.album] + self.h - 9 - (self.d.spectrogram.height if self.spectrogram else 0)]):
            line += self.d.list.cy[self.d.list.album]
            s = f'{i.info.title:{self.rw - 3}}'[:self.rw - 3]  # 3 chars of padding
            if a.playing == line:
                color = select_color(c.album.music.playing, self.focus == Application.FOCUS_RIGHT, line == self.d.list.selected[self.d.list.album])
            else:
                color = select_color(c.album.music.wait, self.focus == Application.FOCUS_RIGHT, line == self.d.list.selected[self.d.list.album])
            addstr(2 + line - self.d.list.cy[self.d.list.album], self.lw + 3, s, color)

        # -------------------- playing
        track = self.lists[self.d.list.album].curr
        if track is not None:
            progress = self.lists[self.d.list.album].get_progress()
            progress = [progress[0], progress[1], progress[0] / progress[1]]
            # h - 9
            s = f'{f"{hhmmss(progress[0], progress[1])} / {hhmmss(progress[1], progress[1]):}":^{self.rw - 1}}'[:self.rw - 1]
            addstr(self.h - 9 - (self.d.spectrogram.height if self.spectrogram else 0), self.lw + 1, s, c.info['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            if self.spectrogram and track is not None:
                self.draw_spectrogram()
            l, ch = generate_bar(progress[2], self.rw - 1)
            s = " " * l
            ss = " " * (self.rw - 2 - l)
            if ch:
                addch(self.h - 8, self.lw + 1 + l, ch, c.info.timeline['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
                addch(self.h - 7, self.lw + 1 + l, ch, c.info.timeline['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            addstr(self.h - 8, self.lw + 1, s, c.info.timeline.full['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            addstr(self.h - 7, self.lw + 1, s, c.info.timeline.full['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            addstr(self.h - 8, self.lw + 2 + l, ss, c.info.timeline.empty['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            addstr(self.h - 7, self.lw + 2 + l, ss, c.info.timeline.empty['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            s = f'{track.info.title:^{self.rw - 1}}'[:self.rw - 1]
            addstr(self.h - 6, self.lw + 1, s, c.info.name['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            s = f'{f"album: {track.info.album}":^{self.rw - 1}}'[:self.rw - 1]
            addstr(self.h - 5, self.lw + 1, s, c.info['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            s = f'{f"artist: {track.info.artist}":^{self.rw - 1}}'[:self.rw - 1]
            addstr(self.h - 4, self.lw + 1, s, c.info['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            s = f'{f"autor: {track.info.autor}":^{self.rw - 1}}'[:self.rw - 1]
            addstr(self.h - 3, self.lw + 1, s, c.info['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            s = f'{f"content: {track.info.content}":^{self.rw - 1}}'[:self.rw - 1]
            addstr(self.h - 2, self.lw + 1, s, c.info['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
        else:
            s = f'{"- / -":^{self.rw - 1}}'[:self.rw - 1]
            addstr(self.h - 9 - (5 if self.spectrogram else 0), self.lw + 1, s, c.info['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            s = ''.join(('X', ' ')[x % 2] for x in range(self.rw))
            addstr(self.h - 8, self.lw + 1, s[:-1], c.info.timeline['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            addstr(self.h - 7, self.lw + 1, s[1:],  c.info.timeline['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            s = f'{"No Track":^{self.rw - 1}}'[:self.rw - 1]
            addstr(self.h - 6, self.lw + 1, s, c.info.name['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            s = f'{"No Track":^{self.rw - 1}}'[:self.rw - 1]
            addstr(self.h - 5, self.lw + 1, s, c.info['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            s = f'{"No Track":^{self.rw - 1}}'[:self.rw - 1]
            addstr(self.h - 4, self.lw + 1, s, c.info['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            s = f'{"No Track":^{self.rw - 1}}'[:self.rw - 1]
            addstr(self.h - 3, self.lw + 1, s, c.info['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])
            s = f'{"No Track":^{self.rw - 1}}'[:self.rw - 1]
            addstr(self.h - 2, self.lw + 1, s, c.info['focus' if self.focus == Application.FOCUS_RIGHT else 'unfocus'])

        # -------------------- spectrogram

    def lists_selection_move_up(self):
        if self.d.list.selected[self.d.list.album] is None and self.lists[self.d.list.album].list:
            self.d.list.selected[self.d.list.album] = len(self.lists[self.d.list.album].list) - 1
        self.d.list.selected[self.d.list.album] -= 1
        if self.d.list.selected[self.d.list.album] < 0:
            self.d.list.selected[self.d.list.album] = 0
        self.d.list.cy[self.d.list.album] = self.to_visible(self.d.list.cy[self.d.list.album], self.d.list.selected[self.d.list.album], 0, len(self.lists[self.d.list.album].list), self.h - 3 - 9 - (self.d.spectrogram.height if self.spectrogram else 0))

    def lists_selection_move_down(self):
        if self.d.list.selected[self.d.list.album] is None and self.lists[self.d.list.album].list:
            self.d.list.selected[self.d.list.album] = 0
        self.d.list.selected[self.d.list.album] += 1
        if self.d.list.selected[self.d.list.album] > len(self.lists[self.d.list.album].list) - 1:
            self.d.list.selected[self.d.list.album] = len(self.lists[self.d.list.album].list) - 1
        self.d.list.cy[self.d.list.album] = self.to_visible(self.d.list.cy[self.d.list.album], self.d.list.selected[self.d.list.album], 0, len(self.lists[self.d.list.album].list), self.h - 3 - 9 - (self.d.spectrogram.height if self.spectrogram else 0))

    def events_lists_list(self, key):
        if key == curses.KEY_UP:
            self.lists_selection_move_up()
        elif key == curses.KEY_DOWN:
            self.lists_selection_move_down()
        elif key == ord('\n'):  # curses.KEY_ENTER:
            if 0 <= self.d.list.selected[self.d.list.album] < len(self.lists[self.d.list.album].list):
                self.lists[self.d.list.album].play_from(self.d.list.selected[self.d.list.album])
            self.clear_spectrogram()
        elif key == ord(' '):  # curses.KEY_SPACE:
            self.lists[self.d.list.album].pause_or_unpause()
        elif key == ord('w') or key == ord('ц'):
            if 0 <= self.d.list.selected[self.d.list.album] < len(self.lists[self.d.list.album].list):
                self.lists[self.d.list.album].move_up(self.d.list.selected[self.d.list.album])
                self.lists_selection_move_up()
        elif key == ord('s') or key == ord('ы'):
            if 0 <= self.d.list.selected[self.d.list.album] < len(self.lists[self.d.list.album].list):
                self.lists[self.d.list.album].move_down(self.d.list.selected[self.d.list.album])
                self.lists_selection_move_down()

    def listdir(self):
        a = os.listdir(self.d.path)
        l = []
        for i in a:
            if os.path.isfile(os.path.join(self.d.path, i)):
                l.append(jsd({'name': i, 'type': 'file'}))
            else:  # directory
                l.append(jsd({'name': i, 'type': 'directory'}))
        l.sort(key=lambda x: (x.type == 'file', x.name.lower()))
        l.insert(0, jsd(name='.', type='directory'))
        l.insert(1, jsd(name='..', type='directory'))
        self.d.listdir = l

    def resize(self):
        self.h, self.w = sc.getmaxyx()

        self.lw = self.w // 2
        self.rw = self.w - self.lw

    def run(self, screen: curses.window):
        global sc, lsc, rsc
        # curses.beep()
        sc = screen
        self.h, self.w = sc.getmaxyx()
        sc.nodelay(True)
        curses.curs_set(False)
        os.environ.setdefault('ESCDELAY', '0')
        init_colors()

        self.lw = self.w // 2
        self.rw = self.w - self.lw
        lsc = sc.subwin(self.h, self.lw, 0, 0)
        rsc = sc.subwin(self.h, self.rw, 0, self.lw)

        # ---- set self.d
        self.d.path = os.path.abspath(os.path.normpath(os.getcwd()))
        self.d.explorer = jsd(
            selected=defaultdict(lambda: 1),
            cy=defaultdict(int),
            message='',
            message_level=c.log.info,
        )
        self.d.list = jsd(
            album=0,
            selected=defaultdict(int),
            cy=defaultdict(int),
        )
        self.lists.append(Album())
        self.d.spectrogram = jsd(
            prev_pos=-1,
            samples=None,
            width=1024 * 4,
            margin=1024 * 4,
            height=5,  # of spectrogram at display
            track_id=None,
            remove_low_part=0.001,
            remove_high_part=0.5,  # high part + low part must be less than 1
            grid_power=10.0,  # must be 1 or greater. 1 - no changes, 2,3,4.5... - logarithmic scale of frequencies
            last_maximum_decrease=0.001,  # percent of decrease per second (multiplicative)
            colory=True,
            last_maximum=0.0,
            last_maximum_position=0,
            music_avr_value=0.0,
        )
        self.d.console = jsd(
            data=[],
            string="",
            string_saved="",
            autocompleted=False,
            height=1,
            stop_execution=False,
            input_function=None,
            functions=defaultdict(list),
            loops=[],
            function_args={},
            function_keys={},
            curr_function=None,
            history=[],
            history_length=100,
            history_position=0,
        )

        lib_linkage()

        x = music_gen.TrackProject(climplib.kernel)
        x.run()
        x.create('m')
        self.lists[self.d.list.album].add(x.x.sound)
        x = music_gen.TrackProject(climplib.kernel)
        x.create('t')
        self.lists[self.d.list.album].add(x.x.sound)


        self.listdir()

        while True:
            self.resize()
            self.draw()
            self.events()


lsc: None | curses.window = None
rsc: None | curses.window = None
sc: None | curses.window = None
c = jsd({
    'base': 0,
    'path': jsd({
        'unfocus': 1,
        'focus': 2,
    }),
    'file': jsd({
        'unfocus': jsd({
            'unselected': 3,
            'selected': 4,
        }),
        'focus': jsd({
            'unselected': 5,
            'selected': 6,
        }),
    }),
    'directory': jsd({
        'unfocus': jsd({
            'unselected': 7,
            'selected': 8,
        }),
        'focus': jsd({
            'unselected': 9,
            'selected': 10,
        }),
    }),
    'log': jsd({
        'text': 11,
        'info': 12,
        'warn': 13,
        'error': 14,
        'job': 38,
    }),
    'album': jsd({
        'header': jsd({
            'unfocus': jsd({
                'unselected': 15,
                'selected': 16,
            }),
            'focus': jsd({
                'unselected': 17,
                'selected': 18,
            }),
        }),
        'music': jsd({
            'playing': jsd({
                'unfocus': jsd({
                    'unselected': 19,
                    'selected': 20,
                }),
                'focus': jsd({
                    'unselected': 21,
                    'selected': 22,
                }),
            }),
            'wait': jsd({
                'unfocus': jsd({
                    'unselected': 23,
                    'selected': 24,
                }),
                'focus': jsd({
                    'unselected': 25,
                    'selected': 26,
                }),
            }),
        }),
    }),
    'info': jsd({
        'unfocus': 27,
        'focus': 28,
        'name': jsd({
            'unfocus': 29,
            'focus': 30,
        }),
        'timeline': jsd({
            'unfocus': 31,
            'focus': 32,
            'full': jsd({
                'unfocus': 33,
                'focus': 34,
            }),
            'empty': jsd({
                'unfocus': 35,
                'focus': 36,
            }),
        }),
    }),
    'console': jsd({
        'text': 37,
    }),
    'gen': jsd({
        'text': 39,
        'note': jsd({
            'a': 40,
            'b': 41,
            'selected': 42,
        }),
        'timeline': 43,
    })
})
#    END INDEX IS 39, at 'gen/text'

climplib = None
C_SPECTROGRAM = None
COL_SPECTROGRAM = None
COL_SPECTROGRAM_STEPS = None
COLOR_LIGHT_GREY = 9
COLOR_DARK_GREY = 10


def init_colors():
    global C_SPECTROGRAM, COL_SPECTROGRAM, COL_SPECTROGRAM_STEPS, COLOR_LIGHT_GREY
    COL_SPECTROGRAM = max(8, curses.COLORS - 65)
    C_SPECTROGRAM = max(8, curses.COLOR_PAIRS - 65)
    if curses.COLORS - COL_SPECTROGRAM > 0:
        COL_SPECTROGRAM_STEPS = n = min(curses.COLORS - COL_SPECTROGRAM - 1, curses.COLOR_PAIRS - C_SPECTROGRAM - 1)
        for i in range(n + 1):
            if i == n:
                r = 1000
                g = 600
                b = 0
            else:
                r = 1000 * (i + 1) // n
                g = int(1000 - 500 * (i / n)**0.5)
                b = int(400 - 300 * (i / n)**0.5)
            curses.init_color(COL_SPECTROGRAM + i, r, g, b)
        for i in range(n + 1):
            curses.init_pair(C_SPECTROGRAM + i, COL_SPECTROGRAM + i, curses.COLOR_BLACK)

    curses.init_color(COLOR_LIGHT_GREY, 600, 600, 600)
    curses.init_color(COLOR_DARK_GREY, 300, 300, 300)

    curses.init_pair(c.path.unfocus, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(c.path.focus,   curses.COLOR_BLACK, curses.COLOR_BLUE)
    curses.init_pair(c.file.unfocus.unselected, curses.COLOR_WHITE,  curses.COLOR_BLACK)
    curses.init_pair(c.file.unfocus.selected,   curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(c.file.focus.unselected,   curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(c.file.focus.selected,     curses.COLOR_BLACK,  curses.COLOR_YELLOW)
    curses.init_pair(c.directory.unfocus.unselected, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(c.directory.unfocus.selected,   curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(c.directory.focus.unselected,   curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(c.directory.focus.selected,     curses.COLOR_BLACK, curses.COLOR_GREEN)
    curses.init_pair(c.log.text,  curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(c.log.info,  curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(c.log.warn,  curses.COLOR_YELLOW,   curses.COLOR_BLACK)
    curses.init_pair(c.log.error, curses.COLOR_RED,   curses.COLOR_BLACK)
    curses.init_pair(c.log.job,   COLOR_DARK_GREY,   curses.COLOR_BLACK)
    curses.init_pair(c.album.header.unfocus.unselected, curses.COLOR_YELLOW, curses.COLOR_WHITE)
    curses.init_pair(c.album.header.unfocus.selected,   curses.COLOR_BLACK,  curses.COLOR_WHITE)
    curses.init_pair(c.album.header.focus.unselected,   curses.COLOR_BLACK,  curses.COLOR_WHITE)
    curses.init_pair(c.album.header.focus.selected,     curses.COLOR_BLACK,  curses.COLOR_BLUE)
    curses.init_pair(c.album.music.wait.unfocus.unselected, curses.COLOR_WHITE,  curses.COLOR_BLACK)
    curses.init_pair(c.album.music.wait.unfocus.selected,   curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(c.album.music.wait.focus.unselected,   curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(c.album.music.wait.focus.selected,     curses.COLOR_BLACK,  curses.COLOR_YELLOW)
    curses.init_pair(c.album.music.playing.unfocus.unselected, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(c.album.music.playing.unfocus.selected,   curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(c.album.music.playing.focus.unselected,   curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(c.album.music.playing.focus.selected,     curses.COLOR_WHITE,   curses.COLOR_MAGENTA)
    curses.init_pair(c.info.unfocus, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(c.info.focus,   curses.COLOR_BLACK, curses.COLOR_GREEN)
    curses.init_pair(c.info.name.unfocus, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(c.info.name.focus,   curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(c.info.timeline.unfocus, curses.COLOR_BLUE, COLOR_LIGHT_GREY)
    curses.init_pair(c.info.timeline.focus,   curses.COLOR_BLUE, COLOR_LIGHT_GREY)
    curses.init_pair(c.info.timeline.full.unfocus, curses.COLOR_BLUE, curses.COLOR_BLUE)
    curses.init_pair(c.info.timeline.full.focus,   curses.COLOR_BLUE, curses.COLOR_BLUE)
    curses.init_pair(c.info.timeline.empty.unfocus, COLOR_LIGHT_GREY, COLOR_LIGHT_GREY)
    curses.init_pair(c.info.timeline.empty.focus,   COLOR_LIGHT_GREY, COLOR_LIGHT_GREY)
    curses.init_pair(c.console.text, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(c.gen.text, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(c.gen.note.a, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(c.gen.note.b, curses.COLOR_BLACK, COLOR_LIGHT_GREY)
    curses.init_pair(c.gen.note.selected, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(c.gen.timeline, curses.COLOR_BLACK, curses.COLOR_YELLOW)



GLOBAL_HELP = [""" GLOBAL HELP :: PAGE 1 :: basics
    --------- LANGUAGE SPECIFIC
    it is two main states of program:  
        * selected track
        * current path
    with path all is similar as in shell:
        you have commands cd, dir, load
        (see help on them by enter 'help <command name>')
    selected track displayed as yellow line in right part.
        it is track, with which many commands will work.
        for example, command speedup (used for change temp) changes temp
        of selected music.

        you can select track by 'select <track index / track name(may be unsupported)>'.

        also, loops change current selected track, you can learn about them at third page.
""",
               """ GLOBAL HELP :: PAGE 2 :: commands
                   there is many commands, divided into groups:
                   (for each function you can see help by 'help <function name>')
               
                   * current playing music manipulation
                       functions 'from' 'play' 'stop' 'pause'/'p' 'next'/'n'
               
                   * album changing:
                       functions 'shuffle' 'del' 'select'
               
                   * path change & loading
                       functions 'cd' 'dir' 'load'/'l'
               
                   * change music (filters, etc.)
                       ...
               
                   * console manipulations
                       function 'print'    
               
                   * exit :)
                       function 'exit'
               """,
               """ GLOBAL HELP :: PAGE 3 :: join commands, loops
                   join commands: 
                       you can use | for join commands together
               
                       EXAMPLE:
               
                           1. print hello
                           2. exit
                         is equal to
                           1. print hello | exit 
               
                   loops: 
                       you can execute loop with 2 variants:
                           * <command>  -> executes command for every track (select it, and execute command)
                           %<a>-<b>% <command>  -> executes loop from <a> to (including) <b>, select this value, and execute command.
                       you can get loop index, by write
                           @<num>, where num is id of loop (in reverse order, @1 means last loop)
               
                       EXAMPLE:
                           1. * print @1   -> prints list from 0 to length of album - 1
               
                           1. %1-5%%1-6% print @1 @2   -> prints 30 lines ('0 0', '1 0', '2 0' ...)
                                                       ! @1 means second loop (1-6), because it is last loop.
                                                         to get first loop value, used @2 (because it is second loop from top)
               
                           1. %1-5% get-temp | reverse-temp -> execute block of 2 commands for id from 1 to 5
               """]

GLOBAL_FUNCTIONS_HELP = {
    'print': """ Help on function "print":
        arg list: 
            *args   -> any strings to print
        print all args, joined by space.""",
    'next': """ Help on function "next":
        arg list: 
            [int steps=1]   -> default 1, count of 'next' steps 
        play next music (as then current ends), 
        repeat this 'steps' times.

        This command has alias: 'n'.""",
    'from': """ Help on function "from":
        arg list: 
            [int id=current_selected_track]   -> default to current selected track, index of first track to be played 
        play music from index id.""",
    'select': """ Help on function "select":
        arg list: 
            [int id=current_playing_music]   -> default to current track playing, index of track to select 
        selects track with given id""",
    'replay': """ Help on function "replay":
        arg list: 
            None 
        start playing that track, which is already playing now
        (replay it)""",
    'pause': """ Help on function "pause":
        arg list: 
            None 
        pause/unpause current playing music

        This command has alias: 'p'.""",
    'stop': """ Help on function "stop":
        arg list: 
            None 
        stops playing music""",
    'play': """ Help on function "play":
        arg list: 
            None 
        starts playing music""",
    'shuffle': """ Help on function "shuffle":
        arg list: 
            None 
        shuffle all music, playing track places in first position.""",
    'cd': """ Help on function "cd":
        arg list: 
            string path 
        changes path to new (may be relative). 
        You can use autofill by pressing TAB key""",
    'dir': """ Help on function "dir":
        arg list: 
            None
        displays content of current path directory""",
    'load': """ Help on function "load":
        arg list: 
            string template
        loads all music which pass template.
        you can use templates, like in command shell ('ab*c?.txt')
        load can automatically add extensions
        you can write 'abc' and it will load 'abc.mp3'
        displays content of current path directory
        ! load will pause current music, while it will be loading new.

        This command has alias: 'l'.""",
    'del': """ Help on function "del":
        arg list: 
            int id
        deletes music with index id from playlist.""",
    'l': """ Help on function "l":
        it is alias to 'load'""",
    'p': """ Help on function "p":
        it is alias to 'pause'""",
    'n': """ Help on function "n":
        it is alias to 'next'""",
    'exit': """ Help on function "exit":
        arg list: 
            int return_code
        exit from application with return_code.""",
    'help': """ Help on function "help":
        arg list: 
            [string info=None]
        displays help for command-lets,
        with no arguments, displays main help,
        with argument, displays help for given function (command-let).""",
}

GLOBAL_FUNCTIONS = {
    'print': lambda self, *args: log('info', ' '.join(args)),
    'next': lambda self, int_steps=1: [self.app.lists[self.app.d.list.album].play_next() for i in range(int(int_steps))],
    'from': lambda self, int_id=None: self.app.lists[self.app.d.list.album].play_from(
        self.app.d.list.selected[self.app.d.list.album] if int_id is None else int(int_id)),
    'select': lambda self, int_id=None: (self.app.d.list.selected.__setitem__(self.app.d.list.album,
                                                                              self.app.lists[self.app.d.list.album].playing if int_id is None else int(
                                                                                  int_id)) if int_id is None or 0 <= int(int_id) < len(
        self.app.lists[self.app.d.list.album].list) else log('warn', 'value is out of bounds.')),
    'replay': lambda self: self.app.lists[self.app.d.list.album].play_from(self.app.lists[self.app.d.list.album].playing),
    'pause': lambda self: self.app.lists[self.app.d.list.album].pause_or_unpause(),
    'stop': lambda self: self.app.lists[self.app.d.list.album].stop(),
    'play': lambda self: self.app.lists[self.app.d.list.album].play(),
    'shuffle': lambda self: self.app.lists[self.app.d.list.album].shuffle(),
    'cd': lambda self, string: (self.app.d.__setitem__('path', os.path.normpath(os.path.join(self.app.d.path, string))), self.app.listdir()) if os.path.isdir(
        os.path.join(self.app.d.path, string)) else log('error', 'no such directory. (use dir to see scope)'),
    'dir': lambda self: [log('info', i.name) for i in self.app.d.listdir],
    'load': lambda self, string: self.app.load_track(string),
    'del': lambda self, int_id=None: self.app.lists[self.app.d.list.album].remove(
        self.app.lists[self.app.d.list.album].playing if int_id is None else int(int_id)),
    'jobs': lambda self: self.app.list_jobs(),
    'wait': lambda self, wait_time: time.sleep(float(wait_time)),
    'l': lambda *args: GLOBAL_FUNCTIONS['load'](*args),  # alias for load
    'p': lambda *args: GLOBAL_FUNCTIONS['pause'](*args),  # alias for pause
    'n': lambda *args: GLOBAL_FUNCTIONS['next'](*args),  # alias for next
    'exit': lambda self, code=0: (curses.endwin(), exit(code)),
    'help': lambda self, string="": self.app.get_help(string),
}


def gen_f(function_import):
    return lambda self, *args: log('warn', f'skip cmd-let {function_import} because current music is None.') \
        if self.selected is None \
        else music_class.FUNCTIONS[function_import](self, self.app.lists[self.app.d.list.album].list[self.selected], *args)
for function_import in music_class.FUNCTIONS:
    GLOBAL_FUNCTIONS[function_import] = gen_f(function_import)



if __name__ == "__main__":

    climplib = ctypes.cdll.LoadLibrary(r"D:\C\git\climp\bin\Windows\climp.dll")  # './bin/Windows/climp.dll'
    climplib.kernel.argtypes = [
        np.ctypeslib.ndpointer(dtype=np.float32, ndim=1, flags='C_CONTIGUOUS'),  # res
        ctypes.c_size_t,
        np.ctypeslib.ndpointer(dtype=np.float32, ndim=2, flags='C_CONTIGUOUS'),  # notes
        np.ctypeslib.ndpointer(dtype=np.int32, ndim=1, flags='C_CONTIGUOUS'),  # tools
        np.ctypeslib.ndpointer(dtype=np.int32, ndim=1, flags='C_CONTIGUOUS'),  # start
        ctypes.c_size_t,
        ctypes.c_int32,
    ]
    climplib.kernel.restype = ctypes.c_int
    app = Application()
    curses.wrapper(app.run)
