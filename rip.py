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
from tools import getbitrate

class Parameter:
    def __init__(self, key, required=False, multivalued=False, separator=',', other=None):
        self.key = key
        self.required = required
        self.multivalued = multivalued
        self.separator = separator 
        self.other = other
        self.value = None

    def getvalue(self):
        if self.multivalued:
            self.separator.join(self.value)
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
        self.preferences[pref.key] = pref

    def getparameters(self):
        for p in self.parameters:
            yield p.key, p.getvalue()
    
    def getoptions(self):
        for o in self.options:
            yield o.key, o.getvalue()

    def getpreference(self, key):
        return self.preferences[key]

def loadpreset():
    preset = Preset()
    tree = ET.parse('presets/default.xml')
    root = tree.getroot()
    for child in root.findall('options/option'):
        preset.addoption(Option(child.get('key'), child.get('value'), child.get('handler')))
    for child in root.findall('parameters/option'):
        preset.addparameter(Parameter(child.get('key'), child.get('required', False), child.get('multivalued', False), child.get('separator')))
    for child in root.findall('preferences/option'):
        other = {}
        if child.get('keepforced') is not None:
            other['keepforced'] = child.get('keepforced')
        preset.addpreference(Parameter(child.get('key'), child.get('required', False), child.get('multivalued', False), child.get('separator'), other))
    return preset

def handle(args, preset):
    for f in scan(args.files):
        hp = HandbrakeProcess(f)
        hp.scan()
        hop = HandbrakeOutputParser(hp.buf)
        hop.parse()
        try:
            width = hop.video().width
            height = hop.video().height
            bitrate = getbitrate(width, height, hop.fps)
            print(width, height, bitrate, hop.fps)
        except:
            sys.stderr.write(f+'\n')
            traceback.print_exc(file=sys.stderr)
        print(f)

def scan(files):
    """ TODO
    Handle Bluray folders
    """
    for f in files:
        absfile = path.abspath(f)
        if path.isdir(absfile):
            for root, dirs, files in walk(absfile):
                for name in files:
                    if name.rsplit('.', 1)[1].lower() in ['mkv']:
                        yield path.join(root, name)
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
