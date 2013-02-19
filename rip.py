#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Distributed under terms of the MIT license.

"""
Wrapper using HandBrackeCli with custom presets.
The app contains a default preset which allows HandBrakeCli
to generate lightweight x264 HD Videos (720p/1080p) without quality loss.
"""

import xml.etree.ElementTree as ET

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
        if child.get('key') == 'bpf':
            other['bpf'] = {}
            for subchild in child:
                other['bpf'][subchild.get('width')] = subchild.get('value')
        preset.addparameter(Parameter(child.get('key'), child.get('required', False), child.get('multivalued', False), child.get('separator'), other))
    return preset

def main():
    preset = loadpreset()
    for k, v in preset.getoptions():
        print k, v


if __name__ == '__main__':
    main()
