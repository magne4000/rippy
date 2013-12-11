#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Distributed under terms of the MIT license.

import re
import time
import sys
from subprocess import Popen, PIPE
from threading import Thread
from tools import intduration, non_block_read
from ask.ask import Ask

class Stream:
    """
    Abstract class representing a video-file stream
    """
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
    """
    An audio stream representation
    """
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
    """
    A video stream representation
    """
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
    """
    A subtitle stream representation
    """
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
    """
    Parse the output of HanbrakeCLI
    """
    re_duration = re.compile('Duration: (?P<duration>.*?), .*')
    re_title = re.compile("\+ title (\d+)")

    def __init__(self, buf):
        self.buf = buf
        self.streams = {'audio': [], 'video': None, 'subtitle': []}
        self.duration = None
        self.fps = None
        self.title = None

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
            elif line.startswith('+ title'):
                matches = HandbrakeOutputParser.re_title.search(line)
                if matches is not None:
                    self.title = matches.group(1)


    def audio(self):
        return self.streams['audio']

    def video(self):
        return self.streams['video']

    def subtitle(self):
        return self.streams['subtitle']

class HandbrakeProcess:
    """
    Handles HanbrakeCLI process
    """

    handbrakecli = "/usr/bin/HandBrakeCLI"
    default_args = [handbrakecli]
    NO_VALUE = -1

    def __init__(self, filepath):
        self.filepath = filepath
        self.buf = None
        self.args = {
            'audio': None, # Multivalued, separated by comma
            'subtitle': None, # Multivalued, separated by comma
            'srt-file': None, # Multivalued, separated by comma
            'output': None, 
            'vb': None,
            'title': None,
            'input': self.filepath 
        }

    def setoption(self, k, v):
        if k is not None:
            if v is None:
                self.args[k] = HandbrakeProcess.NO_VALUE
            else:
                self.args[k] = v

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
            self.args['vb'] = b

    def settitle(self, t):
        if t is not None:
            self.args['title'] = t

    def _getargs(self):
        arr = []
        for k, v in self.args.items():
            if v is not None and len(str(v)) > 0:
                arr.append("--"+k)
                if v != HandbrakeProcess.NO_VALUE:
                    arr.append(str(v))
        return arr

    def _ripbuf(self, stdout):
        while True:
            # Progress output eg. "Encoding: task 1 of 2, 0.01 %"
            output = non_block_read(stdout).strip()
            if (output):
                Ask._print(output, True)
            time.sleep(1)


    def scan(self):
        arr = list(HandbrakeProcess.default_args)
        arr.extend(["--scan", "--title", "0", "--min-duration", "600", "--input", self.filepath])
        self.buf = self._call(arr)

    def rip(self):
        arr = list(HandbrakeProcess.default_args)
        arr.extend(self._getargs())
        self._call(arr, handle_stdout=self._ripbuf)

    def _call(self, args, handle_stdout=None, handle_stderr=None):
        child = Popen(args, stderr=PIPE, stdout=PIPE)
        threads = []
        if handle_stdout is not None:
            t = Thread(target=handle_stdout, args=[child.stdout])
            threads.append(t)
            t.daemon = True
            t.start()
        if handle_stderr is not None:
            t = Thread(target=handle_stderr, args=[child.stderr])
            threads.append(t)
            t.daemon = True
            t.start()
        child.wait()
        for t in threads:
            t.join(timeout=1)
        return child.stderr.read()

