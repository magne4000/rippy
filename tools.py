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

def getbitrate(width, height, fps, bpf):
    """return bitrate computed from width, height, FPS and Bits/(pixel*frame)"""
    # Bits/Frame (bpf * width * height)
    bitsperframe = float(bpf) * float(width) * float(height)
    # Bitrate (Bits/Frame * fps / 1000)
    return int(round((bitsperframe * float(fps)) / float(1000), 0))
