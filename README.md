<p align="right">
  <a href="http://www.kernel.org"><img src="https://user-images.githubusercontent.com/25354386/43166763-c43acaf2-8f97-11e8-940c-c4d6651da931.png" height="32" width="27" hspace="15" /></a>
  <a href="http://windows.microsoft.com/en-us/windows/home"><img src="https://user-images.githubusercontent.com/25354386/43166777-d394d15a-8f97-11e8-8f8d-39d56e81e9cb.png" height="32" width="29" /></a>
</p>

# Metamorphosis
> *The Ultimate Cursor Converter*

## Why
After numerous researches, i figured that it doesn't exist a robust tool performing cursor conversions 
between the various formats.

So inspired by [cfx2xc.py](https://github.com/coolwanglu/cfx2xc/blob/master/cfx2xc.py) and [sd2xc.pl](https://github.com/ludios/sd2xc/blob/master/sd2xc.pl), i have decided to create one very cool, working with Linux and Windows.

## Requirements
 - *Python 3.5+*,
 - *PIL (Pillow) 3.3.1+*
 - *xcursorgen*
 - *tar*
 - *[Iconolatry](https://github.com/SystemRage/Iconolatry)*
 
## Features
* Extraction of CursorFX / CursorXP theme images and conversion to Linux X11 cursors or Windows ANI cursors.
    * Automatic correction for lazy authors' mistakes.
    * Detailed info log file creation.
    * Packaging of cursors converted.
    * Support for default animations or animations with scripts.
         * NEW !!! Conversion "repeat" / "end repeat" loops in scripts available.
    * Allows resizing cursors.
    * Support for clicked cursors ( only extraction ).

## Usage
For Linux users, create this path: *~/home/User/Metamorphosis/curs2conv*.

For Windows users, create this path: *C:\\Users\\User\\Metamorphosis\\curs2conv*.

Put your cursors in *curs2conv* folder as shown.

![input](https://user-images.githubusercontent.com/25354386/46557884-b6877300-c8eb-11e8-9908-c5873c0e5b93.png)

Now run *Metamorphosis.py*, then get cursors converted in *conversion* folder.

Enjoy !

## Notes
Do NOT distribute the converted themes without the permission of the original author.

## License
 [![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0) ©  Matteo ℱan
