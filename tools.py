#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Distributed under terms of the MIT license.

def intduration(duration):
    """convert hh:mm:ss to integer"""
    hh, mm, ss, = duration.split(':')
    return int(hh) * 3600 + int(mm) * 60 + int(ss)

def getbpf(width):
    width = int(width)
    if width == 1920:
        return 0.076
    elif width == 1280:
        return 0.092
    return None

def getbitrate(width, height, fps):
    """return bitrate computed from width, height, FPS and Bits/(pixel*frame)"""
    bpf = getbpf(width)
    if bpf is None:
        return None
    # Bits/Frame (bpf * width * height)
    bitsperframe = float(bpf) * float(width) * float(height)
    # Bitrate (Bits/Frame * fps / 1000)
    return int(round((bitsperframe * float(fps)) / 1000.0, 0))
