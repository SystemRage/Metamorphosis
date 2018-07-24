<p align="right">
  <a href="http://www.kernel.org"><img src="https://user-images.githubusercontent.com/25354386/43166763-c43acaf2-8f97-11e8-940c-c4d6651da931.png" height="32" width="27" hspace="15" /></a>
  <a href="http://windows.microsoft.com/en-us/windows/home"><img src="https://user-images.githubusercontent.com/25354386/43166777-d394d15a-8f97-11e8-8f8d-39d56e81e9cb.png" height="32" width="29" /></a>
</p>

# Metamorphosis
> *The Ultimate Cursor Converter*

## Why
A tool that didn't exist is there now, for Linux and Windows users.

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
For Linux users:
Create a folder named *Metamorphosis* under *~/home/User*. Then under *~/home/User/Metamorphosis*
create a folder named *curs2conv* where put all your cursors to convert.
Now run *Metamorphosis.py*.

For Windows users:
Create a folder named *Metamorphosis* under *C:\\Users\\User*. Then under *C:\\Users\\User\\Metamorphosis*
create a folder named *curs2conv* where put all your cursors to convert.
Now run *Metamorphosis.py*.

## Notes
Do NOT distribute the converted themes without the permission of the original author.

## References
- [cfx2xc.py](https://github.com/coolwanglu/cfx2xc/blob/master/cfx2xc.py)
- [sd2xc.pl](https://github.com/ludios/sd2xc/blob/master/sd2xc.pl)

## License
 [![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0) ©  Matteo ℱan
