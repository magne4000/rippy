#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Distributed under terms of the MIT license.
import fcntl
import os
import sys

def non_block_read(output):
    """read output (stdout or stderr), non-blocking way"""
    fd = output.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    try:
        return output.read()
    except:
        return ''

def intduration(duration):
    """convert hh:mm:ss to integer"""
    hh, mm, ss, = duration.split(':')
    return int(hh) * 3600 + int(mm) * 60 + int(ss)

def getbpf(width):
    """get bits/(pixels*frame) from video width"""
    width = int(width)
    if width == 1920:
        return 0.076
    elif width == 1280:
        return 0.092
    return None

def getbitrate(width, height, fps, bpf=None):
    """return bitrate computed from width, height, FPS and Bits/(pixel*frame)"""
    if bpf is None:
        bpf = getbpf(width)
    if bpf is None:
        return None
    # Bits/Frame (bpf * width * height)
    bitsperframe = float(bpf) * float(width) * float(height)
    # Bitrate (Bits/Frame * fps / 1000)
    return int(round((bitsperframe * float(fps)) / 1000.0, 0))
