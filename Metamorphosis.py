#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import Iconolatry
import os
import re
import logging
import argparse
from time import perf_counter
from zlib import decompress
from struct import unpack_from, calcsize
from PIL import Image
from stat import S_IWRITE
from shutil import rmtree
from math import ceil
from subprocess import Popen, PIPE
from zipfile import ZipFile
from io import BytesIO
from itertools import chain
from shutil import make_archive
from tempfile import gettempdir
from hashlib import md5
from collections import OrderedDict

__version__     = "V (Reborn)"
__license__     = "GPL-3.0 License"
__author__      = u"Matteo ℱan <SystemRage@protonmail.com>"
__copyright__   = "© Copyright 2018-2021"
__url__         = "https://github.com/SystemRage/Metamorphosis"
__summary__     = "The Ultimate Cursor Converter"

## _________________________________________
##| Support to "repeat"/"end repeat" loops  |--------------------------------------------------------------------------------------------------------------
##|_________________________________________|
##

class Repeat(object):
        def __init__(self, script):
                self.script = script
                self.start, self.stop, self.nloops = ([] for _ in range(3))
                self.loop_expand()

        def loop_limit(self):
                """ Defines all start loops indexes ('repeat N'),
                    all stop loops indexes ('end repeat') and all number of repetitions ('N').
                """
                for indx, line in enumerate(self.script):
                        if line.startswith('repeat'):
                                self.start.append(indx)
                                self.nloops.append(int(re.split('\s', line)[1]))
                        elif line.startswith('end'):
                                self.stop.append(indx)

        def loop_flatten(self, lst):
                """ Transforms a list of lists to a flat list. """
                for elem in lst:
                        if hasattr(elem, '__iter__') and not isinstance(elem, (str, bytes)):
                                yield from self.loop_flatten(elem)
                        else:
                                yield elem

        def loop_expand(self):
                """ Expands not nested or nested loops or any combination of both. """
                self.loop_limit()

                while self.start != []:
                        ## Calculate distances between first stop index with all start indexes.
                        dist = [self.stop[0] - self.start[i] for i in range(len(self.start))]
                        ## Find index of distances where there's min positive distance.
                        min_dist = min(i for i in dist if i > 0)
                        index_min_dist = dist.index(min_dist)
                        ## Create loop extension and calculate the number of elements to insert.
                        chunk = self.script[self.start[index_min_dist] + 1 : self.stop[0]] * self.nloops[index_min_dist]
                        nadj = (self.stop[0] - (self.start[index_min_dist] + 1)) * self.nloops[index_min_dist]
                        ## Remove in the script the loop in exam and calculate the number of elements erased.
                        self.script[self.start[index_min_dist] : self.stop[0] + 1] = []
                        ndel = self.stop[0] + 1 - self.start[index_min_dist]
                        ## Insert loop extension at right place and flatten.
                        self.script.insert(self.start[index_min_dist], chunk)
                        self.script = list(self.loop_flatten(self.script))

                        shift = nadj - ndel
                        ## Shift all start indexes after the used one.
                        shifted_start = [x + shift for x in self.start[index_min_dist + 1::]]
                        self.start = self.start[0 : index_min_dist + 1] + shifted_start
                        ## Shift all stop indexes after the first.
                        shifted_stop = [x + shift for x in self.stop[1::]]
                        self.stop = self.stop[0 : 1] + shifted_stop
                        ## Update lists removing used elements.
                        self.start.pop(index_min_dist)
                        self.stop.pop(0)
                        self.nloops.pop(index_min_dist)


## _________________________________
##| Generic functions and variables |------------------------------------------------------------------------------------------------------------------------
##|_________________________________|
##

script_pattern = re.compile(r'(\d+)(?:-(\d+))?(?:,(\d+))?')

label = "*Converted by Metamorphosis, {}*".format(__copyright__)

working_path = os.path.abspath('.')

""" Cursor names.
    the list of output file names are based on http://fedoraproject.org/wiki/Artwork/EchoCursors/NamingSpec.
    NameCursorFX:((NameCursorXP), (NameCursorWindows), (LinkforLinux), (NamesCursorLinux))
"""
## TODO: To assign : dotbox, dot-box, dot_box, dot_box_mask, draped_box, draped-box, icon, target, zoom-in, zoom-out
cursor_namemap = {
                  # Cursor shape arrow.
                  0  : (('Arrow'),        ('Arrow'),      ('00normal_select'),             ('default','arrow',
                                                                                            'top-left-arrow','top_left_arrow',
                                                                                            'left_ptr',
                                                                                            'x-cursor','X_cursor')),
                  # Cursor guide (arrow with ?).
                  1  : (('Help'),         ('Help'),       ('01help_select'),               ('ask','dnd-ask',
                                                                                           'help','question_arrow','whats_this',
                                                                                           '5c6cd98b3f3ebcb1f9c7f1c204630408',
                                                                                           'left_ptr_help',
                                                                                           'd9ce0ab605698f320427677b458ad60b')),
                  # Cursor applications start.
                  2  : (('AppStarting'),  ('AppStarting'),('02working_in_background'),     ('progress','left_ptr_watch',
                                                                                            '08e8e1c95fe2fc01f976f1e063a24ccd',
                                                                                            '3ecb610c1bf2410f44200f48c40d3599')),
                  # Cursor wait.
                  3  : (('Wait'),         ('Wait'),       ('03busy'),                      ('wait','watch',
                                                                                            '0426c94ea35c87780ff01dc239897213')),
                  # Cursor precision selection.
                  4  : (('Cross'),        ('Crosshair'),  ('04precision_select'),          ('crosshair','cross',
                                                                                            'diamond_cross',
                                                                                            'cross_reverse','tcross')),
                  # Cursor text.
                  5  : (('IBeam'),        ('IBeam'),      ('05text_select'),               ('text','xterm',
                                                                                            'ibeam','vertical-text')),
                  # Cursor shape pen.
                  6  : (('Handwriting'),  ('NWPen'),      ('06handwriting'),               ('pencil',)),

                  # Cursor area not allowed.
                  7  : (('NO'),           ('No'),         ('07unavailable'),               ('no-drop','dnd-none','circle',
                                                                                            '03b6e0fcb3499374a867c041f52298f0',
                                                                                            'not-allowed','crossed_circle',
                                                                                            'forbidden','pirate')),
                  # Cursor resize two arrows pointing to N and S.
                  8  : (('SizeNS'),       ('SizeNS'),     ('08north_resize'),              ('col-resize','sb_v_double_arrow',
                                                                                            'split_v','14fef782d02440884392942c11205230',
                                                                                            'n-resize','top_side','ns-resize','v_double_arrow',
                                                                                            'size_ver','00008160000006810000408080010102',
                                                                                            'top-tee','top_tee',
                                                                                            'double_arrow','double-arrow'
                                                                                            'up','sb_up_arrow')),
                  # Cursor resize two arrows pointing to N.
                  9  : (('SizeS'),        ('SizeS'),      ('09south_resize'),              ('bottom-tee','bottom_tee','down',
                                                                                            'sb_down_arrow','s-resize',
                                                                                            'bottom_side')),
                  # Cursor resize two arrows pointing to W and E.
                  10 : (('SizeWE'),       ('SizeWE'),     ('10west_resize'),               ('ew-resize','h_double_arrow',
                                                                                            'size_hor','028006030e0e7ebffc7f7070c0600140',
                                                                                            'left','sb_left_arrow','left-tee','left_tee',
                                                                                            'row-resize','sb_h_double_arrow','split_h',
                                                                                            '2870a09082c103050810ffdffffe0204',
                                                                                            'w-resize','left_side')),
                  # Cursor resize one arrow pointing to W.
                  11 : (('SizeE'),        ('SizeE'),      ('11east_resize'),               ('e-resize','right_side','right','sb_right_arrow',
                                                                                            'right-tee','right_tee')),
                  # Cursor resize two arrows pointing to NW and SE.
                  12 : (('SizeNWSE'),     ('SizeNWSE'),   ('12northwest_resize'),          ('nw-resize','top_left_corner','ul_angle',
                                                                                            'nwse-resize','fd_double_arrow','size_fdiag',
                                                                                            'c7088f0f3e6c8088236ef8e1e3e70000')),
                  # Cursor resize one arrow pointing to NW.
                  13 : (('SizeSE'),       ('SizeSE'),     ('13southeast_resize'),          ('se-resize','lr_angle',
                                                                                            'bottom_right_corner')),
                  # Cursor resize two arrows pointing to NE and SW.
                  14 : (('SizeNESW'),     ('SizeNESW'),   ('14northeast_resize'),          ('ne-resize','top_right_corner','ur_angle',
                                                                                            'nesw-resize','bd_double_arrow','size_bdiag',
                                                                                            'fcf1c3c7cd4491d801f1e1c78f100000')),
                  # Cursor resize one arrow pointing to NE.
                  15 : (('SizeSW'),       ('SizeSW'),     ('15southwest_resize'),          ('sw-resize','ll_angle',
                                                                                            'bottom_left_corner')),
                  # Cursor resize with four arrows pointing to N/S/W/E.
                  16 : (('SizeAll'),      ('SizeAll'),    ('16move'),                      ('cell','plus','all-scroll','fleur',
                                                                                            'size_all')),
                  # Cursor arrow upside for an insertion point.
                  17 : (('UpArrow'),      ('UpArrow'),    ('17alternate_select'),          ('top-right-arrow','right_ptr','move','dnd-move',
                                                                                            '4498f0e0c1937ffe01fd06f973665830',
                                                                                            '9081237383d90e509aa00f00170e968f',
                                                                                            'draft_large','draft_small'
                                                                                            'up-arrow','up_arrow','center_ptr')),
                  # Cursor shape hand.
                  18 : (('Hand'),         ('Hand'),       ('18hand'),                      ('alias','link','dnd-link',
                                                                                            '3085a0e285430894940527032f8b26df',
                                                                                            '640fb0e74195791501fd1ed57b41487f',
                                                                                            '9d800788f1b08800ae810202380a0822',
                                                                                            'e29285e634086352946a0e7090d73106',
                                                                                            'a2a266d0498c3104214a47bd64ab0fc8',
                                                                                            'b66166c04f8c3109214a4fbd64a50fc8',
                                                                                            'left-hand','hand1','pointer','hand2',
                                                                                            'grab','grabbing'
                                                                                            'pointing_hand','openhand','hand')),
                  # Cursor default with a small plus sign next to it.
                  19 : (('Button'),       ('Button'),     ('19button'),                    ('copy','dnd-copy',
                                                                                            '1081e37283d90000800003c07f3ef6bf',
                                                                                            '6407b0e94181790501fd1e167b474872'))
                  }

class ExtendAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string = None):
                items = getattr(namespace, self.dest) or []
                items.extend(values)
                setattr(namespace, self.dest, items)

def metamorphosis_parser():
        """ CLI parser. """
        options = {}
        morph_parser = argparse.ArgumentParser(description = __summary__, epilog = 'version: ' + __version__, add_help = False, allow_abbrev = False)
        morph_parser.register('action', 'extend', ExtendAction)
        morph_required = morph_parser.add_argument_group('required arguments')

        morph_required.add_argument('-i', '--input', required = True, nargs = "+", action = "extend", default = [], type = str,
                                    dest = "input",
                                    help = "Path(s) of cursor file(s) or folder(s) to convert.")

        morph_optional = morph_parser.add_argument_group('optional arguments')
        morph_optional.add_argument('-h', '--help', action = "help", default = argparse.SUPPRESS,
                                    help = "show this help message and exit")

        morph_optional.add_argument('-o', '--output', action = "store", default = working_path, type = str,
                                    dest = "output",
                                    help = "Path of converted cursor(s). Default is your working directory.")
        morph_optional.add_argument('-p', '--pack', action = 'store_true', default = False,
                                    dest = "pack",
                                    help = "Enable packing converted cursors. Disabled by default")
        morph_optional.add_argument('-r', '--crop', action = 'store_false', default = True,
                                    dest = "crop",
                                    help = "Disable removing transparent border. Enabled by default.")
        morph_optional.add_argument('-s', '--size', action = 'store', default = 16, choices = [16, 24, 32, 48, 64, 96], type = int,
                                    dest = "size",
                                    help = "Select size (in pixels) for converted cursors. Default is `16` pixels.")
        morph_optional.add_argument('-c', '--color', action = 'store', default = 'rgb', choices = ['rgb', 'rbg', 'grb', 'brg', 'gbr', 'bgr'], type = str,
                                    dest = "color",
                                    help = "Select color change for converted cursors. Default is `rgb`.")
        morph_optional.add_argument('-t', '--platform', action = 'store', default = 'Linux', choices = ['Linux', 'Windows'], type = str,
                                    dest = "platform",
                                    help = "Select destination OS for converted cursors. Default is `Linux` platform.")

        try:
                options.update(vars(morph_parser.parse_args()))
                ## Define size as tuple (width and height).
                options['size'] = (options['size'], options['size'])
        except Exception as e:
                raise e

        return options


## ________________________
##| Image editor functions |---------------------------------------------------------------------------------------------------------------------------------
##|________________________|
##

class Editor(object):
        def __init__(self, parameters, options):
                self.parameters = parameters
                self.options = options

        def resize_meth(self, image, method = Image.LANCZOS):
                """ Resizes PIL image to a maximum size specified maintaining the aspect ratio.
                    Allows usage of different resizing methods and does not modify the image in place,
                    then creates an exact square image.
                """
                w_fin, h_fin = self.options['size']
                w_ini, h_ini = image.size

                ini_aspect = float(w_ini) / float(h_ini)
                fin_aspect = float(w_fin) / float(h_fin)

                if ini_aspect >= fin_aspect:
                        ## Set w to (final width).
                        ## Set h to (final width / initial aspect ratio).
                        image = image.resize((w_fin, int((float(w_fin) / ini_aspect) + 0.5)), method)
                else:
                        ## Set w to (final height * initial aspect ratio).
                        ## Set h to (final height).
                        image = image.resize((int((float(h_fin) * ini_aspect) + 0.5), h_fin), method)

                ## Create background transparent image.
                thumbnail = Image.new('RGBA', self.options['size'], (255, 255, 255, 0))
                thumbnail.paste(image, ((w_fin - image.size[0]) // 2, (h_fin - image.size[1]) // 2))

                return thumbnail

        def resize_exec(self, image_list):
                """ Applies icon dimensions resize to image list and adjusts hotspots. """
                w_fin, h_fin = self.options['size']
                w_ini, h_ini = image_list[0].size
                scale_x = w_fin / w_ini
                scale_y = h_fin / h_ini

                image_list = [self.resize_meth(image_list[i], method = Image.LANCZOS) for i in range(self.parameters['count'])]

                ## Scale hotspots.
                self.parameters['hotx'] = int(0.5 * ceil(2.0 * (self.parameters['hotx'] * scale_x)))
                self.parameters['hoty'] = int(0.5 * ceil(2.0 * (self.parameters['hoty'] * scale_y)))

                return image_list

        def slice(self, image_strip):
                """ Gets images from strip image. """
                image_w, image_h = image_strip.size
                frame_w = int(image_w / self.parameters['count'])
                image_list = [image_strip.crop((frame_w * i, 0, frame_w * (i + 1), image_h)) for i in range(self.parameters['count'])]

                return image_list

        def crop(self, image_list):
                """ Crops border. """
                bbox = [self.parameters['hotx'], self.parameters['hoty'],
                        self.parameters['hotx'] + 1, self.parameters['hoty'] + 1]

                for i in range(self.parameters['count']):
                        tbbox = image_list[i].getbbox()
                        if tbbox is not None:
                                bbox[0] = min(bbox[0], tbbox[0])
                                bbox[1] = min(bbox[1], tbbox[1])
                                bbox[2] = max(bbox[2], tbbox[2])
                                bbox[3] = max(bbox[3], tbbox[3])

                image_list = [image_list[i].crop(bbox) for i in range(self.parameters['count'])]
                self.parameters['hotx'] -= bbox[0]
                self.parameters['hoty'] -= bbox[1]

                return image_list

        def colorize(self, image):
                """ Changes color cursor. """
                ## rgba --> original.
                if self.options['color'] != 'rgb':
                        image = image.convert('RGBA')
                        r, g, b, a = image.split()
                        ch1, ch2, ch3 = list(self.options['color'])
                        ## rbga --> swap green - blue.
                        ## grba --> swap red - green.
                        ## bgra --> inverted.
                        ## brga --> inverted, swap red - green.
                        ## gbra --> inverted, swap green - blue.
                        image = Image.merge('RGBA', (eval(ch1), eval(ch2), eval(ch3), a))

                return image

        def adjust(self, image, extended = True, custom = ''):
                """ Executes some edit operations. """
                if extended:
                        ## Save image strip (format: img0-1.png).
                        path = os.path.join(process.original_dir, "img{:d}-{:d}.png".format(self.parameters['index'], self.parameters['status']))
                        image.save(path, 'PNG')
                        ## Get every frame image from image strip.
                        image = self.slice(image)
                        ## Crop transparent border (eventually).
                        if self.options['crop']:
                                image = self.crop(image)

                ## Resize.
                if self.options['size'] != (0, 0):
                        image = self.resize_exec(image)
                ## Colorize and save images (format: img0-1_0.png).
                for i in range(self.parameters['count']):
                        ima = self.colorize(image[i])
                        path = os.path.join(process.original_dir, ("{}".format(custom) if custom else
                                                                   "img{:d}-{:d}_{:d}.png".format(self.parameters['index'], self.parameters['status'], i)))
                        ima.save(path, 'PNG')


## ______________________________________
##| Parsing script / animation functions |-------------------------------------------------------------------------------------------------------------------
##|______________________________________|
##

class Parser(object):
        def __init__(self, parameters, options):
                self.parameters = parameters
                self.options = options
                self.logger = logging.getLogger('Metamorphosis')

        def cfg_writer(self, cfg, script_index, script_interval, custom = ''):
                """ Support for config files writing. """
                towrite = ''

                if self.options['platform'] == 'Linux':
                        towrite += "{:d} {:d} {:d} ".format(self.options['size'][0], self.parameters['hotx'], self.parameters['hoty'])

                path = (process.icocur_dir if self.options['platform'] == 'Windows' else process.original_dir)
                extension = ('.cur' if self.options['platform'] == 'Windows' else '.png')
                towrite += os.path.join(path, "img{:d}-{:d}_{:d}{}{} {:d}\n".format(self.parameters['index'],
                                                                                    self.parameters['status'], script_index, custom,
                                                                                    extension, script_interval))
                cfg.write(towrite)

        def script(self, cfg, script_data):
                """ Creates the sequence script defined. """
                is_parsed = True

                try:
                        for line in script_data:
                                ## Note examples:
                                ## script_pattern.match('2-5,30').groups() --> ('2', '5', '30')
                                ## script_pattern.match('6-10').groups() --> ('6', '10', None)
                                ## script_pattern.match('1,3000').groups() --> ('1', None, '3000')
                                start_frame, stop_frame, interval = script_pattern.match(line).groups()
                                start_frame = int(start_frame)
                                stop_frame = (int(stop_frame) if stop_frame else start_frame)
                                interval = (int(interval) if interval else self.parameters['interval'])
                                step = (1 if stop_frame >= start_frame else -1)
                                ## Note that the frame index in the script is 1-based.
                                if all(value <= self.parameters['count'] for value in [start_frame, stop_frame]):
                                        for i in range(start_frame, stop_frame + step, step):
                                                self.cfg_writer(cfg, i - 1, interval)
                                else:
                                        self.logger.error('Error: cannot parse script line "{}" --> script indexes mismatch\n'.format(line))
                                        is_parsed = False
                                        break
                except:
                        self.logger.error('Error: cannot parse script line "{}" --> script corrupted\n'.format(line))
                        is_parsed = False

                return is_parsed

        def animation(self, cfg):
                """ Creates the sequence animation defined. """
                if self.parameters['anim'] == 0:
                        # Case animation: NONE
                        for i in range(self.parameters['count']):
                                interval = (self.parameters['interval'] if i < self.parameters['count'] - 1 else 1000000)
                                self.cfg_writer(cfg, i, interval)
                elif self.parameters['anim'] == 2:
                        # Case animation: LOOP
                        for i in range(self.parameters['count']):
                                self.cfg_writer(cfg, i, self.parameters['interval'])
                elif self.parameters['anim'] == 3:
                        # Case animation: ALTERNATE
                        for i in chain(range(self.parameters['count']), range(self.parameters['count'] - 2, -1, -1)):
                                self.cfg_writer(cfg, i, self.parameters['interval'])
                else:
                        self.logger.error('Error: unknown animation type: {:d}\n'.format(self.parameters['anim']))


## _______________________________________
##| Stardock cursors conversion functions |------------------------------------------------------------------------------------------------------------------
##|_______________________________________|
##

class Stardock(object):
        def __init__(self, options):
                self.options = options
                self.logger = logging.getLogger('Metamorphosis')

        def strip_frames(self, image_strip):
                """ Gets image strip frames and adjust them. """
                editor = Editor(self.parameters, self.options)
                editor.adjust(image_strip)

        def script_missing(self, cfg_file):
                """ Defines operations when script missing. """
                self.logger.warning('Warning: script missing: fallback to default animation for image index #{:d}, status {:d}\n'
                                    .format(self.parameters['index'], self.parameters['status']))
                ## Use default animation.
                parser = Parser(self.parameters, self.options)
                parser.animation(cfg_file)

        def script_exist(self, cfg_file, script_data):
                """ Defines operations when script exists. """
                ## Log script lines.
                self.logger.info('\tScript:\n\t\t{}\n'.format('\n\t\t'.join(script_data)))
                ## Eventually expand loops.
                if 'end repeat' in script_data:
                        try:
                                script_data = Repeat(script_data).script
                        except:
                                self.logger.error('Error: cannot expand script --> script corrupted\n')

                ## Parse script.
                parser = Parser(self.parameters, self.options)
                is_parsed = parser.script(cfg_file, script_data)

                if not is_parsed:
                        ## Script not well formatted.
                        self.logger.warning('Warning: script corrupted: fallback to default animation for image index #{:d}, status {:d}\n'
                                            .format(self.parameters['index'], self.parameters['status']))
                        cfg_file.seek(0)
                        ## Using default animation.
                        parser.animation(self.options['size'][0])

        def convert_FX(self, fileFX):
                """ Extracts data from theme file `.cursorFX`, then creates `.ani`s or `X11`s. """
                ## Read data file.
                with open(fileFX, 'rb') as file:
                        data = file.read()

                ## Extract header data.
                self.logger.info('<------>< Info Extraction ><------>\n')
                version, header_size, data_size, theme_type = unpack_from('<4I', data, 0)
                info_size, = unpack_from('<I', data, header_size - 4)
                self.logger.info(u'Header info:\n\n\tVersion: {}\n\tHeader size: {}\n\tData size: {}\n\tTheme type: {}\n\tInfo size: {}\n\n'
                                 .format(version, header_size, data_size, theme_type, info_size))

                ## Extract remaining data.
                data = decompress(data[header_size:])

                try:
                        assert len(data) == data_size
                except AssertionError:
                        self.logger.error('Error: file {} corrupted --> conversion aborted\n'.format(fileFX))
                        return

                ## Get theme info.
                info = data[:info_size].decode('utf-16le').split('\0')[:-1]
                ## Handle theme info data.
                if not info:
                        comment = 'missing'
                        ## Theme name missing in datastream, get it from filename.
                        theme_name = os.path.splitext(os.path.basename(fileFX))[0]
                else:
                        comment = " - ".join(list(" ".join(inf.splitlines()) for inf in info))
                        theme_name = info[0].strip()
                theme_name = theme_name.replace(',', '_').replace(' ', '')
                self.logger.info('Theme info:\n\n\t{}\n\n'.format(comment))

                ## Creation subfolders under `targets` folder.
                process.create_subfolders(theme_name)

                ## Start processing data.
                cur_pos = info_size
                while cur_pos < len(data):
                        ## Extract data.
                        pointer_type, size_of_header_without_script_1, size_of_header_and_image = unpack_from('<3I', data, cur_pos)

                        if pointer_type != 2:
                                self.logger.error('Error: found type #{:d}, not a pointer image --> conversion skipped\n'.format(pointer_type))
                                cur_pos += size_of_header_and_image
                                continue

                        (unknown_1, image_index, cursor_status,
                        unknown_2, frame_count, image_width, image_height, frame_interval, animation_type,
                        unknown_3, mouse_x, mouse_y,
                        size_of_header_with_script, size_of_image,
                        size_of_header_without_script_2, size_of_script) = unpack_from('<16I', data, cur_pos + calcsize('<3I'))

                        self.logger.info('<------>< Image Extraction ><------>\n')
                        self.logger.info(u'Image index #{}:\n\n\tType: {}\n\tUnknown_1: {}\n\tStatus: {}\n\tUnknown_2: {}\n\tFrame count: {}\n\t\
Image size: {} x {}\n\tFrame interval: {}\n\tUnknown_3: {}\n\tAnimation type: {}\n\tHotspot position: ({}, {})\n\tScript size: {}\n'
                                         .format(image_index, pointer_type, unknown_1, cursor_status, unknown_2, frame_count,
                                                 image_width, image_height, frame_interval, unknown_3, animation_type, mouse_x, mouse_y, size_of_script))

                        self.parameters = {'index'    : image_index,
                                           'status'   : cursor_status,
                                           'count'    : frame_count,
                                           'interval' : frame_interval,
                                           'hotx'     : mouse_x,
                                           'hoty'     : mouse_y,
                                           'anim'     : animation_type
                                           }

                        try:
                                assert size_of_header_without_script_1 == size_of_header_without_script_2
                                assert size_of_header_with_script == size_of_header_without_script_1 + size_of_script
                                assert size_of_header_and_image == size_of_header_with_script + size_of_image
                                assert size_of_image == image_width * image_height * 4
                        except AssertionError:
                                self.logger.error('Error: image #{:d} corrupted --> conversion skipped\n'.format(image_index))
                                cur_pos += size_of_header_and_image
                                continue

                        ## Get strip image / strip image frames.
                        image_strip = Image.frombytes('RGBA', (image_width, image_height),
                                                      data[cur_pos + size_of_header_with_script : cur_pos + size_of_header_and_image],
                                                      'raw', 'BGRA', 0, -1)
                        self.strip_frames(image_strip)

                        ## Create config file.
                        with open(process.config(self.parameters), 'w') as cfg_file:
                                if size_of_script > 0:
                                        script_data = data[cur_pos + size_of_header_without_script_1 : cur_pos + size_of_header_with_script].decode('utf-16le')[:-1]
                                        script_data = script_data.replace(';', '\n')
                                        script_data = script_data.splitlines()
                                        script_data = [re.sub(r'(?:(?<=\,|-)\s*|\s*(?=\,|-))', '', ' '.join(line.split())) for line in script_data]
                                        self.script_exist(cfg_file, script_data)
                                elif size_of_script == 0:
                                        self.script_missing(cfg_file)

                        ## Generate.
                        gen_instance = process.generate(self.parameters, theme_name)

                        cur_pos += size_of_header_and_image

                ## Packing.
                process.packing(gen_instance, theme_name, comment)


        def convert_XP(self, fileXP):
                """ Extracts data from theme file `.CurXPTheme`, then creates `.ani`s or `X11`s. """
                ## Open and read XP theme file.
                try:
                        archive = ZipFile(fileXP, 'r')
                        scheme = archive.read('Scheme.ini')
                        scheme = scheme.decode('ascii').replace(';', '\r\n').split('\r\n')
                        ## Fix for multi return carriage.
                        scheme = [line for line in scheme if line != '']
                except:
                        self.logger.error('Error: file {} missing "Scheme.ini" --> conversion aborted\n'.format(fileXP))
                        return

                ## Get description content.
                try:
                        comment = scheme[scheme.index('[Description]') + 1 ::]
                        comment = [line.strip() for line in comment if line.strip() != '']
                        comment = " - ".join(comment)
                except ValueError:
                        comment = 'missing'

                ## Get theme name from file name.
                theme_name = os.path.splitext(os.path.basename(fileXP))[0]
                theme_name = theme_name.replace(',', '_').replace(' ', '')
                self.logger.info('Theme info:\n\n\t{}\n\n'.format(comment))

                ## Creation subfolders under `targets` folder.
                process.create_subfolders(theme_name)

                ## Get "Scheme.ini" data indexes.
                indexes = [scheme.index(line) for line in scheme if line.startswith('[') and line != '[General]']

                ## Start processing data.
                for i in range(len(indexes) - 1):
                        if not scheme[indexes[i]].endswith('_Script]'):
                                ## Get data image.
                                image_data = scheme[indexes[i] + 1 : indexes[i + 1]]
                                name = scheme[indexes[i]].replace('_Down', '').replace('[', '').replace(']', '')
                                image_index, = [key for key, value in cursor_namemap.items() if name == value[0]]

                                ## Prevents incorrect ordering.
                                self.parameters = {'index'   : image_index,
                                                   'status'  : 'StdCursor',
                                                   'count'   : 'Frames',
                                                   'interval': 'Interval',
                                                   'anim'    : 'Animation style',
                                                   'hotx1'   : 'Hot spot x',
                                                   'hoty1'   : 'Hot spot y',
                                                   'hotx2'   : 'Hot spot x2',
                                                   'hoty2'   : 'Hot spot y2',
                                                   'script'  : 'FrameScript'
                                                   }

                                for line in image_data:
                                        identifier, assign = line.split('=')
                                        for key, value in self.parameters.items():
                                                if value == identifier:
                                                        self.parameters[key] = int(assign)

                                ## Impose some parameters if missing.
                                for key in ['status', 'anim', 'script']:
                                        if not isinstance(self.parameters[key], int):
                                                self.parameters[key] = 0

                                ## Some preliminar parameters checks.
                                if (self.parameters['count'] in [0, 'Frames']) or \
                                   (self.parameters['interval'] in [0, 'Interval']) or \
                                   any(isinstance(self.parameters[key], str) for key in ['hotx1', 'hoty1', 'hotx2', 'hoty2']):
                                        self.logger.error('Error: "Scheme.ini" corrupted --> cursor #{:d} skipped\n'.format(self.parameters['index']))
                                        continue
                                else:
                                        ## Normalize variables like `.cursorFX` style.
                                        # Status.
                                        # for CursorXP --> CURSOR_STATUS_NORMAL = 0, CURSOR_STATUS_ERROR = 1
                                        self.parameters['status'] = 1 - self.parameters['status']
                                        if scheme[indexes[i]].endswith('_Down]'):
                                                self.parameters['status'] = 2
                                        # Animation.
                                        # for CursorXP --> ANIMATION_TYPE_NONE = 0, ANIMATION_TYPE_LOOP = 1, ANIMATION_TYPE_ALTERNATE = 2
                                        self.parameters['anim'] = (self.parameters['anim'] + 1 if self.parameters['anim'] else self.parameters['anim'])
                                        ## Fix for different hotspot couples.
                                        if (self.parameters['hotx1'] != self.parameters['hotx2']) or (self.parameters['hoty1'] != self.parameters['hoty2']):
                                                self.parameters['hotx'] = min(self.parameters['hotx1'], self.parameters['hotx2'])
                                                self.parameters['hoty'] = min(self.parameters['hoty1'], self.parameters['hoty2'])
                                        else:
                                                self.parameters['hotx'] = self.parameters['hotx1']
                                                self.parameters['hoty'] = self.parameters['hoty1']
                                        for key in ['hotx1', 'hotx2', 'hoty1', 'hoty2']:
                                                self.parameters.pop(key, None)

                                self.logger.info('<------>< Image Extraction ><------>\n')
                                self.logger.info(u'Image index #{}:\n\n\tStatus: {}\n\tFrame count: {}\n\tFrame interval: {}\n\t\
Animation type: {}\n\tHotspot position: ({}, {})\n\tScript status: {}\n'
                                                 .format(self.parameters['index'], self.parameters['status'], self.parameters['count'],
                                                         self.parameters['interval'], self.parameters['anim'],
                                                         self.parameters['hotx'], self.parameters['hoty'], self.parameters['script']))

                                ## Get strip image / strip image frames.
                                if self.parameters['status'] in [1, 2]:
                                        try:
                                                image_strip = Image.open(BytesIO(archive.read(name + '.png')))
                                        except:
                                                self.logger.error('Error: strip image missing --> cursor #{:d} skipped\n'.format(self.parameters['index']))
                                                continue
                                elif self.parameters['status'] == 0:
                                        self.logger.error('Error: strip image missing --> cursor #{:d} skipped\n'.format(self.parameters['index']))
                                        continue
                                self.strip_frames(image_strip)

                                ## Create config file (no script).
                                if self.parameters['script'] == 0:
                                        with open(process.config(self.parameters), 'w') as cfg_file:
                                                self.script_missing(cfg_file)
                                        ## Generate.
                                        gen_instance = process.generate(self.parameters, theme_name)

                        else:
                                ## Create config file (with script).
                                if self.parameters['script'] == 1:
                                        with open(process.config(self.parameters), 'w') as cfg_file:
                                                script_data = scheme[indexes[i] + 1 : indexes[i + 1]]
                                                script_data = [re.sub(r'(?:(?<=\,|-)\s*|\s*(?=\,|-))', '', ' '.join(line.replace(';', '').split()))
                                                               for line in script_data]
                                                self.script_exist(cfg_file, script_data)
                                        ## Generate.
                                        gen_instance = process.generate(self.parameters, theme_name)

                ## Packing.
                process.packing(gen_instance, theme_name, comment)


## ___________________________________
##| X11 cursors conversion functions  |---------------------------------------------------------------------------------------------------------------------
##|___________________________________|
##

class X11Cur(object):
        def __init__(self, parameters):
                self.parameters = parameters
                self.logger = logging.getLogger('Metamorphosis')

        def path_output(self):
                """ Defines output file path. """
                try:
                        custom_output = os.path.join(process.outputcurs_dir, self.parameters['custom'])
                        os.makedirs(custom_output, exist_ok = True)
                        return custom_output
                except:
                        return process.outputcurs_dir

        def theme_file(self, theme_name, description):
                """ Creates "index.theme" file. """
                description = re.sub(r'[^\x20-\x7e]', '', description)
                themefile = "[Icon Theme]\n" + \
                            "Name={}\n".format(theme_name) + \
                            "Comment={}\n-{}\n".format(description, label) + \
                            "Example=default\n" + \
                            "Inherits=core"

                with open(os.path.join(process.output_dir, 'index.theme'), 'w') as file:
                        file.write(themefile)
                with open(os.path.join(process.output_dir, 'cursor.theme'), 'w') as file:
                        file.write(themefile)

        def convert(self):
                """ Creates `X11` cursors, using `xcursorgen` or byte-by-byte writer. """
                self.logger.info('\n<------>< `X11` files creation ><------>\n')

                ## Get elements from cursor namemap.
                outfilename, links = cursor_namemap[self.parameters['index']][2 : 4]
                ## Manage pressed cursors.
                ## for CursorFX / CursorXP --> CURSOR_STATUS_NORMAL = 1, CURSOR_STATUS_PRESSED = 2
                if self.parameters['status'] == 2:
                        outfilename += '_pressed'
                        links = []

                ## Try `xcursorgen` job.
                path_cfg = ' "' + process.config(self.parameters) + '"'
                path_outcurs = ' "' + os.path.join(self.path_output(), outfilename) + '"'
                proc = Popen('xcursorgen' + path_cfg + path_outcurs, shell = True, stdout = PIPE, stderr = PIPE)
                out, err = proc.communicate()
                code = proc.wait()

                if code != 0:
                        err = ''.join(out.decode('ascii').splitlines())
                        if err == '':
                                err = '`xcursorgen` not installed or `xcursorgen` process trouble\n'
                        self.logger.error("Error: can't convert cursor #{:d} by `xcursorgen` --> {}".format(self.parameters['index'], err))
                else:
                        ok = True
                        for link in links:
                                while True:
                                        path = os.path.join(self.path_output(), link)
                                        try:
                                                os.symlink(outfilename, path)
                                                break
                                        except FileExistsError:
                                                os.remove(path)
                                        except:
                                                self.logger.error('Error: failed creating symlink: "{}" --> "{}"\n'.format(outfilename, link))
                                                ok = False
                                                break
                        if ok:
                                self.logger.info('X11 cursor "{}" and symlinks ----> Done !!\n'.format(outfilename))

        def pack(self, theme_name, description):
                """ Packages `X11` theme. """
                self.theme_file(theme_name, description)
                ## Create archive.
                path_archive = ' "' + os.path.join(process.options['output'], "{}.tar.gz".format(theme_name)) + '"'
                path_where = ' "{}" "{}"'.format(process.targets_dir, theme_name)

                proc = Popen('tar -a -cf' + path_archive + ' -C' + path_where , shell = True, stdout = PIPE, stderr = PIPE)
                out, err = proc.communicate()
                code = proc.wait()

                if code != 0:
                        err = ''.join(out.decode('ascii').splitlines())
                        if err == '':
                                err = '`tar` not installed or `tar` process trouble\n'
                        self.logger.error('Error: "{}" packaging skipped --> {}'.format(theme_name, err))


## _________________________________
##| MS `.cur` conversion functions  |------------------------------------------------------------------------------------------------------------------------
##|_________________________________|
##

class MSCur(object):
        def __init__(self, parameters):
                self.parameters = parameters
                self.logger = logging.getLogger('Metamorphosis')

        def natural(self, string):
                """ Natural sorting function. """
                return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string)]

        def convert(self):
                """ Executes Iconolatry for `.png`s to `.cur`s conversion. """
                self.logger.info('\n<------>< Microsoft `.cur` files creation ><------>')
                pngs = [[os.path.join(process.original_dir, png)] for png in os.listdir(process.original_dir)
                        if "_" in png and re.search('img(.*)-(.*)_', png).groups() == (str(self.parameters['index']), str(self.parameters['status']))]
                lung = len(pngs)
                self.logger.info('\nConversion to `.cur` of set images index: {}, with status: {}\n'
                                 .format(self.parameters['index'], self.parameters['status']))

                encocur = Iconolatry.Encode(pngs,
                                            paths_icocur = [process.icocur_dir] * lung,
                                            names_icocur = [''] * lung,
                                            formats_icocur = [('.cur', self.parameters['hotx'], self.parameters['hoty'])] * lung)

                keys = sorted(encocur.all_icocur_written.keys(), key = self.natural)
                sorted_encocur = OrderedDict((k, encocur.all_icocur_written[k]) for k in keys)

                first = list(sorted_encocur.values())[0][0]
                self.logger.info('\tMode: {} \n\tDepth: {}\n\tImage size: {}\n\tHotspot position: ({}, {})\n'
                                 .format(first['mode'], first['depth'], first['size'], first['hotspot_x'], first['hotspot_y']))


## _________________________________
##| MS `.ani` conversion functions  |------------------------------------------------------------------------------------------------------------------------
##|_________________________________|
##

class MSAni(object):
        def __init__(self, parameters):
                self.parameters = parameters
                self.logger = logging.getLogger('Metamorphosis')

        def int2byte(self, value, byteorder = 'little', padbytes = 4):
                """ Transforms an integer into his hex representation (little or big endian).
                    Usually padbytes = 1 (8-bit), 2 (16-bit), 4 (32-bit), 8 (64-bit).
                """
                lung = (value.bit_length() + 7) // 8
                ## Add padding, if needs.
                pad = padbytes - lung
                if pad < 0:
                        pad = 0
                ## Create bytes representation.
                return value.to_bytes(lung + pad, byteorder = byteorder) or b'\0'

        def ms2jiffies(self, value):
                """ Converts from ms to jiffies. """
                return int(0.5 * ceil(2.0 * (value / (1000 / 60))))

        def jiffies2ms(self, value):
                """ Converts from jiffies to ms. """
                return int(0.5 * ceil(2.0 * (value * (1000 / 60))))

        def unique(self, sequence):
                """ Finds ordered unique values. """
                seen = set()
                seen_add = seen.add
                return [x for x in sequence if not (x in seen or seen_add(x))]

        def even(self, string):
                """ Makes even a byte string. """
                bytes_string = bytes(string, 'utf-8')
                if len(bytes_string) % 2 != 0:
                        bytes_string += b'*'
                return bytes_string

        def pack(self, theme_name, description):
                """ Packages `.ani` theme. """
                ## Create file `.inf`.
                self.inf_file(theme_name, description)
                ## Do package.
                make_archive(os.path.join(process.options['output'], theme_name), 'zip',
                             root_dir = process.output_dir,
                             base_dir = None)

        def inf_file(self, theme_name, description):
                """ Creates `.inf` file for Windows installation. """
                scheme_reg = ['pointer', 'help', 'work', 'busy', 'cross',
                              'text', 'hand', 'unavailiable', 'vert', 'horz',
                              'dgn1', 'dgn2', 'move', 'alternate', 'link']

                scheme_cur = [value[1] for key, value in cursor_namemap.items() if key in list(range(9)) + list(range(10,17,2)) + list(range(17,19))]
                string_cur = ''
                align = len(max(scheme_reg, key = len))
                for reg, cur in zip(scheme_reg, scheme_cur):
                        string_cur += '{:<{align}} = "{}.ani"\n'.format(reg, cur, align = align)

                scheme_inf = '; "{}" cursors pack installation file\n'.format(theme_name) + \
                             '; {}\n; {}\n'.format(description, label) + \
                             '; Right click on the file "Install.inf" and select "Install". Then in the Mouse control panel apply set cursors.' + '\n\n' + \
                             "[Version]\n" + "signature=""$CHICAGO$""" + '\n\n' + \
                             "[DefaultInstall]\n" + "CopyFiles = Scheme.Cur, Scheme.Txt\n" + \
                                                    "AddReg    = Scheme.Reg" + '\n\n' + \
                             "[DestinationDirs]\n" + 'Scheme.Cur = 10,"%CUR_DIR%"\n' + \
                                                     'Scheme.Txt = 10,"%CUR_DIR%"' + '\n\n'+ \
                             "[Scheme.Reg]\n" + 'HKCU,"Control Panel\\Cursors\\Schemes","%SCHEME_NAME%",,"' + \
                                                ','.join('%10%\\%CUR_DIR%\\%{}%'.format(reg) for reg in scheme_reg) + '\n\n' + \
                             "; --Common Information\n\n" + \
                             "[Scheme.Cur]\n" + '\n'.join('{}.ani'.format(cur) for cur in scheme_cur) + '\n\n' + \
                             "[Scheme.Txt]" + '\n\n' + \
                             "[Strings]\n" + '{:<{align}} = "Cursors\\{}"\n'.format('CUR_DIR', theme_name, align = align) + \
                                             '{:<{align}} = "{}"\n'.format('SCHEME_NAME', theme_name, align = align) + \
                                             '{}'.format(string_cur)

                with open(os.path.join(process.output_dir, 'Install.inf'), 'w') as file:
                        file.write(scheme_inf)

        def find_value(self, data, position):
                """ Gets chunk values. """
                offset, = unpack_from('<H', data[position + 4 : position + 8])
                value = data[position + 8 : position + 8 + offset]

                return value

        def find_chunk(self, data, name_chunk):
                """ Finds chunk. """
                try:
                        pos_chunk = re.search(name_chunk, data).start()
                        chunk = self.find_value(data, pos_chunk)
                except AttributeError:
                        chunk = None

                return chunk

        def find_inam_iart(self, data):
                """ Finds 'INAM' and 'IART' chunks values. """
                inam = self.find_chunk(data, b'INAM')
                iart = self.find_chunk(data, b'IART')
                inam = (inam.decode('utf-8') if inam else '')
                iart = (iart.decode('utf-8') if iart else '')

                return inam, iart

        def find_rate_seq(self, data):
                """ Finds 'rate' and 'seq ' chunks values. """
                rate = self.find_chunk(data, b'rate')
                seq = self.find_chunk(data, b'seq ')
                seq = ([unpack_from('<L', seq[i : i + 4])[0] for i in range(0, len(seq), 4)] if seq else [])
                rate = ([self.jiffies2ms(unpack_from('<L', rate[i : i + 4])[0]) for i in range(0, len(rate), 4)] if rate else [])

                return rate, seq

        def convert(self, resized, theme_name):
                """ Writes `.ani` cursor byte-to-byte. """
                self.logger.info('<------>< Microsoft `.ani` file creation ><------>\n')

                ## Get parameters from config file.
                with open(process.config(self.parameters), 'r') as cfg_file:
                        cfg_data = cfg_file.readlines()
                cfg_data = [line.replace('\n', '') for line in cfg_data]

                ## Define global data for 'anih'.
                anih_size, cb_size = (self.int2byte(36) for _ in range(2))

                stored_as_cur = True
                if stored_as_cur:
                        # these fields contain zeroes if the images are
                        # stored in icon or cursor resources.
                        iwidth, iheight, ibitcount, nplanes = (self.int2byte(0) for _ in range(4))
                else:
                        # these fields contain non-zero values if images are
                        # stored as raw bitmaps.
                        iwidth          = self.int2byte(resized[0])
                        iheight         = self.int2byte(resized[1])
                        ibitcount       = self.int2byte(32)
                        nplanes         = self.int2byte(1)

                ## Define remaining data for 'anih'.
                path_list, rate_list, seq_list = ([] for _ in range(3))
                for line in cfg_data:
                        path, rate = line.split(' ')
                        path_list.append(path)
                        rate_list.append(int(rate))
                        seq = re.search('_(.*).cur', path).group(1)
                        seq_list.append(int(seq))

                nframes = self.int2byte(self.parameters['count'])
                nsteps = len(seq_list)
                steps_unique = self.unique(seq_list)
                idisprate = self.int2byte(self.ms2jiffies(self.parameters['interval']))

                if seq_list == steps_unique:
                        create_chunk_seq = False
                        bfattributes = self.int2byte(1)
                else:
                        create_chunk_seq = True
                        bfattributes = self.int2byte(3)
                        if not all(seq in steps_unique for seq in seq_list):
                                self.logger.warning('Warning: not all frame images are used, this `.ani` could be better optimized')

                create_chunk_rate = (False if all(rate == self.parameters['interval'] for rate in rate_list) else True)

                ## Define data for IART (need even length).
                iart = self.even(label)
                iart_size = self.int2byte(len(iart))

                ## Define name of `.ani` file.
                ani_name = cursor_namemap[self.parameters['index']][1]
                if self.parameters['status'] == 2:
                        ani_name += '_pressed'

                # Define data for INAM (need even length).
                inam = '*' + theme_name + ' (' + ani_name + ')*'
                inam = self.even(inam)
                inam_size = self.int2byte(len(inam))

                ## Define size of all tag 'INFO'.
                ## b'INFO' = 4
                ## b'IART' + iart_size = 4 + 4 = 8
                ## b'INAM' + inam_size = 4 + 4 = 8
                list_size = self.int2byte(4 + len(iart) + 8 + len(inam) + 8)

                ## Start to construct `.ani` header.
                ani_header =  b'RIFF' + b'\x00\x00\x00\x00' + b'ACON' # 'RIFF' - RIFF size - 'ACON'
                ani_header += b'LIST' + list_size                     # 'LIST' - LIST size
                ani_header += b'INFO'                                 # 'INFO'
                ani_header += b'INAM' + inam_size           + inam    # 'INAM  - INAM size - INAM string
                ani_header += b'IART' + iart_size           + iart    # 'IART' - IART size - IART string
                ani_header += b'anih' + anih_size           + cb_size
                ani_header += nframes + self.int2byte(nsteps) + iwidth + iheight
                ani_header += ibitcount + nplanes + idisprate + bfattributes

                ## Continue to construct `.ani` header with tags 'rate' and 'seq '.
                rateseq_size = self.int2byte(nsteps * 4) # 4 byte -> len of DWORD
                if create_chunk_seq:
                        ani_header += b'seq ' + rateseq_size
                        for seq in seq_list:
                                ani_header += self.int2byte(seq)

                if create_chunk_rate:
                        ani_header += b'rate' + rateseq_size
                        for rate in rate_list:
                                ani_header += self.int2byte(self.ms2jiffies(rate))

                ## Continue to construct `.ani` header with tag 'icon'.
                ani_header += b'LIST' + b'\x00\x00\x00\x00' + b'fram' # 'LIST' - LIST size - 'fram'

                ## Do process.
                ani_path = os.path.join(process.outputcurs_dir, ani_name + '.ani')
                with open(ani_path, 'wb+') as ani_file:
                        ## Write `.ani` header.
                        ani_file.write(ani_header)
                        ## Write 'icon' and his size identifier then data, for all `.cur`s.
                        for path in self.unique(path_list):
                                cur_size = self.int2byte(os.path.getsize(path))
                                ani_file.write(b'icon' + cur_size)
                                with open(path, 'rb') as cur_file:
                                        ani_file.write(cur_file.read())

                        ## Fix RIFF size with proper value after writing all `.ani` file.
                        riff_size = ani_file.tell() - 8
                        ani_file.seek(4)
                        ani_file.write(self.int2byte(riff_size))
                        ## Fix LIST size with proper value after writing all `.cur`s.
                        ani_file.seek(0)
                        offset = re.search(b'fram', ani_file.read()).start() - 4
                        list_size = riff_size - (offset - 4)
                        ani_file.seek(offset)
                        ani_file.write(self.int2byte(list_size))

                self.logger.info('{} ----> Done !!\n'.format(ani_path))


## _____________________________________
##| Mixed cursors conversion functions  |--------------------------------------------------------------------------------------------------------------------
##|_____________________________________|
##

class Mixed(object):
        def __init__(self, options):
                self.options = options
                self.logger = logging.getLogger('Metamorphosis')

        def adjust(self, image, name):
                """ Adjusts single image (only resize and recolor) and save. """
                editor = Editor(self.parameters, self.options)
                editor.adjust([image], extended = False, custom = name)

        def work(self, result, result_index, seq_value, rate_value, order):
                """ Works on Iconolatry results. """
                result = result[result_index]

                if isinstance(result, dict):
                        self.logger.info('\tData {}:'.format(result_index if result_index.startswith('stream') else 'stream_0'))
                        for key in result:
                                subresult = result[key]
                                if isinstance(subresult, dict):
                                        if 'warning' in subresult:
                                                for warn in subresult['warning']:
                                                        self.logger.warning(warn)
                                        if 'info' in subresult:
                                                inf = ', '.join('{} = {}'.format(k, v) for k, v in subresult['info'].items())
                                                self.logger.info(inf)

                                        self.parameters['hotx'] = subresult['hotspot_x']
                                        self.parameters['hoty'] = subresult['hotspot_y']
                                        depth = subresult['depth']
                                        image_width, image_height = subresult['im_obj'].size

                                        ## Log specific info.
                                        self.logger.info(u'\t\tImage size: {} x {}\t\tHotspot position: ({}, {})\t\tDepth: {}'
                                                         .format(image_width, image_height, self.parameters['hotx'], self.parameters['hoty'], depth))

                                        ## Do work.
                                        name, extension = os.path.splitext(os.path.basename(subresult['saved']))
                                        entry = (image_width, image_height, depth)
                                        if entry not in order:
                                                # order by size and depth.
                                                order[entry] = (0 if not order else max(order.values()) + 1)

                                        ## Adjust image.
                                        self.adjust(subresult['im_obj'], ''.join([name, extension]))

                                        ## Create config file.
                                        self.parameters['custom'] = ("_{:d}".format(order[entry]) if len(result) > 1 else "")
                                        with open(process.config(self.parameters), 'a') as cfg_file:
                                                parser = Parser(self.parameters, self.options)
                                                parser.cfg_writer(cfg_file, seq_value, rate_value, custom = self.parameters['custom'])
                else:
                        if isinstance(subresult, list):
                                for warn in subresult:
                                        self.logger.warning(warn)
                        else:
                                self.logger.error(subresult)

                return order

        def convert_ani2x11(self, fileMS, theme_name, comments):
                """ Creates `.png`s from `.ani` or `.cur` cursor, then produces `X11` cursor. """
                ## Get cursor index.
                name, extension = os.path.splitext(os.path.basename(fileMS))
                try:
                        image_index, = [key for key, value in cursor_namemap.items() if name == value[1]]
                except:
                        self.logger.error('Error: have not standard Windows cursor name --> cursor {} skipped\n'.format(''.join([name, extension])))
                        return (None, comments)

                ## Creation subfolders under `targets` folder.
                process.create_subfolders(theme_name)

                ## Define parameters.
                self.parameters = {'index'    : image_index,
                                   'status'   : 1                       # impose status always "1" (normal), not exist status pressed for `.ani` and `.cur`.
                                   }

                self.logger.info('<------>< Image Extraction ><------>\n')
                order = {}
                ## Work on `.cur` and `.ani`.
                if extension.lower() == '.cur':
                        self.parameters.update({'count'    : 1,         # always 1 frame.
                                                'interval' : 1000000,   # impose "Inf" for `.cur`.
                                                'anim'     : 0          # impose "NONE" for `.cur`.
                                                })

                        name = 'img{:d}-{:d}_{:d}'.format(self.parameters['index'], self.parameters['status'], 0)

                        ## Conversion `.cur` --> `.png`
                        decocur = Iconolatry.Decode([fileMS],
                                                    paths_image = [process.original_dir],
                                                    names_image = [name],
                                                    formats_image = ['.png'],
                                                    rebuild = True)

                        order = self.work(decocur.all_icocur_readed, fileMS, 0, self.parameters['interval'], order)

                elif extension.lower() == '.ani':
                        ## Read data from file.
                        with open(fileMS, 'rb') as file:
                                data = file.read()

                        ## Find 'anih' parameters.
                        msani = MSAni(None)
                        pos_anih = re.search(b'anih', data).start()

                        (nframes, nsteps, iwidth, iheight,
                         ibitcount, nplanes, idisprate, bfattributes) = unpack_from('<8L', data[pos_anih + 12 : pos_anih + 44])
                        idisprate = msani.jiffies2ms(idisprate)

                        inam, iart = msani.find_inam_iart(data)
                        if inam or iart:
                                comment = inam + iart + ';'
                                ## Get `.ani` complete comment.
                                if comment not in comments:
                                        comments.append(comment)

                        rate, seq = msani.find_rate_seq(data)

                        self.parameters.update({'count'    : nframes,
                                                'interval' : idisprate,
                                                'anim'     : 2                  # impose "LOOP" for `.ani`.
                                                })

                        ## Find 'icon' data.
                        pos_cur = [cur.start() for cur in re.finditer(b'icon', data)]
                        ## Get images.
                        streams, names = ([] for _ in range(2))
                        for indx in range(self.parameters['count']):
                                names.append('img{:d}-{:d}_{:d}'.format(self.parameters['index'],
                                                                        self.parameters['status'],
                                                                        (seq[indx] if seq else indx)))
                                try:
                                        streams.append(data[pos_cur[indx] + 8 : pos_cur[indx + 1]])
                                except:
                                        ## Get last image.
                                        # Any of the blocks ("ACON", "anih", "rate", or "seq ")
                                        # can appear in any order (so appended at last),
                                        # so can contain not wanted data.
                                        last = data[pos_cur[indx] + 8 : len(data)]
                                        for find in [b'ACON', b'anih', b'rate', b'seq ']:
                                                if re.search(find, last):
                                                        pos = re.search(find, last).start()
                                                        last = data[pos_cur[indx] + 8 : len(data) - len(last) + pos]
                                        streams.append(last)

                        ## Conversion `.cur` --> `.png`
                        decocur = Iconolatry.Decode(streams,
                                                    paths_image = [process.original_dir] * self.parameters['count'],
                                                    names_image = names,
                                                    formats_image = ['.png'] * self.parameters['count'],
                                                    rebuild = True)

                        ## Log general info.
                        self.logger.info(u'Image index #{}:\n\n\tStatus: {}\n\tFrame count: {}\n\tFrame steps: {}\n\tFrame interval: {}\n\t\
Animation type: {}\n\tSequence chunk: {}\n\tRate chunk: {}\n\t'
                                         .format(self.parameters['index'], self.parameters['status'], self.parameters['count'], nsteps,
                                                 self.parameters['interval'], self.parameters['anim'], seq, rate))

                        self.parameters['count'] = 1  # impose for resizing images one-by-one.
                        for indx, stream in enumerate(decocur.all_icocur_readed):
                                order = self.work(decocur.all_icocur_readed, stream,
                                                  (seq[indx] if seq else indx),
                                                  (rate[indx] if rate else self.parameters['interval']),
                                                  order)

                        self.parameters['count'] = nframes # re-assign for further processing.

                ## Generate (`X11` cursor from `.png`s).
                ord_val = order.values()
                if len(ord_val) > 1:
                        for num in ord_val:
                                self.parameters['custom'] = "{:d}_{:d}".format(self.parameters['index'], num)
                                self.logger.info('\nMulti-size / Multi-depth set: {}:'.format(self.parameters['custom']))
                                gen_instance = process.generate(self.parameters, theme_name)
                else:
                        self.parameters['custom'] = ""
                        gen_instance = process.generate(self.parameters, theme_name)

                return gen_instance, comments

        def convert_x112ani(self, fileX11, theme_name, comments):
                """ Gets `.png`s from `X11` cursor, then produces `.ani` cursor
                    (intermediate step is `.cur` creation).
                """
                ## https://www.x.org/releases/X11R7.7/doc/man/man3/Xcursor.3.xhtml

                ## Get cursor index.
                name, _ = os.path.splitext(os.path.basename(fileX11))
                try:
                        image_index, = [key for key, value in cursor_namemap.items() if name == value[2] or name in value[3]]
                except:
                        self.logger.error('Error: have not standard Linux cursor name --> cursor {} skipped\n'.format(name))
                        return (None, comments)

                ## Creation subfolders under `targets` folder.
                process.create_subfolders(theme_name)

                ## Read data from file.
                with open(fileX11, 'rb') as file:
                        data = file.read()

                ## Define parameters.
                self.parameters = {'index'    : image_index,
                                   'status'   : 1               # impose status always "1" (normal), not exist status pressed for `X11`.
                                   }
                self.logger.info('<------>< Image Extraction ><------>\n')

                ## Get positions.
                ## magic [0:4]/ header_size [4:8] / version [8:12] / ntocs [12:16].
                vers, ntocs = unpack_from('<2L', data[8 : 16])

                ## list_of_tocs -->    type     |               subtype                     |        position          |
                ##                  0xfffe0001  | { 1 (COPYRIGHT), 2 (LICENSE), 3 (OTHER) } |  absolute byte position  |
                ##                  0xfffd0002  |           nominal dimension               |     of table in file     |
                pos_images, pos_comments = ([] for _ in range(2))
                for num in range(ntocs):
                        offset = num * 12
                        identify = data[16 + offset : 20 + offset]
                        get, = unpack_from('<L', data[24 + offset : 28 + offset])

                        if identify == b'\x02\x00\xfd\xff':
                                pos_images.append(get)
                        elif identify == b'\x01\x00\xfe\xff':
                                pos_comments.append(get)

                ## chunks --> common header fields:
                ## header (bytes) |    type    |              subtype                      | version |
                ##       20       | 0xfffe0001 | { 1 (COPYRIGHT), 2 (LICENSE), 3 (OTHER) } |    1    |
                ##       36       | 0xfffd0002 |         nominal dimension                 |    1    |

                ## chunks --> additional type-specific fields:
                ##
                ##                    |           length          |       string           |
                ## comment(0xfffe0001)|  byte length UTF-8 string | byte list UTF-8 string |
                ##
                ##                    |    width    |    height   |     xhot   |   yhot     | delay  | pixels |
                ## image  (0xfffd0002)|   4bytes    |    4bytes   |    4bytes  |  4bytes    | 4bytes | 8bytes |
                ##                    | (max 0x7fff)| (max 0x7fff)| (max width)|(max height)| (ms)   | (ARGB) |

                ## Get comments.
                comment = ""
                subtypes = {1 : 'COPYRIGHT: ',
                            2 : 'LICENSE: ',
                            3 : 'OTHER: '}
                for pos in pos_comments:
                        identify = data[pos + 4 : pos + 8]
                        if identify == b'\x01\x00\xfe\xff':
                                subtype, = unpack_from('<L', data[pos + 8 : pos + 12])
                                if subtype in subtypes.keys():
                                        lung, = unpack_from('<L', data[pos + 16 : pos + 20])
                                        comment += subtypes[subtype] + str(data[pos + 20 : pos + 20 + lung], 'utf-8') + ';'

                ## Get total comment.
                if comment not in comments:
                        comments.append(comment)

                ## Get images.
                msani = MSAni(None)
                self.parameters.update({'count' : len(pos_images),
                                        'anim'  : (0 if len(pos_images) == 1 else 2)
                                        })
                ## Log general info.
                self.logger.info(u'Image index #{}:\n\n\tStatus: {}\n\tFrame count: {}\n\tAnimation type: {}\n\n'
                                 .format(self.parameters['index'], self.parameters['status'], self.parameters['count'], self.parameters['anim']))

                self.parameters['count'] = 1 # impose for resizing images one-by-one.

                for i, pos in enumerate(pos_images):
                        identify = data[pos + 4 : pos + 8]
                        if identify == b'\x02\x00\xfd\xff':
                                image_width, image_height, mouse_x, mouse_y, frame_interval_ms = unpack_from('<5L', data[pos + 16 : pos + 36])
                                frame_interval = msani.ms2jiffies(frame_interval_ms)

                                self.parameters.update({'hotx'     : mouse_x,
                                                        'hoty'     : mouse_y,
                                                        'interval' : frame_interval
                                                        })

                        try:
                                image = Image.frombytes('RGBA', (image_width, image_height), data[pos + 36 : pos_images[i + 1]], 'raw', 'BGRA', 0, 1)
                        except:
                                # get last.
                                image = Image.frombytes('RGBA', (image_width, image_height), data[pos + 36 : len(data)], 'raw', 'BGRA', 0, 1)

                        ## Log specific info.
                        self.logger.info(u'\tData {}:\n\t\tFrame Interval: {}\t\t Image size: {} x {}\t\tHotspot position: ({}, {})'
                                         .format('stream_{:d}'.format(i), frame_interval_ms, image_width, image_height,
                                                 self.parameters['hotx'], self.parameters['hoty']))

                        ## Adjust image.
                        self.adjust(image, "img{:d}-{:d}_{:d}.png".format(self.parameters['index'], self.parameters['status'], i))

                self.parameters['count'] = len(pos_images) # re-assign for further processing.

                ## Use default animation.
                with open(process.config(self.parameters), 'w') as cfg_file:
                        parser = Parser(self.parameters, self.options)
                        parser.animation(cfg_file)

                ## Generate.
                gen_instance = process.generate(self.parameters, theme_name)

                return gen_instance, comments


## ____________________
##| Process functions  |-------------------------------------------------------------------------------------------------------------------------------------
##|____________________|
##

class Process(object):
        def __init__(self, options):
                self.options = options

        def find_magic(self, path):
                """ Checks if a file is `.ani`, `.cur` or `X11` cursor. """
                is_cur, is_ani, is_x11 = (False for _ in range(3))
                with open(path, 'rb') as file:
                        data = file.read()[0:12]

                if data[0:4] == b'\x00\x00\x02\x00':
                        is_cur = True
                elif (data[0:4] == b'RIFF') and (data[8:12] == b'ACON'):
                        is_ani = True
                elif data[0:4] == b'Xcur':
                        is_x11 = True

                return (is_cur, is_ani, is_x11)

        def remove_readonly(self, func, path, excinfo):
                """ Removes read-only permission. """
                os.chmod(path, S_IWRITE)
                func(path)

        def clean(self, redo = True):
                """ Deletes job temp folders."""
                if not ((self.is_folder_anicur is True) or (self.is_folder_x11 is True)):
                        try:
                                rmtree(self.temp_dir, onerror = self.remove_readonly)
                        except OSError:
                                pass
                        if redo:
                                os.makedirs(self.temp_dir, exist_ok = True)

        def handle_time(self, time, done = 0):
                """ Formats process time. """
                minutes, seconds = divmod(time, 60)
                hours, minutes = divmod(minutes, 60)
                if not done:
                        print('{} Process{}#{:d}:{}complete in {:d}:{:02d}:{:02d}'.format(self.larrw, self.blank, self.nproc, self.blank,
                                                                                            hours, minutes, seconds))
                else:
                        print('{} Process{}#{:d}:{}complete in {:d}:{:02d}:{:02d}. Converted {:d}/{:d}.'.format(self.larrw, self.blank,
                                                                                                                self.nproc - 1, self.blank,
                                                                                                                hours, minutes, seconds,
                                                                                                                done, self.nsubproc))
        def handle_header(self, num):
                """ Prints process number. """
                dict_header = {'0' : ' ██████╗\n██╔═████╗\n██║██╔██║\n████╔╝██║\n╚██████╔╝\n ╚═════╝',
                               '1' : ' ██╗\n███║\n╚██║\n ██║\n ██║\n ╚═╝',
                               '2' : '██████╗\n╚════██╗\n █████╔╝\n██╔═══╝\n███████╗\n╚══════╝',
                               '3' : '██████╗\n╚════██╗\n █████╔╝\n ╚═══██╗\n██████╔╝\n╚═════╝',
                               '4' : '██╗  ██╗\n██║  ██║\n███████║\n╚════██║\n     ██║\n     ╚═╝',
                               '5' : '███████╗\n██╔════╝\n███████╗\n╚════██║\n███████║\n╚══════╝',
                               '6' : ' ██████╗\n██╔════╝\n███████╗\n██╔═══██╗\n╚██████╔╝\n ╚═════╝',
                               '7' : '███████╗\n╚════██║\n    ██╔╝\n   ██╔╝\n   ██║\n   ╚═╝',
                               '8' : ' █████╗\n██╔══██╗\n╚█████╔╝\n██╔══██╗\n╚█████╔╝\n ╚════╝',
                               '9' : ' █████╗\n██╔══██╗\n╚██████║\n ╚═══██║\n █████╔╝\n ╚════╝',
                               '.' : '\n\n\n\n██╗\n╚═╝'}
                digits = list(str(num))
                lung = len(digits)
                asciiart_num = []
                if lung > 1:
                        allchunks = [dict_header[digit].split('\n') for digit in digits]

                        for items in zip(*allchunks):
                                obj = ''
                                for item in items:
                                        if len(item) != 0 and 4 <= len(item) < 8:
                                                obj += item + '\t\t'
                                        else:
                                                obj += item + '\t'
                                asciiart_num.append(obj)
                        asciiart_num = '\n'.join(asciiart_num)
                else:
                        asciiart_num = dict_header[str(num)]
                asciiart_num = '\n' + asciiart_num + '\n' + '#' * 50 + '\n\n'

                return asciiart_num

        def handle_folders(self, file, platform):
                """ Creates messages on input folders processing. """
                if self.folder_name != self.old_folder_name:
                        self.nsubproc = 0
                        print('{} Start Processing #{:d}:{}`{}` folder'.format(self.larrw, self.nproc, self.blank, self.folder_name))
                        self.old_folder_name = self.folder_name
                        self.nsubproc += 1
                        print('{} Start Processing #{:d}.{:d}:{}`{}`'.format(self.larrw, self.nproc, self.nsubproc, self.blank, file))
                        self.nproc += 1
                else:
                        self.nsubproc += 1
                        print('{} Start Processing #{:d}.{:d}:{}`{}`'.format(self.larrw, self.nproc - 1, self.nsubproc, self.blank, file))

        def create_folders(self):
                """ Creates job temp folders. """
                self.original_dir   = os.path.join(self.temp_dir, 'originals')
                self.cfg_dir        = os.path.join(self.temp_dir, 'cfgs')
                self.icocur_dir     = os.path.join(self.temp_dir, 'icocurs')
                for path in [self.original_dir, self.cfg_dir, self.icocur_dir]:
                        os.makedirs(path, exist_ok = True)

        def create_subfolders(self, theme_name):
                """ Creates output folders. """
                if self.options['pack']:
                        self.targets_dir    = os.path.join(self.temp_dir, 'targets')
                        self.output_dir     = os.path.join(self.targets_dir, theme_name)
                        os.makedirs(self.targets_dir, exist_ok = True)
                else:
                        self.output_dir = os.path.join(self.options['output'], theme_name)

                self.outputcurs_dir = os.path.join(self.output_dir, 'cursors')
                for path in [self.output_dir, self.outputcurs_dir]:
                        os.makedirs(path, exist_ok = True)

        def create_log(self):
                """ Creates logging file. """
                logname = os.path.join(self.options['output'], 'Metamorphosis.log')

                if os.path.exists(logname):
                        os.remove(logname)
                self.logger = logging.getLogger('Metamorphosis')
                formatter = logging.Formatter('%(message)s')
                filehandler = logging.FileHandler(logname, mode = 'a')
                filehandler.setFormatter(formatter)
                self.logger.setLevel(logging.INFO)
                self.logger.addHandler(filehandler)

        def abort_proc(self, to_process, msg, add = ''):
                """ Aborts processing (file/s). """
                print('{} Start Processing #{:d}:{}`{}` {}'.format(self.larrw, self.nproc, self.blank, to_process, add))
                print('{} Process{}#{:d}:{}aborted, {}.'.format(self.larrw, self.blank, self.nproc, self.blank, msg))
                self.nproc += 1

        def abort_subproc(self, file, msg):
                """ Aborts subprocessing (file/s folder/s). """
                self.handle_folders(file, self.options['platform'])
                print('{} Process{}#{:d}.{:d}:{}aborted, {}.'.format(self.larrw, self.blank, self.nproc - 1, self.nsubproc, self.blank, msg))

        def finish(self, file):
                """ Ends processing current input. """
                print('{} Finished Input      #{:d}:{}`{}`'.format(self.sarrw, self.nfold, self.blank, file))
                self.nfold += 1

        def generate(self, parameters, theme_name):
                """ Generates `X11` / `.ani` cursor from current image. """
                if self.options['platform'] == 'Linux':
                        ## Generate `X11` (Linux).
                        gen_instance = X11Cur(parameters)
                        gen_instance.convert()
                elif self.options['platform'] == 'Windows':
                        ## Generate `.ani` (Windows).
                        MSCur(parameters).convert()
                        gen_instance = MSAni(parameters)
                        gen_instance.convert(self.options['size'], theme_name)

                return gen_instance

        def packing(self, instance, theme_name, comment):
                """ Creates cursor pack archive. """
                if self.options['pack']:
                        if self.options['platform'] in ['Linux', 'Windows']:
                                instance.pack(theme_name, comment)
                else:
                        if self.options['platform'] == 'Linux':
                                instance.theme_file(theme_name, comment)
                        elif self.options['platform'] == 'Windows':
                                instance.inf_file(theme_name, comment)

        def config(self, parameters):
                """ Defines configuration file path. """
                try:
                        if len(parameters['custom']) == 3:
                                custom = parameters['custom'][1:]
                        elif len(parameters['custom']) == 2:
                                custom = parameters['custom']
                        elif len(parameters['custom']) == 0:
                                custom = "_0"

                        name_cfg = "img{:d}-{:d}{}.cfg".format(parameters['index'], parameters['status'], custom)
                except:
                        name_cfg = "img{:d}-{:d}.cfg".format(parameters['index'], parameters['status'])

                return os.path.join(process.cfg_dir, name_cfg)

        def work_setup(self, file):
                """ Setups global processing operations. """
                self.clean(redo = True)
                self.create_folders()

                return (True if file.lower().endswith(('.cursorfx', '.curxptheme')) else False)

        def work_stardock(self, path, file):
                """ Runs Stardock files processing. """
                self.is_folder_anicur, self.is_folder_x11 = (False, False)
                print('{} Start Processing #{:d}:{}`{}`'.format(self.larrw, self.nproc, self.blank, file))
                self.logger.info(self.handle_header(self.nproc))

                stardock = Stardock(self.options)

                if file.lower().endswith('.cursorfx'):
                        stardock.convert_FX(path)
                elif file.lower().endswith('.curxptheme'):
                        stardock.convert_XP(path)

        def work_anix11_setup(self, file, is_unpaired = True):
                """ Setups `.ani`, `.cur` or `X11` unpaired / folder(s) file(s) processing operations. """
                is_continue = False
                is_cur, is_ani, is_x11 = self.find_magic(file)
                ## First check: extension ok.
                if (file.lower().endswith('.cur') and is_cur) or (file.lower().endswith('.ani') and is_ani):
                        self.is_folder_anicur, self.is_folder_x11 = (True, False)
                elif is_x11:
                        self.is_folder_anicur, self.is_folder_x11 = (False, True)
                else:
                        self.is_folder_anicur, self.is_folder_x11 = ('?', '?')
                        msg = 'not a cursor file'
                        if is_unpaired:
                                self.abort_proc(file, msg)
                                self.finish(file)
                        else:
                                self.abort_subproc(file, msg)
                        is_continue = True

                ## Second check:
                ## Abort conversion `.ani`/`.cur` to `.ani`/`.cur` OR conversion `X11` to `X11`.
                if not is_continue:
                        if (self.options['platform'] == 'Windows' and self.is_folder_anicur) \
                           or (self.options['platform'] == 'Linux' and self.is_folder_x11 ):
                                self.is_folder_anicur, self.is_folder_x11 = ('?', '?')
                                msg = 'conversion not needed'
                                if is_unpaired:
                                        self.abort_proc(file, msg)
                                        self.finish(file)
                                else:
                                        self.abort_subproc(file, msg)
                                is_continue = True

                return is_continue

        def work_anix11(self, file, theme_name, comments):
                """ Runs `.ani`, `.cur` or `X11` unpaired / folder(s) file(s) processing. """
                mixed = Mixed(self.options)
                if self.options['platform'] == 'Linux':
                        gen_instance, comments = mixed.convert_ani2x11(file, theme_name, comments)
                elif self.options['platform'] == 'Windows':
                        gen_instance, comments = mixed.convert_x112ani(file, theme_name, comments)

                return gen_instance, comments

        def main(self):
                """ Main process. """
                ## Define conversion job temp path.
                self.temp_dir = os.path.join(gettempdir(), 'Metamorphosis')
                ## Define converted stuff output path.
                self.options['output'] = os.path.abspath(os.path.expanduser(self.options['output']))
                if self.options['output'].startswith('\\'):
                        self.options['output'] = 'C:' + self.options['output']
                os.makedirs(self.options['output'], exist_ok = True)

                ## Create initial variables for process.
                self.folder_name, self.old_folder_name = ('' for _ in range(2))
                self.nproc, self.nfold = (0 for _ in range(2))
                self.is_folder_anicur, self.is_folder_x11 = ('?' for _ in range(2))
                subtimes, unique, comments = ([] for _ in range(3))
                self.blank = '\t\t '
                self.larrw, self.sarrw = ('-' * 6 + '>', '-' * 3 + '>')

                ## Create log file.
                self.create_log()
                ## Do conversion.
                print('\nMetamorphosis working...')
                for file_dir in self.options['input']:
                        print('\n{} Processing Input    #{:d}:{}`{}`'.format(self.sarrw, self.nfold, self.blank, file_dir))
                        if not os.path.exists(file_dir):
                                print('{} Input{}#{:d}:{}aborted, {}.'.format(self.sarrw, self.blank, self.nfold, self.blank, 'not exist'))
                                self.finish(file_dir)
                                continue

                        if os.path.isfile(file_dir):
                                #######################
                                # is an unpaired file #
                                #######################
                                tic = perf_counter()
                                self.nproc = self.nfold

                                is_stardock = self.work_setup(file_dir)

                                ## Check duplicate files.
                                filehash = md5(open(file_dir, 'rb').read()).hexdigest()
                                if filehash not in unique:
                                        unique.append(filehash)
                                else:
                                        self.abort_proc(file_dir, 'duplicate file found')
                                        self.finish(file_dir)
                                        continue

                                if is_stardock:
                                        self.work_stardock(file_dir, file_dir)
                                else:
                                        is_continue = self.work_anix11_setup(file_dir)
                                        if is_continue:
                                                continue

                                        self.logger.info(self.handle_header(self.nproc))

                                        self.work_anix11(file_dir, 'Input_' + str(self.nfold), comments)

                                ## Get total process time elapsed (`stardock` or `.ani` or `X11` files).
                                # Note: `.ani` or `X11` unpaired: no need to pack and create installation files.
                                toc = perf_counter()
                                self.handle_time(ceil(toc - tic))

                        else:
                                #####################
                                # is a files folder #
                                #####################
                                for dirpath, dirnames, filenames in os.walk(file_dir):
                                        dirpath = os.path.normpath(dirpath)
                                        numsep = dirpath[len(file_dir):].count(os.path.sep)

                                        if not filenames and not dirnames:
                                                self.abort_proc(os.path.basename(dirpath), "empty folder", add = 'folder')
                                                continue

                                        if numsep < 2:
                                                for filename in filenames:
                                                        tic = perf_counter()
                                                        pathfile = os.path.join(dirpath, filename)
                                                        self.folder_name = os.path.basename(dirpath)

                                                        is_stardock = self.work_setup(filename)

                                                        ## Check duplicate files.
                                                        filehash = md5(open(pathfile, 'rb').read()).hexdigest()
                                                        if filehash not in unique:
                                                                unique.append(filehash)
                                                        else:
                                                                msg = 'duplicate file found'
                                                                if is_stardock:
                                                                        self.abort_proc(filename, msg)
                                                                else:
                                                                        self.abort_subproc(filename, msg)
                                                                continue

                                                        if is_stardock:
                                                                if numsep == 0:
                                                                        self.work_stardock(pathfile, filename)
                                                                        ## Get total process time elapsed - (`stardock` files).
                                                                        toc = perf_counter()
                                                                        self.handle_time(ceil(toc - tic))
                                                                        self.nproc += 1
                                                                elif numsep == 1:
                                                                        self.is_folder_anicur, self.is_folder_x11 = ('?', '?')
                                                                        self.abort_proc(self.folder_name,
                                                                                        'take out the stardock cursor(s) from the folder',
                                                                                        add = 'folder')
                                                                        continue
                                                        else:
                                                                if numsep == 0:
                                                                        self.is_folder_anicur, self.is_folder_x11 = ('?', '?')
                                                                        self.abort_proc(self.folder_name,
                                                                                        'insert `.ani`, `.cur` or `X11` cursor(s) in a folder',
                                                                                        add = 'folder')
                                                                        continue
                                                                elif numsep == 1:
                                                                        is_continue = self.work_anix11_setup(pathfile, is_unpaired = False)
                                                                        if is_continue:
                                                                                continue

                                                                        self.handle_folders(filename, self.options['platform'])
                                                                        self.logger.info(self.handle_header('{:d}.{:d}'.format(self.nproc - 1, self.nsubproc)))

                                                                        gen_instance, comments = self.work_anix11(pathfile, self.folder_name, comments)

                                                                        ## Get partial subprocess time elapsed - (`.ani`, `.cur` or `X11` folders).
                                                                        toc = perf_counter()
                                                                        subtimes.append(ceil(toc - tic))

                                                ## Get total process time elapsed / and eventually packing - (`.ani`, `.cur` or `X11` folders).
                                                if (self.is_folder_anicur is True) or (self.is_folder_x11 is True):
                                                        if subtimes:
                                                                self.handle_time(sum(subtimes), len(subtimes))
                                                                if gen_instance:
                                                                        self.packing(gen_instance, self.folder_name, '\n'.join(comments))
                                                        else:
                                                                print('{} Process{}#{:d}:{}complete. Converted {:d}/{:d}.'.format(self.larrw, self.blank,
                                                                                                                                  self.nproc - 1, self.blank,
                                                                                                                                  0, self.nsubproc))
                                                ## Reset for next step - (`.ani`, `.cur` or `X11` folders).
                                                subtimes, comments = ([] for _ in range(2))
                                        else:
                                                nested = str(os.path.sep).join(dirpath.split(os.path.sep)[-numsep:])
                                                self.abort_proc(nested, 'too much nested folder', add = 'folder')
                        ## Increment.
                        self.finish(file_dir)
                ## Complete.
                self.clean(redo = False)
                print("\nMetamorphosis finished.")


if __name__ == "__main__":
        options = metamorphosis_parser()
        process = Process(options)
        process.main()
