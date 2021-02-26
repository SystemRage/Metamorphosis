#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from struct import unpack_from, pack, calcsize
from PIL import Image, ImageCms
from tempfile import mkstemp
from os.path import isfile, splitext, abspath, isdir, join, basename
from os import listdir
from io import BytesIO
import sys
import argparse
from functools import partial
from itertools import chain

__version__     = "2.0"
__license__     = "MIT License"
__author__      = u"Matteo ℱan <SystemRage@protonmail.com>"
__copyright__   = "© Copyright 2018-2021"
__url__         = "https://github.com/SystemRage/Iconolatry"
__summary__     = "Advanced Icon Converter"

## _________
##| Generic |-----------------------------------------------------------------------------------------------------------------------------------------------
##|_________|
##

is_cli = False
working_path = abspath('.')

def calc_rowsize(bits, width):
        """ Computes number of bytes per row in a image (stride). """
        ## The size of each row is rounded up to the nearest multiple of 4 bytes.
        return int(((bits * width + 31) // 32)) * 4

def calc_masksize(width):
        """ Computes number of bytes for AND mask. """
        return int((width + 32 - width % 32 if (width % 32) > 0 else width) / 8)

def print_err(msg, view = True, toexit = True):
        """ Handles stderr. """
        if view:
                sys.stderr.write(msg + '\n')
                sys.stderr.flush()
                if toexit:
                        sys.exit(1)

def print_std(msg, view = False):
        """ Handles stdout. """
        if view:
                sys.stdout.write(msg + '\n')
                sys.stdout.flush()

class EncodeErr(Exception):
        """ Custom encode exception. """
        def __init__(self, **kwargs):
                self.code, self.msg = kwargs['code'], kwargs['msg']


## ________
##| Parser |------------------------------------------------------------------------------------------------------------------------------------------------
##|________|
##

def tupledict(value):
        from ast import literal_eval
        try:
                value = literal_eval(value)
        except:
                # get errors after.
                pass
        return value

class ExtendAction(argparse.Action):
        # https://stackoverflow.com/questions/41152799/argparse-flatten-the-result-of-action-append
        def __call__(self, parser, namespace, values, option_string = None):
                items = getattr(namespace, self.dest) or []
                items.extend(values)
                setattr(namespace, self.dest, items)

def iconolatry_parser():
        """ CLI parser. """
        options = {}
        icon_parser = argparse.ArgumentParser(description = __summary__, epilog = 'version: ' + __version__)
        icon_subparsers = icon_parser.add_subparsers(dest = 'mode', help = "Select if you want to read or to write an `.ico` / `.cur`.")

        # Decode parser.
        dec_parser = icon_subparsers.add_parser('decode', add_help = False, allow_abbrev = False)
        dec_parser.register('action', 'extend', ExtendAction)
        dec_required = dec_parser.add_argument_group('required arguments')
        dec_required.add_argument('-i', '--icocurs-paths', required = True, nargs = "+", action = "extend", default = [], type = str,
                                  dest = "paths_icocurs",
                                  help = "Path(s) of `.ico` / `.cur` file(s) or folder(s) to be decoded.")

        dec_optional = dec_parser.add_argument_group('optional arguments')
        dec_optional.add_argument('-h', '--help', action = "help", default = argparse.SUPPRESS,
                                  help = "show this help message and exit")
        dec_optional.add_argument('-o', '--image-paths', nargs = "+", action = "extend", default = [], type = str,
                                  dest = "paths_image",
                                  help = "Path(s) of `.ico` / `.cur` image(s) decoded.")
        dec_optional.add_argument('-n', '--image-names', nargs = "+", action = "extend", default = [], type = str,
                                  dest = "names_image",
                                  help = "Name(s) of `.ico` / `.cur` image(s) decoded.")
        dec_optional.add_argument('-f', '--image-formats', nargs = "+", action = "extend", default = [], type = str,
                                  dest = "formats_image",
                                  help = "Format(s) of `.ico` / `.cur` image(s) decoded.")
        dec_optional.add_argument('-u', '--rebuild', action = 'store_true', default = False,
                                  dest = "rebuild",
                                  help = "Enable recompute AND mask.")

        # Encode parser.
        enc_parser = icon_subparsers.add_parser('encode', add_help = False, allow_abbrev = False)
        enc_parser.register('action', 'extend', ExtendAction)
        enc_required = enc_parser.add_argument_group('required arguments')
        enc_required.add_argument('-i', '--images-paths', required = True, nargs = "+", action = "append", default = [], type = str,
                                  dest = "paths_images",
                                  help = "Path(s) of image file(s) or folder(s) to be encoded.")

        enc_optional = enc_parser.add_argument_group('optional arguments')
        enc_optional.add_argument('-h', '--help', action = "help", default = argparse.SUPPRESS,
                                  help = "show this help message and exit")
        enc_optional.add_argument('-o', '--icocur-paths', nargs = "+", action = "extend", default = [], type = str,
                                  dest = "paths_icocur",
                                  help = "Path(s) of `.ico` / `.cur`(s) encoded.")
        enc_optional.add_argument('-n', '--icocur-names', nargs = "+", action = "extend", default = [], type = str,
                                  dest = "names_icocur",
                                  help = "Name(s) of `.ico` / `.cur`(s) encoded.")
        enc_optional.add_argument('-f', '--icocur-formats', nargs = "+", action = "extend", default = [], type = tupledict,
                                  dest = "formats_icocur",
                                  help = "Format(s) of `.ico` / `.cur`(s) encoded.")
        enc_optional.add_argument('-r', '--resize', action = "store", default = 'up256_prop', type = tupledict,
                                  dest = "type_resize",
                                  help = "Resize method (values) to apply during encoding.")
        enc_optional.add_argument('-c', '--force', action = "store", default = 'raw', type = str,
                                  dest = "force_to",
                                  help = "Bit depth conversion method to apply during encoding.")
        enc_optional.add_argument('-p', '--custom-palettes', action = "store", default = {}, type = tupledict,
                                  dest = "custom_palettes",
                                  help = "Palettes to apply during encoding.")

        try:
                options.update(vars(icon_parser.parse_args()))
        except Exception as e:
                raise e

        return options

## _____________________
##| Parameters Checker  |-----------------------------------------------------------------------------------------------------------------------------------
##|_____________________|
##

class Check(object):

        def __init__(self, list_in, list_out):
                self.list_in, self.list_out = list_in, list_out

        def setup(self):
                """ Checks output length list. """
                if not isinstance(self.list_out, list):
                        print_err("Input error: %s not a list." %self.msg)

                if len(self.list_in) > len(self.list_out):
                        # used default for missing fields.
                        self.list_out.extend([self.default] * (len(self.list_in) - len(self.list_out)))
                elif len(self.list_in) < len(self.list_out):
                        print_err("Input error: too much %s." %self.msg)

        def paths(self, msg):
                """ Checks output paths list. """
                self.msg = msg + " directory path/s"
                self.default = working_path
                self.setup()

                for indx, path in enumerate(self.list_out):
                        if not isinstance(path, str):
                                print_err("Input error: %s directory path '%s' not a string." %(msg, path))
                        else:
                                if path is "":
                                        # used default for specified empty field.
                                        self.list_out[indx] = self.default
                                elif not isdir(path):
                                        print_err("Input error: %s directory path '%s' not found." %(msg, path))

        def names(self, msg):
                """ Checks output names list. """
                self.msg = msg + " name/s"
                self.default = ""
                self.setup()

                for indx, (path, name) in enumerate(zip(self.list_in, self.list_out)):
                        if not isinstance(name, str):
                                print_err("Input error: %s name '%s' not a string." %(msg, name))
                        else:
                                if name is "":
                                        try:
                                                if isinstance(path, list) and len(path) == 1:
                                                        path = path[0]
                                                        # single image --> get image name.
                                                        # directory images --> put "".
                                                        self.list_out[indx] = (splitext(basename(path))[0] if isfile(path) else self.default)
                                        except:
                                                # get errors after.
                                                pass

        def formats_checker(self, msg):
                """ Formats checking function. """
                Image.init()
                for indx, frmt in enumerate(self.list_out):
                        if not isinstance(frmt, str):
                                print_err("Input error: %s format '%s' not a string." %(msg, frmt))
                        else:
                                if frmt is "":
                                        self.list_out[indx] = self.default
                                else:
                                        if (self.default == ".png" and frmt[1:].upper() not in Image.SAVE.keys()) or \
                                           (self.default == ".ico" and frmt not in [".ico", ".cur"]):
                                                print_err("Input error: %s format '%s' not recognized." %(msg, frmt))

        def formats(self, msg, default, check = True):
                """ Checks output formats list. """
                self.msg = msg + " format/s"
                self.default = default
                self.setup()

                if check:
                        self.formats_checker(msg)


## _______________________
##| Read `.ico` / `.cur`  |----------------------------------------------------------------------------------------------------------------------------------
##|_______________________|
##

class Decode(object):

        def __init__(self, paths_icocurs, paths_image = [], names_image = [], formats_image = [],
                     rebuild = False, force_to = 'original'):

                """
                    `paths_icocurs`   : a list   : can contain one/more icon/cursor(s) path(s)
                                                   and/or one/more folder icon/cursor(s) path(s) to convert.
                    `paths_image`     : a list   : contains output path(s) for every resulting conversion.
                                                   If `paths_image` isn't defined, working directory is used.
                    `names_image`     : a list   : contains output name(s) for every resulting conversion.
                    `formats_image`   : a list   : contains format(s) for every resulting conversion (all saving PIL formats).
                    `rebuild`         : a bool   : if 'True', recompute mask from the alpha channel data.
                    `force_to`        : a string : if 'original', original bit depth is kept. (TODO)
                """

                self.paths_icocurs = paths_icocurs
                self.paths_image = paths_image
                self.formats_image = formats_image
                self.names_image = names_image
                self.rebuild = rebuild
                self.force_to = force_to
                self.is_cli = is_cli
                self.want_save = (False if all(x == [] for x in [self.paths_image, self.names_image, self.formats_image]) else True)
                self.build()

        def is_png(self, dataimage):
                """ Determines whether a sequence of bytes is a PNG. """
                return dataimage.startswith(b'\x89PNG\r\n\x1a\n')

        def is_gray(self):
                """ Determines whether an image is grayscale (from palette). """
                paletteblocks = [self.parameters['palette'][i : i + 3] for i in range(0, self.parameters['size_pal'], 4)]
                if all(elem == block[0] for block in paletteblocks for elem in block):
                        return True
                else:
                        return False

        def check_output(self):
                """ Verifies if output paths, names, formats are ok. """
                ## Check rebuild option.
                if not isinstance(self.rebuild, bool):
                        print_err("Input error: option 'rebuild' not a boolean.")

                ## Checks paths.
                Check(self.paths_icocurs, self.paths_image).paths("image")
                ## Check names.
                Check(self.paths_icocurs, self.names_image).names("image")
                ## Check formats.
                Check(self.paths_icocurs, self.formats_image).formats("image", ".png")

        def build(self):
                """ Verifies if input paths are ok and starts conversion job. """
                self.print_std = partial(print_std, view = self.is_cli)
                self.print_err = partial(print_err, view = self.is_cli)

                ## Checks paths `.ico` / `.cur` files (Input).
                if not self.paths_icocurs:
                        print_err("Input error: `.ico` / `.cur` file path/s missing.")

                if isinstance(self.paths_icocurs, list):
                        self.check_output()
                        self.remind = {}
                        self.all_icocur_readed = {}

                        for self.index, self.path_icocur in enumerate(self.paths_icocurs):
                                if isinstance(self.path_icocur, str):
                                        if isfile(self.path_icocur):
                                                self.work()
                                        else:
                                                if isdir(self.path_icocur):
                                                        temp = self.path_icocur
                                                        for file in sorted(listdir(self.path_icocur)):
                                                                self.path_icocur = join(self.path_icocur, file)
                                                                self.work()
                                                                self.path_icocur = temp
                                                else:
                                                        self.all_icocur_readed.update({self.path_icocur : "Input error: file/directory not found."})
                                elif isinstance(self.path_icocur, bytes):
                                        self.data_icocur = self.path_icocur
                                        self.path_icocur = "stream_%s" %self.index
                                        self.work(is_byte = True)
                                else:
                                        self.all_icocur_readed.update({self.path_icocur : "Input error: neither a file/directory nor bytes."})
                else:
                        print_err("Input error: `.ico` / `.cur` file path/s not a list.")

        def extract(self, dataimage, offset):
                """ Gets bitmap parameters. """
                # Should be:
                # biSize is the size of the header
                # biHeight doubled respect bHeight
                # biPlanes = 1
                # biCompression = 0 (if BI_RGB)
                # biSizeImage = size of the XOR mask + AND mask (can be also 0)
                # biXPelsPerMeter = 0 (if not used)
                # biYPelsPerMeter = 0 (if not used)
                # biClrUsed = 0 (if not used)
                # biClrImportant = 0 (if not used)

                ## Get BITMAPINFO header data.
                (biSize, biWidth, biHeight, biPlanes, biBitCount,
                biCompression, biSizeImage, biXPelsPerMeter, biYPelsPerMeter, biClrUsed, biClrImportant) = unpack_from('<3L2H6L', dataimage[0 : 40])

                biHeight = int(biHeight / 2.)
                ## Get palette, xor & and mask.
                xorsize = calc_rowsize(biBitCount, biWidth) * biHeight
                andsize = calc_masksize(biWidth) * biHeight
                palettesize = offset - (biSize + xorsize + andsize)
                if palettesize < 0:
                        palettesize = 0

                palette = dataimage[biSize : biSize + palettesize]
                xordata = dataimage[biSize + palettesize : biSize + palettesize + xorsize]
                anddata = dataimage[biSize + palettesize + xorsize : len(dataimage)]

                self.parameters = {"head"      : biSize,
                                   "width"     : biWidth,
                                   "height"    : biHeight,
                                   "planes"    : biPlanes,
                                   "bpp"       : biBitCount,
                                   "compress"  : biCompression,
                                   "size_img"  : biSizeImage,
                                   "colors"    : biClrUsed,
                                   "size_pal"  : palettesize,
                                   "num_pal"   : 0,
                                   "palette"   : palette,
                                   "size_xor"  : xorsize,
                                   "xor"       : xordata,
                                   "size_and"  : andsize,
                                   "and"       : anddata
                                   }

        def load(self):
                """ Gets image from bytes. """
                modes = {32 : ("RGBA", "BGRA"),
                         24 : ("RGB",  "BGR"),
                         16 : ("RGB",  "BGR"),
                         8  : ("P",    "P"),
                         4  : ("P",    "P;4"),
                         2  : ("P",    "P;2"),
                         1  : ("P",    "P;1")}

                if self.is_gray():
                        modes.update({8 : ("L", "L"),
                                      4 : ("L", "L;4"),
                                      2 : ("L", "L;2"),
                                      1 : ("1", "1")})

                pad_msk = calc_masksize(self.parameters['width'])

                if self.parameters['bpp'] == 16:
                        # PIL I;16 converted to RGB555 format.
                        pad_ima = calc_rowsize(24, self.parameters['width'])
                        dataimage = []
                        for i in range(0, len(self.parameters['xor']), 2):
                                data = int.from_bytes(self.parameters['xor'][i : i + 2], byteorder = 'little')
                                a = (data & 0x8000) >> 15
                                b = (data & 0x7C00) >> 10
                                g = (data & 0x3E0) >> 5
                                r = (data & 0x1F)
                                r = (r << 3) | (r >> 2)
                                g = (g << 3) | (g >> 2)
                                b = (b << 3) | (b >> 2)
                                value = r << 16 | g << 8 | b
                                dataimage.append((value).to_bytes(3, byteorder = 'little'))

                        dataimage = b"".join(dataimage)
                        image = Image.frombytes(modes[self.parameters['bpp']][0], (self.parameters['width'], self.parameters['height']),
                                                dataimage, 'raw', modes[self.parameters['bpp']][1], pad_ima, -1)
                else:
                        pad_ima = calc_rowsize(self.parameters['bpp'], self.parameters['width'])
                        image = Image.frombytes(modes[self.parameters['bpp']][0], (self.parameters['width'], self.parameters['height']),
                                                self.parameters['xor'], 'raw', modes[self.parameters['bpp']][1], pad_ima, -1)

                if self.parameters['bpp'] == 32:
                        mask = Image.frombuffer("L", (self.parameters['width'], self.parameters['height']),
                                                self.parameters['xor'][3::4], 'raw', 'L', 0, -1)
                else:
                        mask = Image.frombuffer("1", (self.parameters['width'], self.parameters['height']),
                                                self.parameters['and'], 'raw', '1;I', pad_msk, -1)

                if self.parameters['palette'] and self.parameters['bpp'] <= 8:
                        image = image.convert('P')
                        palette_int = [self.parameters['palette'][i : i + 3] for i in range(0, self.parameters['size_pal'], 4)]
                        rsv = [self.parameters['palette'][i + 3 : i + 4] for i in range(0, self.parameters['size_pal'], 4)]

                        if (self.parameters['size_pal'] % 3 == 0) and (self.parameters['size_pal'] % 4 == 0):
                                if len(set(rsv)) <= 1:
                                        # palette RGBA.
                                        palette_int = [pal[i] for pal in palette_int for i in reversed(range(3))]
                                        self.parameters['num_pal'] = self.parameters['size_pal'] // 4
                                else:
                                        # palette RGB.
                                        palette_int = [pal for pal in self.parameters['palette'][::-1]]
                                        self.parameters['num_pal'] = self.parameters['size_pal'] // 3
                        else:
                                if self.parameters['size_pal'] % 3 == 0:
                                        # palette RGB.
                                        palette_int = [pal for pal in self.parameters['palette'][::-1]]
                                        self.parameters['num_pal'] = self.parameters['size_pal'] // 3
                                elif self.parameters['size_pal'] % 4 == 0:
                                        # palette RGBA.
                                        palette_int = [pal[i] for pal in palette_int for i in reversed(range(3))]
                                        self.parameters['num_pal'] = self.parameters['size_pal'] // 4

                        ## PIL is wonky with next RGBA conversion,
                        ## if the palette isn't complete (768 values) for bilevel.
                        if self.parameters['bpp'] == 1:
                                pal = list(image.palette.getdata()[1])
                                pal[:3], pal[-3:] = palette_int[:3], palette_int[-3:]
                                palette_int = pal
                        # Assign palette.
                        image.putpalette(palette_int)

                image = image.convert('RGBA')
                image.putalpha(mask)

                return image

        def from_icocur(self):
                """ Reads an `.ico` / `.cur` file and checks whether it's acceptable. """
                def add_warning(dict_icocur, num, msg):
                        if 'warning' in dict_icocur['image_%s' %num]:
                                dict_icocur['image_%s' %num]['warning'].append(msg)
                        else:
                                dict_icocur['image_%s' %num].update({'warning' : [msg]})

                icocur_readed = {}
                typ = {1 : 'ICO',
                       2 : 'CUR'}
                datasize = len(self.data_icocur)
                identf, count = unpack_from('<2H', self.data_icocur[2 : 6])

                ## Control if it's a `.ico` / `.cur` type and extract values.
                if identf not in [1, 2]:
                        self.all_icocur_readed.update({self.path_icocur : "Icon/Cursor error: invalid `.ico` / `.cur`."})
                        return
                else:
                        if identf == 1 and self.path_icocur.endswith('.cur'):
                                msg = "Not a real `.cur` ! It's an icon with extension `.cur`."
                                icocur_readed.update({'warning' : [msg]})
                        elif identf == 2 and self.path_icocur.endswith('.ico'):
                                msg = "Not a real `.ico` ! It's a cursor with extension `.ico`."
                                icocur_readed.update({'warning' : [msg]})

                ## Note: always one frame for `.cur`.
                icondirentries = [unpack_from('<4B2H2L', self.data_icocur[6 + 16 * i : 22 + 16 * i]) for i in range(count)]

                for cnt in range(count):
                        # Should be:
                        # wPlanes = 0 (if not used)
                        # wBitCount = 0 (if not used)
                        # dwBytesInRes is the total number of bytes in the image data, including palette data
                        # dwImageOffset is offset from the beginning of the file to the image data
                        icocur_readed.update({'image_%s' %cnt: {}})

                        bWidth, bHeight, bColorCount, bReserved, \
                                wPlanes_or_wXHotSpot, wBitCount_or_wYHotSpot, dWBytesInRes, dWImageOffset = icondirentries[cnt]
                        bWidth = bWidth or 256
                        bHeight = bHeight or 256

                        if cnt == 0:
                                totalsize = dWImageOffset + dWBytesInRes
                        else:
                                totalsize += dWBytesInRes

                        icocurdata_with_header = self.data_icocur[dWImageOffset : dWImageOffset + dWBytesInRes]
                        png_flag = self.is_png(icocurdata_with_header)

                        if not png_flag:
                                if bWidth >= 256 or bHeight >= 256:
                                        add_warning(icocur_readed, cnt, "Is a large uncompressed `bmp` ! Should be `png` format.")

                                ## Get bmp parameters.
                                self.extract(icocurdata_with_header, dWBytesInRes)
                                ## Get mask and check it.
                                self.parameters, chk = Mask().rebuild_AND_mask(icocurdata_with_header, self.parameters, self.rebuild)
                                if not chk:
                                        add_warning(icocur_readed, cnt, "Bad mask found ! Will display incorrectly in some places (Windows).")

                                ## Other checks.
                                try:
                                        assert bWidth == self.parameters['width'], ('width')
                                        assert bHeight == self.parameters['height'], ('height')
                                        if identf == 1:
                                                assert (wPlanes_or_wXHotSpot in [0, 1]) and (self.parameters['planes'] == 1), ('planes')
                                                assert (wBitCount_or_wYHotSpot == 0) or (wBitCount_or_wYHotSpot == self.parameters['bpp']), ('bits')
                                        assert self.parameters['compress'] == 0, ('compression')
                                        if (self.parameters['size_img'] != 0) and \
                                           (self.parameters['size_img'] != self.parameters['size_xor'] + self.parameters['size_and']):
                                                # it seems legal to put a wrong 'size_img' !
                                                add_warning(icocur_readed, cnt, "Size image malformed value !")

                                        assert (bColorCount == self.parameters['colors']) or \
                                               (bColorCount == 0 and self.parameters['colors'] == 1 << wBitCount_or_wYHotSpot) or \
                                               (bColorCount == 0 and self.parameters['colors'] == 1 << self.parameters['bpp']) or \
                                               (bColorCount == 1 << wBitCount_or_wYHotSpot and self.parameters['colors'] == 0) or \
                                               (bColorCount == 1 << self.parameters['bpp'] and self.parameters['colors'] == 0), ('color count')
                                except AssertionError as e:
                                        icocur_readed.update({'image_%s' %cnt : "Image error: malformed %s." %e.args[0]})
                                        continue

                                try:
                                        image = self.load()
                                        icocur_readed['image_%s' %cnt].update({'im_obj' : image,
                                                                               'depth'  : self.parameters['bpp']})
                                        if self.parameters['num_pal'] > 0:
                                                icocur_readed['image_%s' %cnt].update({'num_pal' : self.parameters['num_pal']})
                                except:
                                        icocur_readed.update({'image_%s' %cnt : "Image error: image not supported."})
                                        continue

                        elif png_flag:
                                icocurdata = BytesIO(icocurdata_with_header)
                                image = Image.open(icocurdata)

                                if image:
                                        w, h = image.size
                                        icocurdata = icocurdata.getvalue()
                                        bitdepth, colortype = unpack_from('<2B', icocurdata[24 : 26])
                                        bpp = len(image.getbands()) * bitdepth

                                        ## Other checks.
                                        try:
                                                assert bWidth == w , ('width')
                                                assert bHeight == h , ('height')
                                                if identf == 1:
                                                        assert wPlanes_or_wXHotSpot in [0, 1], ('planes')
                                                        assert (wBitCount_or_wYHotSpot == 0) or (wBitCount_or_wYHotSpot == bpp), ('bits')
                                                        assert (bColorCount == 0) or (bColorCount == 1 << wBitCount_or_wYHotSpot), ('color count')
                                                elif identf == 2:
                                                        assert bColorCount == 0, ('color count')
                                        except AssertionError as e:
                                                icocur_readed.update({'image_%s' %cnt : "Image error: malformed %s." %e.args[0]})
                                                continue

                                        icocur_readed['image_%s' %cnt].update({'info' : {'format' : "`png` compressed"}})
                                        if image.info:
                                                icocur_readed['image_%s' %cnt]['info'].update(image.info)

                                        icocur_readed['image_%s' %cnt].update({'im_obj' : image,
                                                                               'depth'  : bpp})

                                        if image.palette:
                                                modepal, palette = image.palette.getdata()
                                                if modepal in ['RGB', 'RGB;L']:
                                                        palettenum = int(len(palette) / 3)
                                                elif modepal in ['RGBA', 'RGBA;L']:
                                                        palettenum = int(len(palette) / 4)

                                                icocur_readed['image_%s' %cnt].update({'num_pal' : palettenum})
                        else:
                                icocur_readed.update({'image_%s' %cnt : "Image error: neither `bmp` nor `png`."})
                                continue

                        if identf == 2:
                                icocur_readed['image_%s' %cnt].update({'hotspot_x' : wPlanes_or_wXHotSpot,
                                                                       'hotspot_y' : wBitCount_or_wYHotSpot})

                if datasize != totalsize:
                        self.all_icocur_readed.update({self.path_icocur : "Icon/Cursor error: invalid %s, unexpected EOF." %typ[identf]})
                        return

                return icocur_readed

        def printsave(self):
                """ Saves conversion file and print results. """
                current = self.paths_icocurs[self.index]
                result = self.all_icocur_readed[self.path_icocur]

                if isinstance(result, dict):
                        self.print_std('\n' + '#' * 80 + '\n')
                        if isinstance(current, bytes):
                                self.print_std('bytes = %s\n' %self.path_icocur)
                        else:
                                if isdir(current):
                                        self.print_std('folder = %s\n' %current)
                                self.print_std('file = %s\n' %self.path_icocur)

                        for indx, key in enumerate(result):

                                self.print_std('** ' + key + ' **')

                                subresult = result[key]
                                if isinstance(subresult, dict):
                                        if 'warning' in subresult:
                                                # print image warnings.
                                                for warn in subresult['warning']:
                                                        self.print_err(warn, toexit = False)
                                        if 'info' in subresult:
                                                # print image info png.
                                                inf = ', '.join('{} = {}'.format(k, v) for k, v in subresult['info'].items())
                                                self.print_std('info --> %s' %inf)

                                        self.print_std('(width, height) = %s' %str(subresult['im_obj'].size))
                                        self.print_std('depth = %s' %subresult['depth'])

                                        if 'num_pal' in subresult:
                                                # print image palette size.
                                                self.print_std('palette length = %s' %subresult['num_pal'])
                                        if 'hotspot_x' in subresult:
                                                # print `.cur` hotspots.
                                                self.print_std('(hotspot_x, hotspot_y) = %s' %str((subresult['hotspot_x'], subresult['hotspot_y'])))
                                        # save.
                                        if self.want_save or self.is_cli:
                                                # define current path, name and format.
                                                path, name, frmt = self.paths_image[self.index], \
                                                                   self.names_image[self.index], \
                                                                   self.formats_image[self.index]

                                                if name == "":
                                                        name = splitext(basename(self.path_icocur))[0]

                                                # define current index.
                                                couple = (path, name)
                                                current_indx = (indx + self.remind[couple] + 1 if couple in self.remind.keys() else indx)
                                                # define current name with index.
                                                current_name = (name + '_' + str(current_indx) if len(result) > 1 or couple in self.remind.keys() else name)

                                                save_path = join(path, current_name + frmt)
                                                subresult['im_obj'].save(save_path, format = frmt[1:].upper())
                                                subresult.update({'saved' : save_path})
                                                self.print_std('saved as = %s' %save_path)
                                else:
                                        if isinstance(subresult, list):
                                                for warn in subresult:
                                                        self.print_err(warn, toexit = False)
                                        else:
                                                self.print_err(subresult, toexit = False)

                        # remind last index bound to a specific path and name.
                        if isinstance(subresult, dict):
                                self.remind.update({couple : current_indx})
                else:
                        self.print_err(result, toexit = False)

        def work(self, is_byte = False):
                """ Executes conversion job."""
                if not is_byte:
                        if self.path_icocur.lower().endswith('.ico') or self.path_icocur.lower().endswith('.cur'):
                                with open(self.path_icocur, 'rb') as file:
                                        self.data_icocur = file.read()
                        else:
                                print_err("Input error: not an `.ico` / `.cur` file.")

                ico_r = self.from_icocur()
                if ico_r:
                        self.all_icocur_readed.update({self.path_icocur : ico_r})
                        ## Show / save results.
                        self.printsave()

## __________________
##| Mask Operations  |--------------------------------------------------------------------------------------------------------------------------------------
##|__________________|
##

class Mask(object):
        """ edited / adapted parts of:
            https://chromium.googlesource.com/chromium/src/+/master/tools/resources/ico_tools.py
        """

        def compute_AND_mask(self, width, height, xordata):
                """ Computes AND mask from 32-bit BGRA image data. """
                andbytes = []
                for y in range(height):
                        bitcounter, currentbyte = (0 for _ in range(2))
                        for x in range(width):
                                alpha = xordata[(y * width + x) * 4 + 3]
                                currentbyte <<= 1
                                if alpha == 0:
                                        currentbyte |= 1
                                bitcounter += 1
                                if bitcounter == 8:
                                        andbytes.append(currentbyte)
                                        bitcounter, currentbyte = (0 for _ in range(2))
                        ## Pad current byte at the end of row.
                        if bitcounter > 0:
                                currentbyte <<= (8 - bitcounter)
                                andbytes.append(currentbyte)
                        ## Keep padding until multiple 4 bytes.
                        while len(andbytes) % 4 != 0:
                                andbytes.append(0)

                andbytes = b"".join(pack('B', andbyte) for andbyte in andbytes)

                return andbytes

        def check_AND_mask(self, width, height, xordata, anddata):
                """ Verifies if AND mask is good for 32-bit BGRA image data.
                    1- Checks if AND mask is opaque wherever alpha channel is not fully transparent.
                    2- Checks inverse rule, AND mask is transparent wherever alpha channel is fully transparent.
                """
                xorbytes = width * 4
                andbytes = calc_rowsize(1, width)
                for y in range(height):
                        for x in range(width):
                                alpha = ord(bytes([xordata[y * xorbytes + x * 4 + 3]]))
                                mask = bool(ord(bytes([anddata[y * andbytes + x // 8]])) & (1 << (7 - (x % 8))))
                                if mask:
                                        if alpha > 0:
                                                ## mask transparent, alpha partially or fully opaque. This pixel
                                                ## can show up as black on Windows due to a rendering bug.
                                                return False
                                else:
                                        if alpha == 0:
                                                ## mask opaque, alpha transparent. This pixel should be marked as
                                                ## transparent in the mask, for legacy reasons.
                                                return False
                return True

        def rebuild_AND_mask(self, dataimage, parameters, rebuild = False):
                """ Checks icon image AND mask for correctness, or rebuilds it.
                    With rebuild == False, checks whether the mask is bad.
                    With rebuild == True, throw the mask away and recompute it from the alpha channel data.
                """
                # Note: the monochrome AND mask does not have a palette table.
                check = True
                if parameters['bpp'] != 32:
                        ## No alpha channel, so the mask cannot be wrong.
                        return parameters, check
                else:
                        if rebuild:
                                parameters['and'] = self.compute_AND_mask(parameters['width'], parameters['height'], parameters['xor'])
                                return parameters, check
                        else:
                                return parameters, self.check_AND_mask(parameters['width'], parameters['height'], parameters['xor'], parameters['and'])


## ________________________
##| Write `.ico` / `.cur`  |---------------------------------------------------------------------------------------------------------------------------------
##|________________________|
##

class Encode(object):

        def __init__(self, paths_images, paths_icocur = [], names_icocur = [], formats_icocur = [],
                     type_resize = 'up256_prop', force_to = 'original', custom_palettes = {}):

                """
                    `paths_images`   : a list of lists   : every list can contain one/more image(s) path(s)
                                                           and/or one/more folder image(s) path(s) to convert.
                    `paths_icocur`   : a list            : contains output path(s) for every resulting conversion.
                                                           If `paths_icocur` isn't defined, working directory is used.
                    `names_icocur`   : a list            : contains output name(s) for every resulting conversion.
                                                           If `paths_images` contains a *folder path* and corresponding `names_icocur` is defined,
                                                           a multi-`.ico` is created (note: multi-`.cur` creation is forbidden), otherwise
                                                           every image in *folder path* is converted to a single `.ico` / `.cur`.
                    `formats_icocur` : a list            : contains format(s) for every resulting conversion (that is ".ico" or ".cur").
                                                           If ".cur", can be specified hotspot x (integer) and hotspot y (integer)
                                                           using a tuple; example: (".cur", 2, 5).
                    `type_resize`    : a string or tuple : If used 'up256_prop' / 'up256_no_prop' dimensions greater than 256 pixels are resized
                                                           keeping / without keeping global image aspect ratio.
                                                           If used 'square', dimensions are resized to nearest square standard size.
                                                           Can be also provided a custom resize tuple (width, height).
                    `force_to`       : a string          : If 'original', original bit depth is kept. (TODO)
                    `custom_palettes`: a dict            : The key is a tuple (mode, bitdepth), the value can be
                                                           a list of RGB tuples [(R1,G1,B1),...,(Rn,Bn,Gn)] (usual palette format) or
                                                           a list flat [V1,V2,...,Vn] (compact format for grayscale palette) or
                                                           a '.gpl' file path.
                """

                self.paths_images = paths_images
                self.paths_icocur = paths_icocur
                self.names_icocur = names_icocur
                self.formats_icocur = formats_icocur
                self.type_resize = type_resize
                self.force_to = force_to
                self.custom_palettes = custom_palettes
                self.is_cli = is_cli
                self.build()

        def add_name2path(self, name, frmt, indx):
                """ Adds `.ico` / `.cur` name to output path. """
                couple = (self.path_icocur, name)
                current_indx = (self.remind[couple] + 1 if couple in self.remind.keys() else indx)
                current_name = (name + '_' + str(current_indx) if couple in self.remind.keys() else name)
                self.remind.update({(self.path_icocur, name) : current_indx})
                self.path_icocur = join(self.path_icocur, current_name + frmt)

        def add_errors(self, msg):
                """ Assigns / prints process errors."""
                self.all_icocur_written.update({self.path_icocur : msg})
                self.print_err(msg)

        def check_output(self):
                """ Verifies if output paths, names, formats are ok. """
                ## Check other options.
                if not isinstance(self.type_resize, (tuple, str)):
                        print_err("Input error: option `type_resize` not a tuple or a string.")
                else:
                        if isinstance(self.type_resize, tuple) and not (len(self.type_resize) == 2 \
                                                                        and all(isinstance(tyr, int) for tyr in [self.type_resize[0], self.type_resize[1]]) \
                                                                        and self.type_resize[0] <= 256 and self.type_resize[1] <= 256):
                                print_err("Input error: option `type_resize` tuple not proper defined.")
                        elif isinstance(self.type_resize, str) and (self.type_resize not in ['up256_prop', 'up256_no_prop', 'square']):
                                print_err("Input error: option `type_resize` unknown '%s' method." %self.type_resize)

                if self.force_to not in ['original']:
                        print_err("Input error: option `force_to` not proper defined.")

                ## Check paths.
                msg = "icon / cursor"
                Check(self.paths_images, self.paths_icocur).paths(msg)
                ## Check names.
                Check(self.paths_images, self.names_icocur).names(msg)
                ## Check formats.
                # 1 - check length list.
                frmtchk = Check(self.paths_images, self.formats_icocur)
                frmtchk.formats(msg, ".ico", check = False)
                # 2 - check hotspots (for `.cur`).
                self.hotspots = []
                for i, frmt in enumerate(self.formats_icocur):
                        if isinstance(frmt, tuple):
                                if frmt[0] == '.ico':
                                        print_err("Input error: hotspot specification invalid for `.ico` conversion.")
                                if all(not isinstance(hot, int) for hot in frmt[1::]) or (len(frmt[1::]) != 2):
                                        print_err("Input error: hotspot specification not proper defined.")

                                self.formats_icocur[i] = frmt[0]
                                self.hotspots.append(frmt[1::])
                        else:
                                if frmt == '.ico':
                                        self.hotspots.append("")
                                elif frmt == '.cur':
                                        self.hotspots.append((0, 0))
                # 3 - check extensions.
                frmtchk.formats_checker(msg)

        def build(self):
                """ Verifies if input paths are ok and starts conversion job. """
                self.print_std = partial(print_std, view = self.is_cli)
                self.print_err = partial(print_err, view = self.is_cli)

                ## Check paths images.
                if self.paths_images and isinstance(self.paths_images, list):
                        self.check_output()
                        self.remind = {}
                        self.all_icocur_written = {}

                        groups = zip(self.paths_images, self.paths_icocur, self.names_icocur, self.formats_icocur, self.hotspots)
                        for indx, (path_image, self.path_icocur, name, frmt, hotspot) in enumerate(groups):
                                self.print_std('#' * 80)
                                no_err, paths = True, []

                                if isinstance(path_image, list):
                                        if not path_image:
                                                no_err = False
                                                message = "Input error: image file/directory path/s missing."
                                        else:
                                                for imapath in path_image:
                                                        if not isinstance(imapath, str):
                                                                no_err = False
                                                                message = "Input error: image file/directory path '%s' not a string." %imapath
                                                        else:
                                                                if isfile(imapath):
                                                                        paths.append(imapath)
                                                                else:
                                                                        if isdir(imapath):
                                                                                paths.extend([join(imapath, file) for file in listdir(imapath)])
                                                                        else:
                                                                                no_err = False
                                                                                message = "Input error: file/directory '%s' not found." %imapath

                                                if len(paths) > 1:
                                                        if frmt == '.cur':
                                                                if name != "":
                                                                        no_err = False
                                                                        message = "Input error: can't create multi-size '.cur'."
                                                                else:
                                                                        # eventually remove duplicate jobs.
                                                                        paths = list(set(paths))
                                                        elif frmt == '.ico':
                                                                if name == "":
                                                                        name = 'multi'
                                else:
                                        no_err = False
                                        message = "Input error: image file/directory path/s not a list of lists."

                                ## Do job.
                                if name != "":
                                        self.add_name2path(name, frmt, indx)
                                if not no_err:
                                        if name == "":
                                                self.add_name2path('noname', frmt, indx)
                                        self.add_errors(message)
                                else:
                                        self.work(paths, name, frmt, hotspot)
                else:
                        print_err("Input error: image file/directory path/s not a list of lists.")

        def convert_8bit_to_4bit(self, bits_8):
                """ Converts 8-bit image data to 4-bit. """
                bits_4 = []
                for i in range(0, len(bits_8), 2):
                        high = bits_8[i]     & 0b11110000
                        low =  bits_8[i + 1] & 0b00001111
                        bits_4 += [high | low]
                return bytes(bits_4)

        def convert_8bit_to_2bit(self, bits_8):
                """ Converts 8-bit image data to 2-bit. """
                bits_2 = []
                for i in range(0, len(bits_8), 4):
                        hh = bits_8[i]      & 0b11000000
                        hl = bits_8[i + 1]  & 0b00110000
                        lh = bits_8[i + 2]  & 0b00001100
                        ll = bits_8[i + 3]  & 0b00000011
                        bits_2 += [hh | hl | lh | ll]
                return bytes(bits_2)

        def convert_16bit_to_8bit(self, bits_16):
                """ Converts 16-bit image data to 8-bit """
                pass

        def get_bgra(self, image, pad):
                """ Gets image data for RGBA. """
                try:
                        dataimage = image.tobytes('raw', 'BGRA', pad, -1)
                except SystemError:
                        # workaround for earlier versions.
                        r, g, b, a = image.split()
                        image = Image.merge('RGBA', (b, g, r, a))
                        dataimage = image.tobytes('raw', 'BGRA', pad, -1)
                return dataimage

        def extract(self, path):
                """ Gets parameters input image. """
                ## Open image in-memory as '.png'.
                _, ext = splitext(path)
                try:
                        image = Image.open(path, 'r')
                except:
                        raise EncodeErr(code = 1, msg = "Image error: format '%s' not recognized or corrupted." %ext)

                imagebyte = BytesIO()
                try:
                        image.save(imagebyte, format = 'PNG')
                except:
                        raise EncodeErr(code = 1, msg = "Image error: format '%s' not recognized or corrupted." %ext)
                dataimage = imagebyte.getvalue()
                image = Image.open(imagebyte)

                self.parameters['bWidth'], self.parameters['bHeight'] = image.size
                self.mode = image.mode

                ## PNG color type represent sums of this values: 1 (palette used), 2 (color used) and 4 (alpha channel used)
                ## Color Option     -   Channels  -  Bits per channel - Bits per pixel - Color type - Interpretation
                ##  indexed                 1           1,2,4,8             1,2,4,8           3        each pixel is a palette index
                ##  grayscale               1           1,2,4,8,16          1,2,4,8,16        0        each pixel is a grayscale sample
                ##  grayscale+alpha         2           8,16                16,32             4        each pixel is a grayscale sample followed by an alpha sample
                ##  truecolor               3           8,16                24,48             2        each pixel is an R,G,B triple
                ##  truecolor+alpha         4           8,16                32,64             6        each pixel is an R,G,B triple followed by an alpha sample

                with open(path, 'rb') as file:
                        data = file.read(30)
                bitdepth, coltyp = unpack_from('<2B', data[24 : 26])
                self.parameters['wBitCount'] = len(image.getbands()) * bitdepth

                if coltyp == 4 and self.mode == 'RGBA':
                        # fix this PIL mode.
                        self.mode, self.parameters['wBitCount'] = ('LA', int(self.parameters['wBitCount'] / 2))

                dict_colortype = {0 : (['1', 'I', 'L'], 'grayscale'),
                                  2 : (['RGB'],         'truecolor'),
                                  3 : (['P'],           'indexed'),
                                  4 : (['LA'],          'grayscale+alpha'),
                                  6 : (['RGBA'],        'truecolor+alpha')
                                  }
                try:
                        assert self.mode in dict_colortype[coltyp][0]
                except AssertionError:
                        raise EncodeErr(code = 2, msg = "Image error: malformed.")

                dizio = {'file' : path,
                         'mode' : dict_colortype[coltyp][1],
                         'depth' : self.parameters['wBitCount']}

                if self.path_icocur not in self.all_icocur_written:
                        self.all_icocur_written[self.path_icocur] = [dizio]
                else:
                        self.all_icocur_written[self.path_icocur].extend([dizio])

                return image

        def load(self, path_image):
                """ Loads input image data. """
                ## Get parameters.
                image = self.extract(path_image)

                ## Manage resize.
                image = self.ico_resize(image, how = self.type_resize, method = Image.ANTIALIAS)

                ## Manage ICC profile.
                if 'icc_profile' in image.info:
                        icc = mkstemp(suffix = '.icc')[1]
                        with open(icc, 'wb') as iccfile:
                                iccfile.write(image.info.get('icc_profile'))
                        srgb = ImageCms.createProfile('sRGB')
                        image = ImageCms.profileToProfile(image, icc, srgb)

                ##                                    | force_to = 'original' | force_to |
                ##--------------------------------------------------------------------
                ## monochrome 1bpp ("1")              | "1"
                ## grayscale 2bpp ("L;2")             | "L;2"
                ## grayscale 4bpp ("L;4")             | "L;4"
                ## grayscale 8bpp ("L")               | "L"
                ## indexed 1bpp ("P;1")               | "P;1"
                ## indexed 2bpp ("P;2")               | "P;2"
                ## indexed 4bpp ("P;4")               | "P;4"
                ## indexed 8bpp ("P")                 | "P"
                ## high-color 16bpp ("I;16")          | "RGBA5551;16"
                ## grayscale+alpha 16bpp ("LA;16")    | "RGBA;32"
                ## grayscale+alpha 32bpp ("LA;32")    | "RGBA;32"
                ## true-color 24bpp ("RGB;24")        | "RGB;24"
                ## deep-color 48bpp ("RGB;48")        | "RGB;24"
                ## true-color+alpha 32bpp ("RGBA;32") | "RGBA;32"
                ## true-color+alpha 64bpp ("RGBA;64") | "RGBA;32"
                ## any mode with indexed transparency | "RGBA;32"

                # Modes that needs always forced conversion.
                forced = True
                if (self.mode == 'LA' and self.parameters['wBitCount'] in [16, 32]) \
                   or ('transparency' in image.info) \
                   or (self.mode == 'RGBA' and self.parameters['wBitCount'] == 64):
                        image = image.convert('RGBA')
                        self.mode, self.parameters['wBitCount'], string_mode = image.mode, 32, 'truecolor+alpha'
                elif (self.mode == 'RGB' and self.parameters['wBitCount'] == 48):
                        image = image.convert('RGB')
                        self.mode, self.parameters['wBitCount'], string_mode = image.mode, 24, 'truecolor'
                else:
                        forced = False

                if forced:
                        dizio = {'new_mode' : string_mode,
                                 'new_depth' : self.parameters['wBitCount']
                                 }
                        self.all_icocur_written[self.path_icocur][self.index].update(dizio)

                ## Continue loading data.
                if self.mode == 'I':
                        self.mode = 'L'
                        table = [i / (2 ** int(self.parameters['wBitCount'] / 2)) for i in range(2 ** self.parameters['wBitCount'])]
                        image = image.point(table, self.mode)
                else:
                        image = image.convert(self.mode)

                if self.mode in ['1', 'L', 'I']:
                        if self.parameters['wBitCount'] in [1, 8]:
                                pad = calc_rowsize(self.parameters['wBitCount'], self.parameters['bWidth'])
                        elif self.parameters['wBitCount'] in [2, 4, 16]:
                                pad = calc_rowsize(8, self.parameters['bWidth'])

                        dataimage = image.tobytes('raw', self.mode, pad, -1)
                        if self.parameters['wBitCount'] == 2:
                                # tobytes() not include a raw L;2
                                dataimage = self.convert_8bit_to_2bit(dataimage)
                        elif self.parameters['wBitCount'] == 4:
                                # tobytes() not include a raw L;4
                                dataimage = self.convert_8bit_to_4bit(dataimage)
                        elif self.parameters['wBitCount'] == 16:
                                # PIL I;16 converted to ABGR1555 format.
                                temp = []
                                for data in dataimage:
                                        value = ((data & 0b10000000) << 8) | ((data & 0b11111000) << 7) | ((data & 0b11111000) << 2) | (data >> 3)
                                        temp.append((value).to_bytes(2, byteorder = 'little'))
                                dataimage = b"".join(temp)

                elif self.mode in ['P', 'RGB', 'RGBA']:
                        pad = calc_rowsize(self.parameters['wBitCount'], self.parameters['bWidth'])
                        if self.parameters['wBitCount'] == 1:
                                dataimage = image.tobytes('raw', 'P;1', pad, -1)
                        elif self.parameters['wBitCount'] == 2:
                                # tobytes() not include a raw P;2
                                pad = calc_rowsize(8, self.parameters['bWidth'])
                                dataimage = image.tobytes('raw', self.mode, pad, -1)
                                dataimage = self.convert_8bit_to_2bit(dataimage)
                        elif self.parameters['wBitCount'] == 4:
                                dataimage = image.tobytes('raw', 'P;4', pad, -1)
                        elif self.parameters['wBitCount'] == 8:
                                dataimage = image.tobytes('raw', 'P', pad, -1)
                        elif self.parameters['wBitCount'] == 24:
                                dataimage = image.tobytes('raw', 'BGR', pad, -1)
                        elif self.parameters['wBitCount'] == 32:
                                dataimage = self.get_bgra(image, pad)

                return image, dataimage

        def ico_palette_gpl(self, file):
                """ Gets values from `.gpl` file. """
                palette = []
                with open(file, 'r') as fd:
                        for line in fd.readlines():
                                if not line.lower().startswith(("gimp", "name", "columns", "#")):
                                        for pal in line.strip().split()[0:3]:
                                                palette.append(int(pal))
                return palette

        def ico_palette_add(self, values):
                """ Adds 4th element (b'\x00') to RGB palette entries. """
                self.parameters['palette'] = bytes(list(chain(*[values[i : i + 3] + [0] \
                                                                if len(values[i : i + 3]) == 3 \
                                                                else values[i : i + 3] \
                                                                for i in range(0, len(values), 3)])))
        def ico_palette(self, image):
                """ Makes some operations on palettes. """
                self.parameters['palette'], self.parameters['size_pal'] = b"", 0
                adjust, is_fallback = (False for _ in range(2))

                ## Assign/create palette.
                if self.parameters['wBitCount'] <= 8:
                        if not image.palette:
                                if self.custom_palettes:
                                        if isinstance(self.custom_palettes, dict):
                                                try:
                                                        palvalues = self.custom_palettes[(self.mode, self.parameters['wBitCount'])]
                                                except:
                                                        print_err("Input error: option `custom_palettes` not proper defined.")
                                        else:
                                                print_err("Input error: option `custom_palettes` not proper defined.")
                                else:
                                        is_fallback = True
                                        fallback_palettes = {('1', 1) : self.ico_palette_gpl(join(working_path, 'palettes/11.gpl')),
                                                             ('L', 2) : self.ico_palette_gpl(join(working_path, 'palettes/L2.gpl')),
                                                             ('L', 4) : self.ico_palette_gpl(join(working_path, 'palettes/L4.gpl')),
                                                             ('L', 8) : self.ico_palette_gpl(join(working_path, 'palettes/L8.gpl')),
                                                             ('P', 1) : self.ico_palette_gpl(join(working_path, 'palettes/P1.gpl')),
                                                             ('P', 2) : self.ico_palette_gpl(join(working_path, 'palettes/P2.gpl')),
                                                             ('P', 4) : self.ico_palette_gpl(join(working_path, 'palettes/P4.gpl')),
                                                             ('P', 8) : self.ico_palette_gpl(join(working_path, 'palettes/P8.gpl')),
                                                             }
                                        palvalues = fallback_palettes[(self.mode, self.parameters['wBitCount'])]

                                if isinstance(palvalues, list):
                                        if all(isinstance(pal, tuple) and len(pal) == 3 and all(isinstance(num, int) for num in pal) for pal in palvalues):
                                                accpal = []
                                                for pal in palvalues:
                                                        accpal += pal + (0,)
                                                self.parameters['palette'] = bytes(accpal)
                                        elif all(isinstance(pal, int) for pal in palvalues):
                                                if is_fallback:
                                                        self.ico_palette_add(palvalues)
                                                else:
                                                        self.parameters['palette'] = bytes([elem for quad in [[pal] * 3 + [0] for pal in palvalues] for elem in quad])
                                        else:
                                                print_err("Input error: option `custom_palettes` not proper defined.")
                                elif isfile(palvalues) and palvalues.endswith('.gpl'):
                                        palvalues = palette_gpl(palvalues)
                                        self.ico_palette_add(palvalues)
                                else:
                                        print_err("Input error: option `custom_palettes` not proper defined.")
                        else:
                                adjust = True
                                self.parameters['palette'] = image.palette.palette

                ## Define length of the palette.
                self.parameters['size_pal'] = len(self.parameters['palette'])

                ## Count palette entries.
                if self.parameters['wBitCount'] <= 8:
                        if (self.parameters['size_pal'] % 3 == 0) and (self.parameters['size_pal'] % 4 == 0):
                                rsv = [self.parameters['palette'][i + 3 : i + 4] for i in range(0, self.parameters['size_pal'], 4)]
                                if len(set(rsv)) <= 1:
                                        # palette RGBA.
                                        self.parameters['bColorCount'] = self.parameters['size_pal'] // 4
                                else:
                                        # palette RGB.
                                        adjust = True
                                        self.parameters['bColorCount'] = self.parameters['size_pal'] // 3
                        else:
                                if self.parameters['size_pal'] % 3 == 0:
                                        adjust = True
                                        self.parameters['bColorCount'] = self.parameters['size_pal'] // 3
                                elif self.parameters['size_pal'] % 4 == 0:
                                        self.parameters['bColorCount'] = self.parameters['size_pal'] // 4

                        if self.parameters['bColorCount'] >= 256:
                                self.parameters['bColorCount'] = 0
                else:
                        self.parameters['bColorCount'] = 0

                ## Transform palette.
                if adjust:
                        temp, step = [], 3
                        for i in range(0, len(self.parameters['palette']), step):
                                # from (RGB or RGBA) to (BGRA) palette.
                                temp.append(self.parameters['palette'][i : i + step][::-1] + b'\x00')
                        self.parameters['palette'] = b"".join(temp)

        def ico_resize(self, image, how = 'up256_prop', method = Image.ANTIALIAS):
                """ Resizes to `.ico` / `.cur` dimensions. """
                old_w, old_h = image.size
                sizes = [16, 24, 32, 48, 64, 128, 256]

                self.all_icocur_written[self.path_icocur][self.index].update({'size' : '%s x %s' %(old_w, old_h)})

                resized = True
                if how in ['up256_prop', 'up256_no_prop']:
                        if old_w > sizes[-1]:
                                if how == 'up256_prop':
                                        image.thumbnail((sizes[-1], old_h), method)
                                elif how == 'up256_no_prop':
                                        image = image.resize((sizes[-1], old_h), method)
                        elif old_h > sizes[-1]:
                                if how == 'up256_prop':
                                        image.thumbnail((old_w, sizes[-1]), method)
                                elif how == 'up256_no_prop':
                                        image = image.resize((old_w, sizes[-1]), method)
                        elif (old_h > 256) and (old_w > 256):
                                if how == 'up256_prop':
                                        image.thumbnail((sizes[-1], sizes[-1]), method)
                                elif how == 'up256_no_prop':
                                        image = image.resize((sizes[-1], sizes[-1]), method)
                        else:
                                resized = False
                elif how == 'square':
                        new_d = min(sizes, key = lambda x : abs(x - max(old_w, old_h)))
                        image = image.resize((new_d, new_d), method)
                elif isinstance(how, tuple):
                        image = image.resize(how, method)

                if resized:
                        self.parameters['bWidth'], self.parameters['bHeight'] = image.size
                        self.all_icocur_written[self.path_icocur][self.index].update({'resize' : '%s x %s' %(self.parameters['bWidth'],
                                                                                                             self.parameters['bHeight'])})
                return image

        def header_icondir(self):
                """ Defines the ICONDIR header. """
                ## (2bytes)idReserved (always 0) - (2bytes)idType (ico=1, cur=2) - (2bytes)idCount.
                self.parameters['bReserved'] = 0
                return pack('3H', self.parameters['bReserved'], self.parameters['idType'], self.parameters['idCount'])

        def header_bmpinfo(self):
                """ Defines the BMPINFO header. """
                ## (4bytes)biSize - (4bytes)biWidth - (4bytes)biHeight - (2bytes)biPlanes - (2bytes)biBitCount -
                ## - (4bytes)biCompression - (4bytes)biSizeImage -
                ## - (4bytes)biXPelsPerMeter - (4bytes)biYPelsPerMeter - (4bytes)biClrused - (4bytes)biClrImportant.
                biSize = calcsize('3I2H2I2i2I')
                biWidth = self.parameters['bWidth']
                # include the mask height
                biHeight = self.parameters['bHeight'] * 2
                # color planes must be 1
                biPlanes = 1
                # 1, 2, 4, 8, 16, 24, 32
                biBitCount = self.parameters['wBitCount']
                # only uncompressed images BI_RGB.
                biCompression = 0
                # calculate sizes XOR, AND masks.
                self.parameters['size_xor'] = calc_rowsize(self.parameters['wBitCount'], self.parameters['bWidth']) * self.parameters['bHeight']
                self.parameters['size_and'] = calc_masksize(self.parameters['bWidth']) * self.parameters['bHeight']
                biSizeImage = self.parameters['size_xor'] + self.parameters['size_and']
                biXPelsPerMeter = 0
                biYPelsPerMeter = 0
                biClrUsed = self.parameters['bColorCount']
                biClrImportant = 0

                return pack('3I2H2I2i2I', biSize, biWidth, biHeight, biPlanes, biBitCount, biCompression, biSizeImage,
                                          biXPelsPerMeter, biYPelsPerMeter, biClrUsed, biClrImportant)

        def to_icocur(self, path_image, hotspot):
                """ Creates result of conversion. """
                image, xordata = self.load(path_image)
                if hotspot != "":
                        self.all_icocur_written[self.path_icocur][self.index].update({'hotspot_x' : hotspot[0],
                                                                                      'hotspot_y' : hotspot[1]})
                self.parameters['wPlanes'] = 0

                ## Identify palette.
                self.ico_palette(image)

                ## Keep offset.
                dataoffset = self.parameters['dwImageOffset']

                ## Generate BITMAPINFO header.
                icobytes = self.header_bmpinfo()

                # Write palette.
                if self.parameters['palette']:
                        icobytes += self.parameters['palette']

                ## Write XOR mask.
                icobytes += xordata

                ## Write AND mask.
                if self.mode == 'RGBA':
                        icobytes += Mask().compute_AND_mask(self.parameters['bWidth'], self.parameters['bHeight'], xordata)
                else:
                        icobytes += pack('B', 0) * self.parameters['size_and']

                ## Increment offset.
                self.parameters['dwImageOffset'] += len(icobytes)
                ## Calculate size of (icondirentry + image data).
                self.parameters['dwBytesInRes'] = len(icobytes)
                ## Define correct dimension, 0 means 256 (or more).
                if self.parameters['bWidth'] >= 256: self.parameters['bWidth'] = 0
                if self.parameters['bHeight'] >= 256: self.parameters['bHeight'] = 0

                ## Pack icondirentry header.
                icondirentry = pack('4B2H2I', self.parameters['bWidth'], self.parameters['bHeight'], self.parameters['bColorCount'],
                                              self.parameters['bReserved'],
                                             (self.parameters['wPlanes'] if hotspot == "" else hotspot[0]),
                                             (self.parameters['wBitCount'] if hotspot == "" else hotspot[1]),
                                              self.parameters['dwBytesInRes'], dataoffset)

                return icondirentry, icobytes

        def printsave(self, how, header, data, hotspot):
                """ Saves conversion file and print results. """

                def printresult(indx):
                        result = self.all_icocur_written[self.path_icocur][indx]
                        self.print_std('\nfile = %s' %result['file'])
                        self.print_std('{:<30} {:>10} {:>10}'.format('mode = %s' %result['mode'],
                                                                     'depth = %s' %result['depth'],
                                                                     'size = %s' %result['size']))

                        if 'new_mode' in result:
                                if 'resize' in result:
                                        self.print_std('{:<30} {:>10} {:>10}'.format('new mode = %s' %result['new_mode'],
                                                                                     'new depth = %s' %result['new_depth'],
                                                                                     'resize = %s' %result['resize']))
                                else:
                                        self.print_std('{:<30} {:>10}'.format('new mode = %s' %result['new_mode'],
                                                                              'new depth = %s' %result['new_depth']))
                        else:
                                if 'resize' in result:
                                        self.print_std('{:<30} {:>10} {:>10}'.format("", "", 'resize = %s' %result['resize']))

                        if hotspot != "":
                                self.print_std('{:<30} {:>10} {:>10}'.format("", "", 'hotspot = %s' %str(hotspot)))

                # printing process.
                if how == 'single':
                        printresult(0)
                        self.print_std('saved = %s' %self.path_icocur)
                elif how == 'multi':
                        for indx in range(self.parameters['idCount']):
                                printresult(indx)
                        self.print_std('\nsaved = %s' %self.path_icocur)
                # save.
                with open(self.path_icocur, 'wb') as f_ico:
                        f_ico.write(header)
                        f_ico.write(data)

        def work(self, paths, name, frmt, hotspot):
                """ Executes conversion job."""
                self.parameters = {}

                if frmt == '.ico':
                        self.parameters['idType'] = 1
                elif frmt == '.cur':
                        self.parameters['idType'] = 2

                if name == "":
                        how = 'single'
                        path_temp = self.path_icocur
                else:
                        how = 'multi'
                        ## Define header of `.ico` file.
                        self.parameters['idCount'] = len(paths)
                        icocur_header, icocur_data = self.header_icondir(), b""
                        ## Size of all the headers (image headers + file header)
                        ## (1byte)bWidth - (1byte)bHeight - (1byte)bColorCount - (1byte)bReserved -
                        ## -(2bytes)wPlanes - (2bytes)wBitCount - (4bytes)dwBytesInRes - (4bytes)dwImageOffset.
                        self.parameters['dwImageOffset'] = calcsize('4B2H2I') * self.parameters['idCount'] + calcsize('HHH')

                ## Create `.ico` / `.cur`.
                for self.index, path_image in enumerate(paths):
                        try:
                                if how == 'single':
                                        self.index = 0
                                        self.parameters['idCount'] = 1
                                        icocur_header, icocur_data = self.header_icondir(), b""
                                        self.parameters['dwImageOffset'] = calcsize('4B2H2I') * self.parameters['idCount'] + calcsize('HHH')
                                        self.path_icocur = join(path_temp, splitext(basename(path_image))[0] + frmt)

                                icondirentry, icobytes = self.to_icocur(path_image, hotspot)
                                icocur_header += icondirentry
                                icocur_data += icobytes

                                if how == 'single':
                                        ## Save `.ico` / `.cur` (single).
                                        self.printsave(how, icocur_header, icocur_data, hotspot)
                                elif how == 'multi':
                                        ## Save `.ico` / `.cur` (multi).
                                        if self.index == self.parameters['idCount'] - 1:
                                                self.printsave(how, icocur_header, icocur_data, hotspot)

                        except EncodeErr as e:
                                self.all_icocur_written.update({self.path_icocur : e.msg})
                                self.print_err(e.msg, toexit = (False if how == 'single' else True))
                                if how == 'single':
                                        continue
                                elif how == 'multi':
                                        return

if __name__ == "__main__":
        is_cli = True
        opts = iconolatry_parser()
        if opts['mode'] == 'decode':
                Decode(opts['paths_icocurs'],
                       paths_image = opts['paths_image'],
                       names_image = opts['names_image'],
                       formats_image = opts['formats_image'],
                       rebuild = opts['rebuild'])
        elif opts['mode'] == 'encode':
                Encode(opts['paths_images'],
                       paths_icocur = opts['paths_icocur'],
                       names_icocur = opts['names_icocur'],
                       formats_icocur = opts['formats_icocur'],
                       type_resize = opts['type_resize'],
                       force_to = opts['force_to'],
                       custom_palettes = opts['custom_palettes'])
        elif opts['mode'] is None:
                is_cli = False
