#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Distributed under terms of the MIT license.

def intduration(duration):
    """convert hh:mm:ss.ms to integer"""
    hh, mm, ssms, = duration.split(':')
    ss, ms, = ssms.split('.')
    return int(hh) * 3600 + int(mm) * 60 + int(ss)

def getbpf(width, height):
    # Hacky formula returning bpf
    t = int(width) * int(height)
    return round((((1/((t/2073600.0)**0.75))*0.066)/125.0)**0.36, 3)

def getbitrate(width, height, fps):
    """return bitrate computed from width, height, FPS and Bits/(pixel*frame)"""
    bpf = getbpf(width, height)
    # Bits/Frame (bpf * width * height)
    bitsperframe = float(bpf) * float(width) * float(height)
    # Bitrate (Bits/Frame * fps / 1000)
    return int(round((bitsperframe * float(fps)) / 1000.0, 0))
