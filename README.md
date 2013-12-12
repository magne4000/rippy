rippy
=====

Wrapper using HandBrackeCli with custom presets.
The app contains a default preset which allows HandBrakeCli to generate lightweight x264 HD Videos (720p/1080p) without quality loss.  
It can rip mkv, BluRay folders or DVD folders.  

installation
------------
```
git clone https://github.com/magne4000/rippy.git
cd rippy
git submodule init
git submodule update
```
preset.xml can be customized to fit to your needs.

usage
-----
```
usage: rip.py [-h] [-d DEST] files [files ...]

Rippy

positional arguments:
  files                 List of files or folders that will be ripped
                        recursively

optional arguments:
  -h, --help            show this help message and exit
  -d DEST, --dest DEST  Folder where ripped files will be stored
```
