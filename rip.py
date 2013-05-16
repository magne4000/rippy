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

class Parameter:
    def __init__(self, key, required=False, multivalued=False, separator=','):
        self.key = key
        self.required = required
        self.multivalued = multivalued
        self.separator = separator 

class Preference(Parameter):
    def __init__(self, key, required=False, multivalued=False, separator=',', value=None):
        Parameter.__init__(self, key, required, multivalued, separator)
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
        self.parameters = []
        self.preferences = {}

    def addoption(self, opt):
        self.options.append(opt)
    
    def addparameter(self, param):
        self.parameters.append(param)

    def addpreference(self, pref):
        self.preferences[pref.key] = pref.getvalue()

    def getparameters(self):
        for p in self.parameters:
            yield p.key, p.getvalue()
    
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
                print("Empty q")

    @staticmethod
    def rip_worker():
        while not Worker.finished:
            try:
                task = Worker.rip_queue.get(True, 3)
                task.rip()
                Worker.rip_queue.task_done()
            except Empty:
                print("Empty rip")

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

def loadpreset():
    preset = Preset()
    tree = ET.parse('presets/default.xml')
    root = tree.getroot()
    for child in root.findall('options/option'):
        preset.addoption(Option(child.get('key'), child.get('value'), child.get('handler')))
    for child in root.findall('parameters/option'):
        preset.addparameter(Parameter(child.get('key'), child.get('required', False), child.get('multivalued', False), child.get('separator')))
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
        handle_ask(hop, preset)
        try:
            width = hop.video().width
            height = hop.video().height
            bitrate = getbitrate(width, height, hop.fps)
            print(width, height, bitrate, hop.fps)
        except:
            sys.stderr.write(f+'\n')
            traceback.print_exc(file=sys.stderr)
        print(f)
        handle_rip(hop)
    Worker.setfinished(True)

def handle_ask(hop, preset):
    print(preset.getpreference('audio-language'))

def handle_rip(hop):
    pass

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
