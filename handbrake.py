#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Distributed under terms of the MIT license.

import re
from subprocess import Popen, PIPE
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

    def getposition(self):
        """Get the position of the stream in the container"""
        pass

    def isdefault(self):
        """docstring for isdefault"""
        pass

class AudioStream(Stream):

    re_parse = re.compile("Stream #0\.(?P<position>\d)(?:\((?P<language>.{3})\))?: \w+: (?P<codec>\w+)(?: \((?P<codecdetail>.*?)\))?, (?P<frequency>\d+) Hz, (?P<channels>\d(?:\.\d)?).*, .*?, (?P<bitrate>\d+).{1,5}(?: \((?P<default>default)\))?")
    re_parse2 = re.compile("Stream #0\.(?P<position>\d)(?:\((?P<language>.{3})\))?: \w+: (?P<codec>\w+)")
    positions = []

    def parse(self):
        matches = AudioStream.re_parse.search(self.buf)
        if matches is not None:
            results = matches.groupdict()
            self.language = results['language']
            self.default = True if results['default'] is not None else False
            self.channels = results['channels']
            if results['codec'] == 'dca': #DTS
                self.codec = results['codecdetail']
            else:
                self.codec = results['codec']
            self.frequency = results['frequency']
            self.position = results['position']
            self.bitrate = results['bitrate']
        else:
            matches = AudioStream.re_parse2.search(self.buf)
            results = matches.groupdict()
            self.language = results['language']
            self.codec = results['codec']
            self.position = results['position']
        AudioStream.positions.append(self.position)
        AudioStream.positions.sort()

    def getposition(self):
        return AudioStream.positions.index(self.position)

class VideoStream(Stream):

    re_parse = re.compile("Stream #0\.(?P<position>\d)(?:\((?P<language>.{3})\))?: \w+: (?P<codec>\w+)(?: \((?P<codecdetail>.*?)\))?,.* (?P<width>\d+)x(?P<height>\d+).*, .* tbc(?: \((?P<default>default)\))?")
    re_parse_fps = re.compile("(\d+(?:\.\d+)) fps")

    def parse(self):
        matches = VideoStream.re_parse.search(self.buf)
        if matches is not None:
            results = matches.groupdict()
            self.language = results['language']
            self.default = True if results['default'] is not None else False
            self.codec = results['codec']
            self.position = results['position']
            self.width = results['width']
            self.height = results['height']
            match_fps = VideoStream.re_parse_fps.search(self.buf)
            if match_fps is not None:
                self.fps = match_fps.group(1)
            else:
                self.fps = None

class SubtitleStream(Stream):

    re_parse = re.compile("Stream #0\.(?P<position>\d)(?:\((?P<language>.{3})\))?: \w+: (?:.*\((?P<forced>forced)\))?")
    positions = []

    def parse(self):
        matches = SubtitleStream.re_parse.search(self.buf)
        if matches is not None:
            results = matches.groupdict()
            self.forced = True if results['forced'] is not None else False
            self.language = results['language']
            self.position = results['position']
            SubtitleStream.positions.append(self.position)
            SubtitleStream.positions.sort()
        
    def getposition(self):
        return SubtitleStream.positions.index(self.position)

class HandbrakeOutputParser:
    
    re_duration = re.compile('Duration: (?P<duration>.*?), .*')
    re_fps = re.compile("\+ size.* (?P<fps>\d+(?:\.\d+)?)")

    def __init__(self, buf):
        self.buf = buf
        self.streams = {'audio': [], 'video': None, 'subtitle': []}
        self.duration = None
        self.fps = None

    def parse(self):
        for line in self.buf.split('\n'):
            if 'Audio: ' in line:
                stream = AudioStream(line)
                stream.parse()
                self.streams['audio'].append(stream)
            elif 'Video: ' in line:
                stream = VideoStream(line)
                stream.parse()
                self.streams['video'] = stream
                if self.fps is None:
                    self.fps = stream.fps
            elif 'Subtitle: ' in line:
                stream = SubtitleStream(line)
                stream.parse()
                self.streams['subtitle'].append(stream)
            elif 'Duration: ' in line:
                matches = HandbrakeOutputParser.re_duration.search(line)
                if matches is not None:
                    self.duration = intduration(matches.groupdict()['duration'])
            elif '+ size: ' in line:
                matches = HandbrakeOutputParser.re_fps.search(line)
                if matches is not None:
                    self.fps = matches.groupdict()['fps']

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

    def scan(self):
        self.buf = self._call([HandbrakeProcess.handbrakecli, "--scan", "--input", self.filepath])

    def rip(self, args):
        self._call([HandbrakeProcess.handbrakecli, "--input", self.filepath].extends(args))

    def _call(self, args):
        child = Popen(args, stderr=PIPE)
        child.wait()
        return child.stderr.read()
