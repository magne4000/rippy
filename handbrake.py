#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Distributed under terms of the MIT license.

import re

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

    def parse(self):
        """docstring for parse"""
        pass

    def getcodec(self):
        pass

    def getfrequency(self):
        """docstring for getfrequency"""
        pass

    def getchannels(self):
        """docstring for getchannels"""
        pass

    def getbitrate(self):
        """docstring for getbitrate"""
        pass

class VideoStream(Stream):

    re_parse = re.compile("Stream #0\.(?P<position>\d)(?:\((?P<language>.{3})\))?: \w+: (?P<codec>\w+)(?: \((?P<codecdetail>.*?)\))?, \w+, (?P<width>\d+)x(?P<height>\d+).*, (?P<fps>\d+(?:\.\d+)?) fps,.* tbc(?: \((?P<default>default)\))?")

    def getcodec(self):
        pass

    def getresolution(self):
        pass

    def getfps(self):
        """docstring for getfps"""
        pass

    def getratio(self):
        """docstring for getratio"""
        pass

class SubtitleStream(Stream):

    def isforced(self):
        pass

class HandbrakeOutputParser:

    def __init__(self, buf):
        self.buf = buf

    def getduration(self):
        pass

    def getstreams(self):
        pass

    def getbitrate(self):
        """docstring for getbitrate"""
        pass
