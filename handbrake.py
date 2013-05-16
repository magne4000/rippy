#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Distributed under terms of the MIT license.

import re
from subprocess import Popen, PIPE
from threading import Thread
from tools import intduration

class Stream:
    
    def __init__(self, buf):
        self.buf = buf
        self.parse()

    def parse(self):
        """Must be overhidden by subclasses"""
        pass

    def getlanguage(self):
        pass

    def isdefault(self):
        """docstring for isdefault"""
        pass

class AudioStream(Stream):

    re_parse = re.compile("\+\s(?P<position>\d+).*?\((?P<codec>.*?)\)\s\((?P<channels>\d(?:\.\d))\sch\)\s\(.*?\:\s(?P<language>\w+)\)(:?,\s(?P<frequency>\d+)Hz,\s(?P<bitrate>\d+)bps)?")

    def parse(self):
        matches = AudioStream.re_parse.search(self.buf)
        if matches is not None:
            results = matches.groupdict()
            self.language = results['language']
            self.channels = results['channels']
            self.codec = results['codec']
            self.frequency = results['frequency']
            self.position = results['position']
            self.bitrate = results['bitrate']
            return True
        return False
        
class VideoStream(Stream):

    re_parse = re.compile("\+ size:\s(?P<width>\d+)x(?P<height>\d+).*?(?P<fps>\d+(?:\.\d+)?) fps")

    def parse(self):
        matches = VideoStream.re_parse.search(self.buf)
        if matches is not None:
            results = matches.groupdict()
            self.width = results['width']
            self.height = results['height']
            self.fps = results['fps']
            self.ratio = round(float(self.width)/float(self.height))
            return True
        return False

class SubtitleStream(Stream):

    re_parse = re.compile("\+\s(?P<position>\d+).*?\(.*?\:\s(?P<language>\w+)\).*\((?P<encoding>.+)\)")

    def parse(self):
        matches = SubtitleStream.re_parse.search(self.buf)
        if matches is not None:
            results = matches.groupdict()
            self.language = results['language']
            self.position = results['position']
            self.encoding = results['encoding']
            return True
        return False
        
class HandbrakeOutputParser:
    
    re_duration = re.compile('Duration: (?P<duration>.*?), .*')

    def __init__(self, buf):
        self.buf = buf
        self.streams = {'audio': [], 'video': None, 'subtitle': []}
        self.duration = None
        self.fps = None

    def parse(self):
        block = None
        for line in self.buf.split('\n'):
            if 'audio tracks:' in line:
                block = 'Audio'
            elif 'subtitle tracks:' in line:
                block = 'Subtitle'
            elif line.startswith('  +'):
                block = None
            if block == 'Audio':
                stream = AudioStream(line)
                if stream.parse():
                    self.streams['audio'].append(stream)
            elif block == 'Subtitle':
                stream = SubtitleStream(line)
                if stream.parse():
                    self.streams['subtitle'].append(stream)
            elif 'size: ' in line:
                stream = VideoStream(line)
                if stream.parse():
                    self.streams['video'] = stream
                    if self.fps is None:
                        self.fps = stream.fps
            elif 'duration: ' in line:
                matches = HandbrakeOutputParser.re_duration.search(line)
                if matches is not None:
                    self.duration = intduration(matches.groupdict()['duration'])

    def audio(self):
        return self.streams['audio']

    def video(self):
        return self.streams['video']

    def subtitle(self):
        return self.streams['subtitle']

class HandbrakeProcess:

    handbrakecli = "/usr/bin/HandBrakeCLI"

    def __init__(self, filepath):
        self.filepath = filepath
        self.buf = None
        self.args = {
            'audio': None, # Multivalued, separated by comma
            'subtitle': None, # Multivalued, separated by comma
            'srt-file': None, # Multivalued, separated by comma
            'output': None, 
            'bitrate': None,
            'input': self.filepath 
        }

    def setaudio(self, l):
        if l is not None:
            self.args['audio'] = ','.join(l)
    
    def setsubtitle(self, l):
        if l is not None:
            self.args['subtitle'] = ','.join(l)

    def setsrtfile(self, l):
        if l is not None:
            self.args['srt-file'] = ','.join(l)

    def setoutput(self, o):
        if o is not None:
            self.args['output'] = o
    
    def setbitrate(self, b):
        if b is not None:
            self.args['bitrate'] = b

    def _getargs(self):
        arr = []
        for k, v in self.args.items():
            if v is not None and len(v) > 0:
                arr.append("--"+k)
                arr.append(v)
        return arr

    def scan(self):
        self.buf = self._call([HandbrakeProcess.handbrakecli, "--scan", "--title", "0", "--min-duration", "600", "--input", self.filepath])

    def rip(self):
        self._call([HandbrakeProcess.handbrakecli].extends(self._getargs()))

    def _call(self, args):
        child = Popen(args, stderr=PIPE)
        child.wait()
        return child.stderr.read()

