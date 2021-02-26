<p align="right">
  <a href="http://www.kernel.org"><img src="https://user-images.githubusercontent.com/25354386/43166763-c43acaf2-8f97-11e8-940c-c4d6651da931.png" height="32" width="27" hspace="15" /></a>
  <a href="http://windows.microsoft.com/en-us/windows/home"><img src="https://user-images.githubusercontent.com/25354386/43166777-d394d15a-8f97-11e8-8f8d-39d56e81e9cb.png" height="32" width="29" /></a>
</p>

# Metamorphosis
> *The Ultimate Cursor Converter*

## Why
After several researches, i come to the conclusion that it doesn't exist a robust tool performing cursors conversions 
between the different platform formats.
So inspired by [cfx2xc.py](https://github.com/coolwanglu/cfx2xc/blob/master/cfx2xc.py) and [sd2xc.pl](https://github.com/ludios/sd2xc/blob/master/sd2xc.pl), i decided to create one very cool.

## Requirements
 - `Python 3+`,
 - `PIL (Pillow)`
 - `xcursorgen`
 - `tar`
 - `[Iconolatry](https://github.com/SystemRage/Iconolatry)`
 
## Features
* Extraction of `CursorFX` / `CursorXP` theme images and:
    * Conversion to Linux `X11` or Windows `.ani` cursors.
    * Automatic correction for lazy authors' mistakes.
    * Supports default animations or script animations (also with *repeat* / *end repeat* loops).
    * Supports clicked cursors ( only extraction ).

* Conversion of `.cur` or `.ani` to `X11` cursors.
* Conversion of `X11` to `.ani` cursors.

* Generic:
    * Detailed log file creation.
    * Packaging of converted cursors.
    * Allows cursors resizing.
    * Changes cursors color.
    * Generates installations files for destination platform.

## Usage
`python3 Metamorphosis.py -h` for all available options.

Conversion to `X11` of an unpaired file and a files folder, packing results as `.tar.gz`:
`python3 Metamorphosis.py -i /path/to/folder/with/some/cursors -i /path/to/a/specific/cursor/file/Example3.CursorFX -o /path/converted/cursors -t Linux -p` 

where an example of the directory and file structure is:
```
/path/to/folder/with/some/cursors
│   Example1.CursorFX
│   Example2.CurXPTheme
│
└───folder_with_cur_and_ani_1
|    │   Help.cur
|    │   Crosshair.cur
|    |   Arrow.ani
|    |   Button.ani
|
└───folder_with_cur_and_ani_2
     |   SizeNS.cur
     |   SizeS.ani
     |   SizeWE.ani
```

Conversion to `.ani` of a files folder, outputting to working directory, resizing and changing original color:
`python3 Metamorphosis.py -i /path/to/folder/with/some/cursors -t Windows -s 32 -c gbr`

where an example of the directory and file structure is:
```
/path/to/folder/with/some/cursors
│   Example1.CursorFX
│   Example2.CurXPTheme
│
└───folder_with_X11
     │   top-left-arrow
     │   progress
     |   crosshair
     |   pencil
```

## Notes
- Remember that `.cur`, `.ani` or `X11` must have standard names.
- Do **NOT** distribute the converted themes without the permission of the original author.

## License
 [![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0) ©  Matteo ℱan
