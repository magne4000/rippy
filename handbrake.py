#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Distributed under terms of the MIT license.

import re, time, sys
from os import path
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
    re_parse = re.compile("\+\s(?P<position>\d+).*?\((?P<codec>.*?)\)\s\((?P<type>.*?)\)\s\(.*?\:\s(?P<language>\w+)\)(:?,\s(?P<frequency>\d+)Hz,\s(?P<bitrate>\d+)bps)?")

    def parse(self):
        matches = AudioStream.re_parse.search(self.buf)
        if matches is not None:
            results = matches.groupdict()
            self.language = results['language']
            self.type = results['type']
            self.codec = results['codec']
            self.frequency = results['frequency']
            self.position = results['position']
            self.bitrate = results['bitrate']
            return True
        return False

    def __str__(self):
        return 'AudioStream #%s (language: %s) (type: %s) (codec: %s) (frequency: %s) (bitrate: %s)' %\
            (self.position, self.language, self.type, self.codec, self.frequency, self.bitrate)
        
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
    
    def __str__(self):
        return 'VideoStream (width: %s) (height: %s) (FPS: %s) (ratio: %s)' %\
            (self.width, self.height, self.fps, self.ratio)

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
    
    def __str__(self):
        return 'SubtitleStream #%s (language: %s) (encoding: %s)' %\
            (self.position, self.language, self.encoding)
        
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

    def summary(self, p_audio_streams, p_sub_streams):
        print('* %s' % self.streams['video'])
        for x in self.streams['audio']:
            sformat = '  %s'
            if x.position in [audio.position for audio in p_audio_streams.values()]:
                sformat = '* %s'
            print(sformat % x)
        for x in self.streams['subtitle']:
            sformat = '  %s'
            if x.position in [sub.position for sub in p_sub_streams]:
                sformat = '* %s'
            print(sformat % x)
        print('Duration : %s' % self.duration)
        print('FPS : %s' % self.fps)
        print('Title : %s' % self.title)

    def parse(self):
        block = None
        intitle = False
        for line in self.buf.split('\n'):
            if line.startswith('+ title'):
                if intitle:
                    """
                    second video track, we just need the first one, so we can exit parse.
                    TODO: When multiple video tracks are available, ask the user to choose one.
                    """
                    return
                matches = HandbrakeOutputParser.re_title.search(line)
                if matches is not None:
                    intitle = True
                    self.title = matches.group(1)
            if intitle:
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
    """
    Handles HanbrakeCLI process
    """

    handbrakecli = "/usr/bin/HandBrakeCLI"
    default_args = [handbrakecli]
    NO_VALUE = -1

    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = path.basename(filepath)
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

    def _printbuf(self, stdout):
        while True:
            # Progress output eg. "Encoding: task 1 of 2, 0.01 %"
            output = non_block_read(stdout).strip()
            if (output):
                Ask._print(self.filename + ': ' + output.splitlines()[-1], False)
            time.sleep(1)

    def scan(self):
        arr = list(HandbrakeProcess.default_args)
        arr.extend(["--scan", "--title", "0", "--min-duration", "700", "--input", self.filepath])
        self.buf = self._call(arr)

    def rip(self):
        arr = list(HandbrakeProcess.default_args)
        arr.extend(self._getargs())
        self._call(arr, handle_stdout=self._printbuf)

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
        if "--scan" not in args: # If ripping 
            if "Signal 2 received, terminating" in child.stderr.read(): # If process received CTRL+C
                raise KeyboardInterrupt
        return child.stderr.read()

