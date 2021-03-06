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
from os import walk, makedirs, remove, rename
import sys, traceback, errno, signal
from handbrake import AudioStream, HandbrakeProcess, HandbrakeOutputParser
from threading import Thread
from tools import getbitrate
from Queue import Queue, Empty
from ask.ask import Ask
from ask.question import Choices, YesNo, Text, Path, Float
from tools import getbpf
from os.path import expanduser

class Preference:
    """
    A Preference object stores parsed preferences from xml preset file.
    Those preferences define for example which language (audio and srt) you want to keep
    in the resulting video file.
    """
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
    """
    An Option object stores options from xml preset file.
    Options are parameters passed to HandbrakeCLI.
    """
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
    """
    Represents preset.xml as an object
    """
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
                handle_ask(q['args'], q['f'], q['dest'], q['hop'], q['preset'])
                Worker.questions_queue.task_done()
            except Empty:
                pass

    @staticmethod
    def rip_worker():
        while not Worker.finished:
            try:
                task = Worker.rip_queue.get(True, 3)
                try:
                    task.rip()
                    Worker.rip_queue.task_done()
                    delete_from_file(task.filepath)
                except KeyboardInterrupt:
                    Worker.finished = True
                    Worker.rip_queue.task_done()
                    with Worker.rip_queue.mutex:
                        Worker.rip_queue.queue.clear()
                        Worker.rip_queue.all_tasks_done.notify_all()
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
    """
    This class stores all questions that the app can ask.
    """
    ask_srt_yn = YesNo('Would you like to add a subtitle track ?', lambda a: Q.ask_srt if a.lower() == 'y' else False)
    ask_srt_yn_bis = YesNo('Would you like to add another subtitle track ?', lambda a: Q.ask_srt if a.lower() == 'y' else False)
    ask_srt = Path('Path of subtitles file :')
    ask_bpf = Float('Bits*(pixels/frame) can\'t be calculated, please choose a value manually :')

class Answers:
    """
    Stores answer to the questions ask to the user.
    """
    def __init__(self):
        self.subtitles_path = []
        self.bpf = None

def loadpreset():
    preset = Preset()
    tree = ET.parse(path.join(path.dirname(__file__), 'presets/default.xml'))
    root = tree.getroot()
    for child in root.findall('options/option'):
        preset.addoption(Option(child.get('key'), child.get('value'), child.get('handler')))
    for child in root.findall('preferences/option'):
        '''other = {}
        if child.get('keepforced') is not None:
            other['keepforced'] = child.get('keepforced')'''
        preset.addpreference(Preference(child.get('key'), child.get('required', False), child.get('multivalued', False), child.get('separator'), child.get('value')))
    return preset

def get_restore_filepath():
    home = expanduser("~")
    filedir = path.join(home, '.config', 'rippy')
    try:
        makedirs(filedir)
    except OSError as exc:
        if exc.errno == errno.EEXIST and path.isdir(filedir):
            pass
        else: raise
    return path.join(filedir, 'last.state')

def save_file_list(filelist):
    filepath = get_restore_filepath()
    with open(filepath, 'w') as fhandler:
        for onefile in filelist:
            fhandler.write(onefile + '\n')

def delete_from_file(deletefile):
    filepath = get_restore_filepath()
    filepathtmp = filepath + '.tmp'
    if path.isfile(filepath):
        with open(filepathtmp, 'w') as writehandler:
            with open(filepath, 'r') as readhandler:
                for line in readhandler:
                    if line != deletefile:
                        writehandler.write(line)
    remove(filepath)
    rename(filepathtmp, filepath)

def get_restored_files():
    filepath = get_restore_filepath()
    if path.isfile(filepath):
        with open(filepath, 'r') as readhandler:
            for line in readhandler:
                yield line.strip()

def handle(args, preset):
    """
    Called by main
    """
    Worker.launch()
    files = []
    if args.restore:
        files = get_restored_files()
    else:
        files = args.files
        save_file_list(files)

    for f in scan(files):
        hp = HandbrakeProcess(f)
        hp.scan()
        hop = HandbrakeOutputParser(hp.buf)
        hop.parse()
        try:
            width = hop.video().width
            height = hop.video().height
            bitrate = getbitrate(width, height, hop.fps)
        except:
            sys.stderr.write(f+'\n')
            traceback.print_exc(file=sys.stderr)
        if args.summary:
            audio_streams, subtitle_streams = get_prefered(hop, preset)
            hop.summary(audio_streams, subtitle_streams)
        else:
            Worker.questions_queue.put({'f': f, 'dest': args.dest, 'hop': hop, 'preset': preset, 'args': args})
    try:
        Worker.rip_queue.join()
        Worker.setfinished(True)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Aborting.")


def handle_ask(args, f, dest, hop, preset):
    """
    Handles question asking and answering.
    All questions are queued and asked one at a time.
    """
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
    handle_rip(args, f, dest, hop, preset, answers)

def getnewfilepath(dest, filepath):
    """
    Compute the new path for current file
    """
    if dest is None:
        dest = path.join(path.dirname(filepath), 'NEW')
    filename = path.basename(filepath)
    if '.' in filename and filename.rsplit('.', 1)[1].lower() in ['mkv']:
        return path.join(dest, filename)
    else: #BluRay folder
        filename = path.basename(path.dirname(filepath))
        return path.join(dest, filename+'.mkv')

def get_prefered(hop, preset):
    prefered_audio = preset.getpreference('audio-language')
    prefered_codec = preset.getpreference('audio-codec')
    prefered_sub = preset.getpreference('subtitle-language')
    audio_streams = {}
    subtitle_streams = []
    
    def getindex(elt, elts):
        i = 0
        ret = None
        for c in elts:
            if elt.lower() == c.lower():
                return i
            elif elt.lower().startswith(c.lower()):
                ret = i
            i += 1
        return ret
    
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

    return audio_streams, subtitle_streams
  

def handle_rip(args, filepath, dest, hop, preset, answers=None):
    """
    Handles ripping with HandbrakeCLI with the help of a queue.
    """
    bpf = answers.bpf if answers is not None else None
    proc = HandbrakeProcess(filepath)
    audio_streams, subtitle_streams = get_prefered(hop, preset)
    
    bitrate = getbitrate(hop.video().width, hop.video().height, hop.video().fps, bpf)
    proc.setaudio([audio.position for audio in audio_streams.values()])
    proc.setsubtitle([sub.position for sub in subtitle_streams])
    if answers is not None:
        proc.setsrtfile(answers.subtitles_path)
    proc.setoutput(getnewfilepath(dest, filepath))
    proc.setbitrate(bitrate)
    proc.settitle(hop.title)
    # Sample generation if necessary
    if args.sample:
        proc.setoption('start-at', 'duration:%d' % args.startfrom)
        proc.setoption('stop-at', 'duration:%d' % (args.startfrom + 30))
    for k, v in preset.getoptions():
        proc.setoption(k, v)
    Worker.rip_queue.put(proc)


def scan(files):
    """
    Yields all files to be ripped !
    """
    for f in files:
        absfile = path.abspath(f)
        if path.isdir(absfile):
            for root, dirs, files in walk(absfile):
                for name in files:
                    if '.' in name and name.rsplit('.', 1)[1].lower() in ['mkv']:
                        yield path.join(root, name)
                if 'BDMV' in (adir.upper() for adir in dirs): # BluRay folder
                    yield(root)
                if 'VIDEO_TS.BUP' in (afile.upper() for afile in files): # DVD folder
                    yield(root)
        else:
            yield absfile

def main():
    parser = ArgumentParser(description="Rippy")
    parser.add_argument("-d", "--dest", dest='dest', help='Folder where ripped files will be stored')
    parser.add_argument("--sample", dest='sample', help='Only generates 30s samples', action="store_true", default=False)
    parser.add_argument("--from", dest='startfrom', default=300, help='When does the 30s sample should start in secondes (default: 300)', type=int)
    parser.add_argument("files", nargs='*', help='List of files or folders that will be ripped recursively')
    parser.add_argument("-r", "--restore", action='store_true', dest='restore', help='Will rip files that have not been ripped the last time')
    parser.add_argument("--summary", action='store_true', dest='summary', help='Print a summary the operations, then exits')
    parser.set_defaults(func=handle)
    args = parser.parse_args()
    if not args.restore and len(args.files) == 0:
        parser.error('At least -r option or one file must be specified')
    preset = loadpreset()
    args.func(args, preset)

if __name__ == '__main__':
    main()
