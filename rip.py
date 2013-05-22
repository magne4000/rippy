#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Distributed under terms of the MIT license.

"""
Wrapper using HandBrackeCli with custom presets.
The app contains a default preset which allows HandBrakeCli
to generate lightweight x264 HD Videos (720p/1080p) without quality loss.
"""

from argparse import ArgumentParser
import xml.etree.ElementTree as ET
import os.path as path
from os import walk
import sys, traceback
from handbrake import AudioStream, HandbrakeProcess, HandbrakeOutputParser
from threading import Thread
from tools import getbitrate
from Queue import Queue, Empty
from ask.ask import Ask
from ask.question import Choices, YesNo, Text, Path
from tools import getbpf

class Preference:
    def __init__(self, key, required=False, multivalued=False, separator=',', value=None):
        self.key = key
        self.required = required
        self.multivalued = multivalued
        self.separator = separator 
        self.value = value

    def getvalue(self):
        if self.multivalued and self.value is not None:
           return self.value.split(self.separator)
        return self.value

class Option:
    def __init__(self, key, value=None, handler=None):
        self.key = key
        self.value = value
        self.handler = handler

    def getvalue(self):
        if self.handler is not None:
            if self.handler in locals():
                return locals()[self.handler]()
            else:
                raise Exception('Handler "' + self.handler + '" has not been defined')
        return self.value

class Preset:
    def __init__(self):
        self.options = []
        self.preferences = {}

    def addoption(self, opt):
        self.options.append(opt)
    
    def addpreference(self, pref):
        self.preferences[pref.key] = pref.getvalue()

    def getoptions(self):
        for o in self.options:
            yield o.key, o.getvalue()

    def getpreference(self, key):
        return self.preferences[key]

class Worker:

    questions_queue = Queue()
    rip_queue = Queue()
    finished = False

    @staticmethod
    def q_worker():
        while not Worker.finished:
            try:
                q = Worker.questions_queue.get(True, 3)
                q.ask()
                Worker.questions_queue.task_done()
            except Empty:
                pass

    @staticmethod
    def rip_worker():
        while not Worker.finished:
            try:
                task = Worker.rip_queue.get(True, 3)
                task.rip()
                Worker.rip_queue.task_done()
            except Empty:
                pass

    @staticmethod
    def launch():
        t_rip = Thread(target=Worker.rip_worker)
        t_rip.start()
        t_q = Thread(target=Worker.q_worker)
        t_q.start()

    @staticmethod
    def setfinished(b):
        Worker.finished = b

class Q:
    ask_srt_yn = YesNo('Would you like to add a subtitle track ?', lambda a: Q.ask_srt if a.lower() == 'y' else False)
    ask_srt_yn_bis = YesNo('Would you like to add another subtitle track ?', lambda a: Q.ask_srt if a.lower() == 'y' else False)
    ask_srt = Path('Path of subtitles file :')
    ask_bpf = Text('Bits*(pixels/frame) can\'t be calculated, please choose a value manually :')

class Answers:

    def __init__(self):
        self.subtitles_path = []
        self.bpf = None

def loadpreset():
    preset = Preset()
    tree = ET.parse('presets/default.xml')
    root = tree.getroot()
    for child in root.findall('options/option'):
        preset.addoption(Option(child.get('key'), child.get('value'), child.get('handler')))
    for child in root.findall('preferences/option'):
        '''other = {}
        if child.get('keepforced') is not None:
            other['keepforced'] = child.get('keepforced')'''
        preset.addpreference(Preference(child.get('key'), child.get('required', False), child.get('multivalued', False), child.get('separator'), child.get('value')))
    return preset

def handle(args, preset):
    Worker.launch()
    for f in scan(args.files):
        hp = HandbrakeProcess(f)
        hp.scan()
        hop = HandbrakeOutputParser(hp.buf)
        hop.parse()
        answers = handle_ask(hop, preset)
        try:
            width = hop.video().width
            height = hop.video().height
            bitrate = getbitrate(width, height, hop.fps)
            print(width, height, bitrate, hop.fps)
        except:
            sys.stderr.write(f+'\n')
            traceback.print_exc(file=sys.stderr)
        print(f)
        #TODO bouger autre part (a gérer par ask)
        handle_rip(f, hop, preset, answers)
    Worker.rip_queue.join()
    Worker.setfinished(True)

def handle_ask(hop, preset):
    answers = Answers()
    ''' subtitles '''
    prefered_sub = preset.getpreference('subtitle-language')
    prefered_sub_present = prefered_sub[0] in [sub.language for sub in hop.subtitle()]
    if not prefered_sub_present:
        a = Ask()
        answer = a.ask(Q.ask_srt_yn)
        while answer:
            answers.subtitles_path.append(answer)
            answer = a.ask(Q.ask_srt_yn_bis)
    ''' bpf '''
    if getbpf(hop.video().width) is None:
        a = Ask()
        answers.bpf = a.ask(Q.ask_bpf)
    return answers

def handle_rip(filepath, hop, preset, answers):
    prefered_audio = preset.getpreference('audio-language')
    prefered_codec = preset.getpreference('audio-codec')
    prefered_sub = preset.getpreference('subtitle-language')
    audio_streams = {}
    subtitle_streams = []
    proc = HandbrakeProcess(filepath)
    
    def getindex(elt, elts):
        i = 0
        for c in elts:
            if elt.lower().startswith(c.lower()):
                return i
            i += 1
        return None
    
    ''' audio '''
    for audio in hop.audio():
        if audio.language.lower() in prefered_audio:
            if audio.language in audio_streams:
                for codec in prefered_codec:
                    if getindex(codec, prefered_codec) < getindex(audio_streams[audio.language].codec, prefered_codec):
                        audio_streams[audio.language] = audio
            else:
                audio_streams[audio.language] = audio
    ''' subtitles '''
    for sub in hop.subtitle():
        if sub.language in prefered_sub:
            subtitle_streams.append(sub)
    
    bitrate = getbitrate(hop.video().width, hop.video().height, hop.video().fps, answers.bpf)
    proc.setaudio([audio.position for audio in audio_streams.values()])
    proc.setsubtitle([sub.position for sub in subtitle_streams])
    proc.setsrtfile(answers.subtitles_path)
    proc.setoutput(filepath + '.new.mkv') #TODO
    proc.setbitrate(bitrate)
    proc.settitle(hop.title)
    Worker.rip_queue.put(proc)


def scan(files):
    for f in files:
        absfile = path.abspath(f)
        if path.isdir(absfile):
            for root, dirs, files in walk(absfile):
                for name in files:
                    if '.' in name and name.rsplit('.', 1)[1].lower() in ['mkv']:
                        yield path.join(root, name)
                if 'BDMV' in dirs: # BluRay folder
                    yield(root)
        else:
            yield absfile

def main():
    parser = ArgumentParser(description="Rippy")
    parser.add_argument("-d", "--dest", dest='dest', help='Folder where ripped files will be stored')
    parser.add_argument("files", nargs='+', help='List of files or folders that will be ripped recursively')
    parser.set_defaults(func=handle)
    preset = loadpreset()
    args = parser.parse_args()
    args.func(args, preset)

if __name__ == '__main__':
    main()
