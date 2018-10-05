
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import Iconolatry
import numpy
import os
import re
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
from binascii import hexlify, unhexlify
from itertools import chain, groupby
from shutil import make_archive
from functools import wraps

__name__        = "Metamorphosis"
__version__     = "III (Chrysalis)"
__license__     = "GPL-3.0 License"
__author__      = u"Matteo ℱan <SystemRage@protonmail.com>"
__copyright__   = "© Copyright 2018"
__url__         = "https://github.com/SystemRage/Metamorphosis"
__summary__     = "The Ultimate Cursor Converter"


## _________________________________________
##| Support to "repeat"/"end repeat" loops  |--------------------------------------------------------------------------------------------------------------
##|_________________________________________|
##
class Repeat(object):
        
        def loop_limit( script ):
                """ Defines all start index of loops ('repeat N'),
                    all stop index ('end repeat') and all number of repetitions ('N'). """
                ini, fin, rip = ([] for _ in range(3))
                for i, v in enumerate(script):
                        if v.startswith('repeat'):
                                ini.append(i)
                                a, b = re.split('\s', v)
                                rip.append(int(b))
                        elif v.startswith('end'):
                                fin.append(i)
                return ini, rip, fin
        

        def loop_flatten( thelist ):
                """ Transforms a list of lists in a flat list. """
                for elem in thelist:
                        if hasattr(elem, '__iter__') and not isinstance(elem, (str, bytes)):
                                yield from Repeat.loop_flatten(elem)
                        else:
                                yield elem


        def loop_expand( script ):
                """ Expands not nested or nested loops or any combination of both. """
                start, nloop, stop = Repeat.loop_limit( script )
                
                while start != []:
                        ## Calculate distances between first stop index with all start indexes.
                        dist = [stop[0] - start[i] for i in range(len(start))]
                        ## Find index of distances where there's min positive distance.
                        min_dist = min(i for i in dist if i > 0)
                        index_min_dist = dist.index(min_dist)
                        ## Create loop extension and calculate the number of elements to insert. 
                        piece = script[ start[index_min_dist] + 1 : stop[0] ] * nloop[index_min_dist]
                        n_adj = (stop[0] - (start[index_min_dist] + 1)) * nloop[index_min_dist]
                        ## Remove in the script the loop in exam and calculate the number of elements erased.
                        script[ start[index_min_dist] : stop[0] + 1 ] = []
                        n_remov = stop[0] + 1 - start[index_min_dist]
                        ## Insert loop extension at right place and flatten.
                        script.insert(start[index_min_dist], piece)
                        script = list(Repeat.loop_flatten( script ))
 
                        shift = n_adj - n_remov
                        ## Shift all start indexes after the used one.
                        shifted_start = [ x + shift for x in start[index_min_dist + 1::] ]
                        start = start[0 : index_min_dist + 1] + shifted_start
                        ## Shift all stop indexes after the first.
                        shifted_stop = [ x + shift for x in stop[1::] ]
                        stop = stop[0 : 1] + shifted_stop
                        ## Update lists removing used elements.
                        start.pop(index_min_dist)
                        stop.pop(0)
                        nloop.pop(index_min_dist)

                return script
        

## ___________________________
##| Various support functions |-----------------------------------------------------------------------------------------------------------------------------
##|___________________________|
##        
class Auxiliary(object):
        
        def namecurs( ):
                """ Cursor names.
                    the list of output file names are based on http://fedoraproject.org/wiki/Artwork/EchoCursors/NamingSpec.
                    NameCursorFX:((NameCursorXP), (NameCursorWindows), (LinkforLinux), (NamesCursorLinux)) """
                ## To assign : dotbox, dot-box, dot_box, dot_box_mask, draped_box, draped-box, icon, target, zoom-in, zoom-out
                CURSOR_NAMEMAP = {
                                0  : (('Arrow'),        ('Arrow'),      ('00normal_select'),             ('default','arrow',
                                                                                                          'top-left-arrow','top_left_arrow',
                                                                                                          'left_ptr',
                                                                                                          'x-cursor','X_cursor')),               # Cursor shape arrow.
                                1  : (('Help'),         ('Help'),       ('01help_select'),               ('ask','dnd-ask',
                                                                                                          'help','question_arrow','whats_this',
                                                                                                          '5c6cd98b3f3ebcb1f9c7f1c204630408',
                                                                                                          'left_ptr_help',
                                                                                                          'd9ce0ab605698f320427677b458ad60b')),  # Cursor guide (arrow with ?).
                                2  : (('AppStarting'),  ('AppStarting'),('02working_in_background'),     ('progress','left_ptr_watch',
                                                                                                          '08e8e1c95fe2fc01f976f1e063a24ccd',
                                                                                                          '3ecb610c1bf2410f44200f48c40d3599')),  # Cursor applications start. 
                                3  : (('Wait'),         ('Wait'),       ('03busy'),                      ('wait','watch',
                                                                                                          '0426c94ea35c87780ff01dc239897213')),  # Cursor wait.
                                4  : (('Cross'),        ('Crosshair'),  ('04precision_select'),          ('crosshair','cross',
                                                                                                          'diamond_cross',
                                                                                                          'cross_reverse','tcross')),            # Cursor precision selection. 
                                5  : (('IBeam'),        ('IBeam'),      ('05text_select'),               ('text','xterm',
                                                                                                          'ibeam','vertical-text')),             # Cursor text.
                                6  : (('Handwriting'),  ('NWPen'),      ('06handwriting'),               ('pencil',)),                           # Cursor shape pen. 
                                7  : (('NO'),           ('No'),         ('07unavailable'),               ('no-drop','dnd-none','circle',
                                                                                                          '03b6e0fcb3499374a867c041f52298f0',
                                                                                                          'not-allowed','crossed_circle',
                                                                                                          'forbidden','pirate')),                # Cursor area not allowed. 
                                8  : (('SizeNS'),       ('SizeNS'),     ('08north_resize'),              ('col-resize','sb_v_double_arrow',
                                                                                                          'split_v','14fef782d02440884392942c11205230',
                                                                                                          'n-resize','top_side','ns-resize','v_double_arrow',
                                                                                                          'size_ver','00008160000006810000408080010102',
                                                                                                          'top-tee','top_tee',
                                                                                                          'double_arrow','double-arrow'
                                                                                                          'up','sb_up_arrow')),                  # Cursor resize two arrows pointing to N and S 
                                9  : (('SizeS'),        ('SizeS'),      ('09south_resize'),              ('bottom-tee','bottom_tee','down',
                                                                                                          'sb_down_arrow','s-resize',
                                                                                                          'bottom_side')),                       # Cursor resize one arrow pointing to N.
                                10 : (('SizeWE'),       ('SizeWE'),     ('10west_resize'),               ('ew-resize','h_double_arrow',
                                                                                                          'size_hor','028006030e0e7ebffc7f7070c0600140',
                                                                                                          'left','sb_left_arrow','left-tee','left_tee',
                                                                                                          'row-resize','sb_h_double_arrow','split_h',
                                                                                                          '2870a09082c103050810ffdffffe0204',
                                                                                                          'w-resize','left_side')),              # Cursor resize two arrows pointing to W and E.
                                11 : (('SizeE'),        ('SizeE'),      ('11east_resize'),               ('e-resize','right_side','right','sb_right_arrow',
                                                                                                          'right-tee','right_tee')),             # Cursor resize one arrow pointing to W.
                                12 : (('SizeNWSE'),     ('SizeNWSE'),   ('12northwest_resize'),          ('nw-resize','top_left_corner','ul_angle',
                                                                                                          'nwse-resize','fd_double_arrow','size_fdiag',
                                                                                                          'c7088f0f3e6c8088236ef8e1e3e70000')),  # Cursor resize two arrows pointing to NW and SE.
                                13 : (('SizeSE'),       ('SizeSE'),     ('13southeast_resize'),          ('se-resize','lr_angle',
                                                                                                          'bottom_right_corner')),               # Cursor resize one arrow pointing to NW.
                                14 : (('SizeNESW'),     ('SizeNESW'),   ('14northeast_resize'),          ('ne-resize','top_right_corner','ur_angle',
                                                                                                          'nesw-resize','bd_double_arrow','size_bdiag',
                                                                                                          'fcf1c3c7cd4491d801f1e1c78f100000')),  # Cursor resize two arrows pointing to NE and SW.
                                15 : (('SizeSW'),       ('SizeSW'),     ('15southwest_resize'),          ('sw-resize','ll_angle',
                                                                                                          'bottom_left_corner')),                # cursor resize one arrow pointing to NE.
                                16 : (('SizeAll'),      ('SizeAll'),    ('16move'),                      ('cell','plus','all-scroll','fleur',
                                                                                                          'size_all')),                          # Cursor resize with four arrows pointing to N/S/W/E.
                                17 : (('UpArrow'),      ('UpArrow'),    ('17alternate_select'),          ('top-right-arrow','right_ptr','move','dnd-move',
                                                                                                          '4498f0e0c1937ffe01fd06f973665830',
                                                                                                          '9081237383d90e509aa00f00170e968f',
                                                                                                          'draft_large','draft_small'
                                                                                                          'up-arrow','up_arrow','center_ptr')),  # Cursor arrow upside for an insertion point.
                                18 : (('Hand'),         ('Hand'),       ('18hand'),                      ('alias','link','dnd-link',
                                                                                                          '3085a0e285430894940527032f8b26df',
                                                                                                          '640fb0e74195791501fd1ed57b41487f',
                                                                                                          '9d800788f1b08800ae810202380a0822',
                                                                                                          'e29285e634086352946a0e7090d73106',
                                                                                                          'a2a266d0498c3104214a47bd64ab0fc8',
                                                                                                          'b66166c04f8c3109214a4fbd64a50fc8',
                                                                                                          'left-hand','hand1','pointer','hand2',
                                                                                                          'grab','grabbing'
                                                                                                          'pointing_hand','openhand','hand')),   # Cursor shape hand.
                                19 : (('Button'),       ('Button'),     ('19button'),                    ('copy','dnd-copy',
                                                                                                          '1081e37283d90000800003c07f3ef6bf',
                                                                                                          '6407b0e94181790501fd1e167b474872'))   # Cursor default with a small plus sign next to it.
                                   }
                
                return CURSOR_NAMEMAP


        def callonce( func ):
                """ To call functions only once. """
                @wraps(func)
                def wrapper( *args, **kwargs ):
                        if not wrapper.called:
                                wrapper.called = True
                                return func(*args, **kwargs)
                wrapper.called = False
                return wrapper

        @callonce
        def initial_clean( ):
                """ Initial directories clean. """
                global TMP_DIR
                try:
                        rmtree(TMP_DIR, onerror = Auxiliary.remove_readonly)
                except OSError:
                        pass
                
        def folder_1lev( ):
                """ Defines general parameters and creates directories. """
                global AUTO_CROP, TMP_DIR, OUTPUT_BASE_DIR, ORIGINAL_DIR, ICOCUR_DIR, CFG_DIR, SCRIPT_LINE_PATTERN
                
                ## Remove transparent border.
                AUTO_CROP = True

                ## Clean at start.    
                Auxiliary.initial_clean( )
                
                ## Create directories.
                OUTPUT_BASE_DIR = os.path.join(TMP_DIR, 'targets')
                ORIGINAL_DIR = os.path.join(TMP_DIR, 'originals')
                CFG_DIR = os.path.join(TMP_DIR, 'cfgs')
                ICOCUR_DIR = os.path.join(TMP_DIR, 'icons')
                
                ## OUTPUT_DIR will be created later, because we need to retrieve the theme_name first.
                ## Create "conversion" directory and subdirectories "targets", "originals", "icons", "cfgs".
                Auxiliary.try_mkdir(TMP_DIR)
                Auxiliary.try_mkdir(OUTPUT_BASE_DIR)
                Auxiliary.try_mkdir(ORIGINAL_DIR)
                Auxiliary.try_mkdir(CFG_DIR)
                Auxiliary.try_mkdir(ICOCUR_DIR)
                                
                SCRIPT_LINE_PATTERN = re.compile(r'(\d+)(?:-(\d+))?(?:,(\d+))?')


        def folder_2lev( themnam ):
                """ Creates sub-directories. """
                global OUTPUT_BASE_DIR, OUTPUT_DIR, OUTPUT_CURS_DIR, logger
                                
                OUTPUT_DIR = OUTPUT_BASE_DIR + os.sep + themnam
                Auxiliary.try_mkdir(OUTPUT_DIR)
                OUTPUT_CURS_DIR = OUTPUT_DIR + os.sep + 'cursors'
                Auxiliary.try_mkdir(OUTPUT_CURS_DIR)
                logger.write('<------>< Image Extraction ><------>\n')
                

        def setup( N ):
                """ Imports parameters. """
                global TMP_DIR, CURSOR_NAMEMAP, logger
                
                ## Import directories.
                Auxiliary.folder_1lev( )
                CURSOR_NAMEMAP = Auxiliary.namecurs( )
                ## Open logging file.
                logger = open('%s/%s' %(TMP_DIR, 'logconv.txt'), 'a', encoding = 'utf-8')
                logger.write( Main.process_headernum( N ) )
                                
        
        def try_mkdir( pathdir ):
                """ Creates job folders. """
                os.makedirs(pathdir, exist_ok = True)

        def remove_readonly( func, path, excinfo ):
                """ Removes read only permission. """
                os.chmod(path, S_IWRITE)
                func(path)
               
        def resize_image( image, newsize, method = Image.ANTIALIAS ):
                """ Resizes a PIL image to a maximum size specified maintaining the aspect ratio.
                    Allows usage of different resizing methods and does not modify the image in place;
                    then creates an exact square image. """
                
                w, h = image.size
                nw, nh = newsize
                imAspect = float(w)/float(h)
                outAspect = float(nw)/float(nh)
                if imAspect >= outAspect:
                        ## Set w to maxWidth.
                        ## Set h to (maxWidth / imAspect).
                        image = image.resize( (nw, int((float(nw)/imAspect) + 0.5)), method )
                else:
                        ## Set w to (maxHeight * imAspect).
                        ## Set h to maxHeight.
                        image = image.resize( (int((float(nh)*imAspect) + 0.5), nh), method )
                        
                ## Create background transparent image.
                thumb = Image.new('RGBA', newsize, (255, 255, 255, 0))
                thumb.paste( image, ((nw - image.size[0]) // 2, (nh - image.size[1]) // 2) )
                        
                return thumb
        

        def resize_make( w_res, h_res, img_list ):
                """ Applies resize with icon dimensions to image list and adjusts hotspots. """
                global mouse_x, mouse_y, frame_count
                
                w_norm, h_norm = img_list[0].size
                scale_x = w_res / w_norm
                scale_y = h_res / h_norm
                
                img_list = [ Auxiliary.resize_image(img_list[i], (w_res, h_res), method = Image.ANTIALIAS) for i in range(frame_count) ]
                        
                ## Scale hotspots.                                
                mouse_x = int(0.5 * ceil(2.0 * (mouse_x * scale_x)))
                mouse_y = int(0.5 * ceil(2.0 * (mouse_y * scale_y)))
                
                return img_list
        

        def single_image( image_width, image_height, imgstrip ):
                """ Gets images from strip image. """
                global frame_count
                
                frame_width = int(image_width / frame_count)
                frame_height = image_height

                img_list = [ imgstrip.crop((frame_width * i, 0, frame_width * (i+1), image_height)) for i in range(frame_count) ]
                                                        
                return img_list


        def crop_image( img_list ):
                """ Crops border. """
                global AUTO_CROP, mouse_x, mouse_y, frame_count

                if AUTO_CROP:
                        bbox = [mouse_x, mouse_y, mouse_x + 1, mouse_y + 1]
                        for i in range(frame_count):
                                tbbox = img_list[i].getbbox()
                                if tbbox is not None:
                                        bbox[0] = min(bbox[0], tbbox[0])
                                        bbox[1] = min(bbox[1], tbbox[1])
                                        bbox[2] = max(bbox[2], tbbox[2])
                                        bbox[3] = max(bbox[3], tbbox[3])
                       
                        img_list = [ img_list[i].crop(bbox) for i in range(frame_count) ]
                        mouse_x -= bbox[0]
                        mouse_y -= bbox[1]
                        
                return img_list
        

        def adjust_image( imgstrip, w_res, h_res, color ):
                """ Executes various image operations. """
                global ORIGINAL_DIR, image_index, cursor_status, frame_count
                
                ## Save image strip (format: img0-1.png).
                imgstrip.save('%s/img%d-%d.png' %(ORIGINAL_DIR, image_index, cursor_status), 'PNG')
                ## Get single images from strip frames.
                w, h = imgstrip.size
                img_list = Auxiliary.single_image( w, h, imgstrip )
                ## Crop transparent border.
                img_list = Auxiliary.crop_image( img_list )
                ## Resize.
                img_list = Auxiliary.resize_make( w_res, h_res, img_list )
                ## Colorize.
                img_list = [ Auxiliary.colorize( color, img_list[i] ) for i in range(frame_count) ]
                ## Save images. (format: img0-1_0.png)
                for i in range(frame_count):
                        img_list[i].save('%s/img%d-%d_%d.png' %(ORIGINAL_DIR, image_index, cursor_status, i), 'PNG')

                        
        def colorize( colortype, image ):
                """ Changes color cursor. """
                if colortype == 'rgb':
                        ## rgba --> colorization original.
                        return image
                else:
                        image = numpy.array(image.convert('RGBA'))
                        r, g, b, a = image.T
                        chan1, chan2, chan3 = list(colortype)
                        ## rbga --> variation red.
                        ## grba --> variation green.
                        ## brga --> variation green.
                        ## gbra --> variation blue.
                        ## bgra --> variation blue.
                        new_image = numpy.dstack((eval(chan1), eval(chan2), eval(chan3), a))
                        new_image = Image.fromarray(new_image, 'RGBA')
                        return new_image
                

        def what_write( typeplatf, typext, *args ):
                """ Support for writing config files. """
                global cfg
                
                towrite = '%s/img%d-%d_%d.%s %d\n' %(args[0], args[1], args[2], args[3], typext ,args[4])

                if typeplatf == 'Linux':
                        stringini = '%d %d %d ' %(args[5], args[6], args[7])
                        towrite = stringini + towrite
                        
                cfg.write(towrite)
                
                        
        def parser_script( script_data, typeplatf, xsize ):
                """ Creates the sequence script defined. """
                global SCRIPT_LINE_PATTERN, frame_interval, frame_count, mouse_x, mouse_y, image_index, cursor_status
                global ICOCUR_DIR, ORIGINAL_DIR
                global logger, cfg
                
                script_parsed = False
                script_flag = True
                try:
                        if script_data == None:
                                pass
                        else:
                                if typeplatf == 'Windows':
                                        ## Config file header for Windows.
                                        cfg.write('%d\n%d\n' %(frame_count, frame_interval)) 
                                        cfg.write('%d\n%d\n' %(mouse_x, mouse_y)) 
                                for x in script_data:
                                        ## Note this examples:
                                        ## SCRIPT_LINE_PATTERN.match('2-5,30').groups() --> ('2', '5', '30')
                                        ## SCRIPT_LINE_PATTERN.match('6-10').groups() --> ('6', '10', None) 
                                        ## SCRIPT_LINE_PATTERN.match('1,3000').groups() --> ('1', None, '3000')
                                        start_frame, end_frame, interval = SCRIPT_LINE_PATTERN.match(x).groups() 
                                        start_frame = int(start_frame)
                                        
                                        if end_frame is None:
                                                end_frame = start_frame
                                        else:
                                                end_frame = int(end_frame)
                                                
                                        if interval is None:
                                                interval = frame_interval
                                        else:
                                                interval = int(interval)

                                        step = 1 if end_frame >= start_frame else -1

                                        ## Note that the frame index in the script is 1-based.
                                        if start_frame <= frame_count and end_frame <= frame_count:
                                                for i in range(start_frame, end_frame + step, step):
                                                        if typeplatf == 'Windows':
                                                                Auxiliary.what_write( typeplatf, 'ico', ICOCUR_DIR,image_index,cursor_status,i-1,interval)
                                                        elif typeplatf == 'Linux':
                                                                Auxiliary.what_write( typeplatf, 'png', ORIGINAL_DIR,image_index,cursor_status,i-1,interval,
                                                                                      xsize,mouse_x,mouse_y)
                                        else:
                                                script_flag = False
                                                break
                                                
                                script_parsed = script_flag
                except:
                        logger.write(' !!! Script Error --> Cannot parse script line: %s\n' %x)
                        pass

                return script_parsed
        

        def parser_animation( typeplatf, xsize ):
                """ Creates the sequence animation defined. """
                global animation_type, frame_interval, frame_count, mouse_x, mouse_y, image_index, cursor_status
                global ICOCUR_DIR, ORIGINAL_DIR
                global cfg, logger

                if typeplatf == 'Windows':
                        ## Config file header for Windows.
                        cfg.write('%d\n%d\n' %(frame_count, frame_interval)) 
                        cfg.write('%d\n%d\n' %(mouse_x, mouse_y))
                        
                if animation_type == 0:         # ANIMATION_TYPE_NONE
                        for i in range(frame_count):
                                if typeplatf == 'Windows':
                                        Auxiliary.what_write( typeplatf, 'ico', ICOCUR_DIR,image_index,cursor_status,i,
                                                              (frame_interval if (i < frame_count - 1) else 1000000) )
                                elif typeplatf == 'Linux':
                                        Auxiliary.what_write( typeplatf, 'png', ORIGINAL_DIR,image_index,cursor_status,i,
                                                              (frame_interval if (i < frame_count - 1) else 1000000), xsize,mouse_x,mouse_y )
 
                elif animation_type == 2:       # ANIMATION_TYPE_LOOP
                        for i in range(frame_count):
                                if typeplatf == 'Windows':
                                        Auxiliary.what_write( typeplatf, 'ico', ICOCUR_DIR,image_index,cursor_status,i,frame_interval )
                                elif typeplatf == 'Linux':
                                        Auxiliary.what_write( typeplatf, 'png', ORIGINAL_DIR,image_index,cursor_status,i,frame_interval,
                                                              xsize,mouse_x,mouse_y )
                        
                elif animation_type == 3:       # ANIMATION_TYPE_ALTERNATE
                        for i in chain(range(frame_count), range(frame_count-2,-1,-1)):
                                if typeplatf == 'Windows':
                                        Auxiliary.what_write( typeplatf, 'ico', ICOCUR_DIR,image_index,cursor_status,i,frame_interval )
                                elif typeplatf == 'Linux':
                                        Auxiliary.what_write( typeplatf, 'png', ORIGINAL_DIR,image_index,cursor_status,i,frame_interval,
                                                              xsize,mouse_x,mouse_y ) 
                else:
                        logger.write(' !!! Animation Error --> Unknown animation type: %d\n' %animation_type)
                        pass
                        

## ____________________________________
##| Stardock Cursor themes conversion  |--------------------------------------------------------------------------------------------------------------------
##|____________________________________|
##
class StardockCursor(object):      
        
        def convert_FX( fileFX, N, w_res, h_res, typeplatf, color ):
                """ Extracts data from file theme CURSORFX, then creates ANIs or X11s. """
                
                global CFG_DIR, logger, cfg
                global mouse_x, mouse_y, frame_count, animation_type, frame_interval, image_index, cursor_status

                ## Create directories.
                Auxiliary.setup( N )
                                
                ## Read data file.
                with open(fileFX, 'rb') as f:
                        data = f.read()

                ## Extract header data.
                version, header_size, data_size, theme_type = unpack_from('<4I', data, 0)
                info_size, = unpack_from('<I', data, header_size - 4)

                logger.write( 'Header Info:\n\n Version: %u\n Header Size: %u\n Data Size: %u\n Theme Type: %u\n Info size: %u\n\n'
                               %(version, header_size, data_size, theme_type, info_size) )
                
                ## Extract remaining data.
                data = decompress(data[header_size:])
        
                try:
                        assert len(data) == data_size
                except AssertionError:
                        logger.write('!!! Conversion Abort --> File %s Corrupted\n' %fileFX)
                        logger.close()
                        return

                ## Get theme info.
                info = data[:info_size].decode('utf-16le').split('\0')[:-1]
                ## Fill with ' ' if theme info data missing (theme info is a list of 3 elements).
                while len(info) < 3:
                        info.append(' ')
                comment = ' - '.join(info)
                logger.write('Theme info: %s\n' %comment)
                                        
                ## Get the theme name.
                theme_name = info[0].strip()
                if theme_name == ' ':
                        ## If theme name missing in data stream, get it from file name.
                        theme_name = fileFX.split(os.sep)[-1].split('.')[0]
                theme_name = theme_name.replace(',','_').replace(' ','')

                ## Creation subdirectories under "targets".
                Auxiliary.folder_2lev( theme_name )
                                        
                ## Start processing image data.
                cur_pos = info_size
                while cur_pos < len(data):

                        # Extract image data.
                        pointer_type, size_of_header_without_script_1, size_of_header_and_image = unpack_from('<3I', data, cur_pos)

                        if pointer_type != 2:
                                logger.write('!!! Cursor Skipped --> Found type #%d, not a pointer image\n' %pointer_type)
                                cur_pos += size_of_header_and_image
                                continue
                        (
                        unknown_1,
                        image_index,
                        cursor_status,
                        unknown_2,
                        frame_count,
                        image_width,
                        image_height,
                        frame_interval,
                        animation_type,
                        unknown_3,
                        mouse_x,
                        mouse_y,
                        size_of_header_with_script,
                        size_of_image,
                        size_of_header_without_script_2,
                        size_of_script
                        ) = unpack_from('<16I', data, cur_pos + calcsize('<3I'))
                  
                        logger.write('\nImage #%d:\n\n Type: %u\n Unknown_1: %u\n Index: %u\n Status: %u\n Unknown_2: %u\n Frame count: %u\n Image size: %ux%u\n \
Frame interval: %u\n Unknown_3: %u\n Animation type: %u\n Mouse position: (%u,%u)\n Size of script: %u\n' %(image_index, pointer_type, unknown_1,
                                                                                                    image_index, cursor_status, unknown_2,
                                                                                                    frame_count, image_width, image_height,
                                                                                                    frame_interval, unknown_3, animation_type,
                                                                                                    mouse_x, mouse_y, size_of_script))
                        
                        try:
                                assert size_of_header_without_script_1 == size_of_header_without_script_2
                                assert size_of_header_with_script == size_of_header_without_script_1 + size_of_script
                                assert size_of_header_and_image == size_of_header_with_script + size_of_image
                                assert size_of_image == image_width * image_height * 4
                        except AssertionError:
                                logger.write(' !!! Cursor Skipped --> Image #%d Corrupted\n' %image_index)
                                cur_pos += size_of_header_and_image
                                continue
                                

                        ## Get strip image frames and adjust. 
                        imgstrip = Image.frombytes('RGBA', (image_width, image_height),
                                                   data[cur_pos + size_of_header_with_script : cur_pos + size_of_header_and_image],
                                                   'raw', 'BGRA', 0, -1)
                        
                        Auxiliary.adjust_image( imgstrip, w_res, h_res, color )

                        ## ---> Parse script. <---
                        ## Create config file.
                        ##( format for Windows: numberFrames\n rateFrames\n hotspotx\n hotspoty\n scriptORanimationSequence\n )
                        ##( format for Linux: scriptORanimationSequence\n )
                        cfg = open('%s/img%d-%d.cfg' %(CFG_DIR, image_index, cursor_status), 'w')

                        if size_of_script > 0:
                                script_data = data[cur_pos + size_of_header_without_script : cur_pos + size_of_header_with_script].decode('utf-16le')[:-1].replace(';','\n').split()
                                ## Write script into log file.
                                logger.write(' Script:\n %s\n' %('\n '.join(script_data)))
                                ## Eventually expand loops.
                                if 'end repeat' in script_data:
                                        script_data = Repeat.loop_expand( script_data )
                        elif size_of_script == 0:
                                script_data = None
                                        
                        script_parsed = Auxiliary.parser_script( script_data, typeplatf, w_res )
                        
                        if not script_parsed:
                                if size_of_script > 0:
                                        ## Script not correctly formatted.
                                        logger.write(' !!! Script Error --> Fall back to default script animation for img%d-%d\n'
                                                     %(image_index, cursor_status))
                                        cfg.seek(0)
                                elif size_of_script == 0:
                                        ## Script not present.
                                        logger.write(' !!! Script Not Existent --> Fall back to default script animation for img%d-%d\n'
                                                     %(image_index, cursor_status))
                                        cfg.seek(0)
                                        
                                ## Not use a script but a default animation.
                                Auxiliary.parser_animation( typeplatf, w_res )
                                    
                        cfg.close()
                        ## Generate X11 cursor (for Linux) from current image.
                        if typeplatf == 'Linux':
                                X11Cursor.convert_X11( )
                                
                        cur_pos += size_of_header_and_image
                                
                ## Generate ANI cursors (for Windows).
                Main.process_complete( theme_name, typeplatf, comment,w_res,h_res )
                                


        def convert_XP( fileXP, N, w_res, h_res, typeplatf, color ):
                """ Extracts data from file theme CURXPTHEME, then creates ANIs or X11s. """
                
                global CFG_DIR, CURSOR_NAMEMAP, logger, cfg
                global mouse_x, mouse_y, frame_count, animation_type, frame_interval, image_index, cursor_status

                ## Create directories.
                Auxiliary.setup( N )

                ## Open Theme file.
                try:
                        archive = ZipFile(fileXP, 'r')
                        scheme = archive.read('Scheme.ini')
                        scheme = scheme.decode('ascii').replace(';','\r\n').split('\r\n')
                        ## Correction for multi return carriage.
                        scheme = [line for line in scheme if line != '']
                except:
                        logger.write('!!! Conversion Abort --> Scheme.ini not found into %s\n' %fileXP)
                        logger.close()
                        return
                        
                ## Get description content.
                descr_data = scheme[scheme.index('[Description]') + 1 ::]
                ## Get theme name from file name.
                theme_name = fileXP.split(os.sep)[-1].split('.')[0]
                theme_name = theme_name.replace(',','_').replace(' ','')
                logger.write('Theme Name: %s\n' %theme_name)
                ## Get comments from description.
                goodlines = [ line.strip() for line in descr_data if line.strip() != '' ]
                if goodlines == []:
                        comment = ''
                else:
                        comment = ' - '.join(goodlines)
                        logger.write('Theme Info: %s\n' %comment) 
                                
                ## Creation subdirectories under "targets".
                Auxiliary.folder_2lev( theme_name )
                        
                ## Get data index in 'Scheme.ini'.
                indx = [ scheme.index(line) for line in scheme if line.startswith('[') and line != '[General]' ]

                ## Do processing.
                for j in range(len(indx) - 1):
                        
                        if not scheme[indx[j]].endswith('_Script]'):                                         
                                
                                ## Get data image.
                                imag_data = scheme[indx[j] + 1 : indx[j + 1]]
                                name = scheme[indx[j]].replace('_Down','').replace('[','').replace(']','')
                                image_index = [ k for k, v in CURSOR_NAMEMAP.items() if name == v[0] ][0]

                                ## To prevent not correct ordering.
                                (cursor_status, frame_count, frame_interval, animation_type,
                                mouse_x1, mouse_y1, mouse_x2, mouse_y2, script_status) = [ 'undef' for _ in range(9) ]
                          
                                for line in imag_data:
                                        ident, val = line.split('=')
                                        if   ident == 'StdCursor': cursor_status = int(val)
                                        elif ident == 'Frames': frame_count = int(val)
                                        elif ident == 'Interval': frame_interval = int(val)
                                        elif ident == 'Animation style': animation_type = int(val)
                                        elif ident == 'Hot spot x': mouse_x1 = int(val)
                                        elif ident == 'Hot spot y': mouse_y1 = int(val)
                                        elif ident == 'Hot spot x2': mouse_x2 = int(val)
                                        elif ident == 'Hot spot y2': mouse_y2 = int(val)
                                        elif ident == 'FrameScript': script_status = int(val)

                                # Impose if lacking.
                                if cursor_status == 'undef':
                                        cursor_status = 0
                                if animation_type == 'undef':
                                        animation_type = 0
                                if script_status == 'undef':
                                        script_status = 0

                                if (frame_count == 0 or frame_count == 'undef') or (frame_interval == 0 or frame_interval == 'undef') or \
                                   any([mouse_x1 == 'undef', mouse_y1 == 'undef', mouse_x2 == 'undef', mouse_y2 == 'undef']):
                                        logger.write(' Cursor #%d Skipped --> Scheme.ini Corrupted\n' %image_index)
                                        continue
                                else:
                                        ## Put variables like cursorFX style.
                                        # Status.
                                        # for CursorXP --> CURSOR_STATUS_NORMAL = 0, CURSOR_STATUS_ERROR = 1
                                        cursor_status = 1 - cursor_status
                                        if scheme[indx[j]].endswith('_Down]'):
                                                cursor_status = 2

                                        # Animation.
                                        # for CursorXP --> ANIMATION_TYPE_LOOP = 0, ANIMATION_TYPE_ALTERNATE = 1
                                        animation_type = animation_type + 2                                                                                                                                                                                        

                                        ## Correction if different couples of hotspots.
                                        if mouse_x1 == mouse_x2 and mouse_y1 == mouse_y2:
                                                mouse_x = mouse_x1
                                                mouse_y = mouse_y1
                                        elif mouse_x1 != mouse_x2 or mouse_y1 != mouse_y2:
                                                mouse_x = min(mouse_x1, mouse_x2)
                                                mouse_y = min(mouse_y1, mouse_y2)

                                        ## Write data in log file.
                                        logger.write('\nImage #%d:\n\n Status: %u\n Frame count: %u\n Frame interval: %u\n Animation type: %u\n \
Mouse position: (%u,%u)\n Script status: %u\n' %(image_index, cursor_status, frame_count, frame_interval, animation_type, mouse_x, mouse_y, script_status))
                                        
                                ## Extract strip image.
                                if cursor_status in [1, 2]:
                                        try:
                                                imgstrip = Image.open(BytesIO(archive.read( name + '.png' )))
                                        except:
                                                logger.write(' !!! Cursor #%d Skipped --> Image Missing\n' %image_index)
                                                continue
                                elif cursor_status == 0:
                                        logger.write(' !!! Cursor #%d Skipped --> Image Missing\n' %image_index)
                                        continue

                                ## Get strip image frames and adjust.
                                Auxiliary.adjust_image( imgstrip, w_res, h_res, color )

                                ## Create config file with a default animation.
                                if script_status == 0:
                                        cfg = open('%s/img%d-%d.cfg' %(CFG_DIR, image_index, cursor_status), 'w')
                                        logger.write(' !!! Script Not Existent --> Fall back to default script animation for img%d-%d\n'
                                                     %(image_index, cursor_status))
                                        Auxiliary.parser_animation( typeplatf, w_res )
                                        cfg.close()
                                        ## Generate X11 cursor (for Linux) from current image.
                                        if typeplatf == 'Linux':
                                                X11Cursor.convert_X11( )                                                                                                   
                        else:
                                ## ---> Parse script. <---
                                ## script data follows cursor data section, so variables are already loaded.
                                if script_status == 1:
                                        ## Create config file.
                                        cfg = open('%s/img%d-%d.cfg' %(CFG_DIR, image_index, cursor_status), 'w')                                                                       
                                        ## Get script data.
                                        script_data = scheme[indx[j] + 1 : indx[j + 1]]
                                        
                                        ## Write script in log file.
                                        logger.write(' Script:\n %s\n' %('\n '.join(script_data)))
                                        ## Eventually expand loops.
                                        if 'end repeat' in script_data:
                                                script_data = Repeat.loop_expand( script_data )
                                        
                                        script_parsed = Auxiliary.parser_script( script_data, typeplatf, w_res )

                                        if not script_parsed: 
                                                ## Script not correctly formatted.
                                                logger.write(' !!! Script Error --> Fall back to default script animation for img%d-%d\n'
                                                             %(image_index, cursor_status))
                                                cfg.seek(0)
                                                        
                                                ## Not a script but use a default animation.
                                                Auxiliary.parser_animation( typeplatf, w_res )   
                                        cfg.close()
                                        
                                        ## Generate X11 cursor (for Linux) from current image.
                                        if typeplatf == 'Linux':
                                                X11Cursor.convert_X11( )
                                                        
                ## Generate ANI cursors (for Windows).
                Main.process_complete( theme_name, typeplatf, comment,w_res,h_res )             
                

## ____________________
##| Create X11 cursor  |------------------------------------------------------------------------------------------------------------------------------------
##|____________________| 
##
class X11Cursor(object):

        def convert_X11( ):
                """ Creates X11 cursors, using xcursorgen or byte-to-byte writer. """
                global CFG_DIR, OUTPUT_CURS_DIR
                global image_index, cursor_status, CURSOR_NAMEMAP, logger
                                
                ## Get elements from namemap.
                (outfilename, links) = CURSOR_NAMEMAP[image_index][2:4]
                ## Pressed cursors management.
                ## for CursorFX --> CURSOR_STATUS_NORMAL = 1, CURSOR_STATUS_PRESSED = 2
                if cursor_status == 2: 
                        outfilename += '_pressed'
                        links = []
                
                ## Try xcursorgen job.
                path_cfg = ' "%s/img%d-%d.cfg"' %(CFG_DIR, image_index, cursor_status)
                path_out = ' "%s/%s"' %(OUTPUT_CURS_DIR, outfilename)
                proc = Popen( 'xcursorgen' + path_cfg + path_out, shell = True, stdout = PIPE, stderr = PIPE )
                out, err = proc.communicate()
                retcode = proc.wait()
                       
                if retcode != 0:
                        err = ' '.join(out.decode('ascii').splitlines())
                        if err == '':
                                err = 'xcursorgen not installed or generic process error'
                        logger.write(" \n Can't convert cursor #%d by xcursorgen --> %s\n" %(image_index, err))

                for link in links:
                        try:
                            os.symlink(outfilename, '%s/%s' %(OUTPUT_CURS_DIR, link))
                        except:
                            logger.write(' Failed in creating symlink: "%s" --> "%s"\n' %(outfilename, link))
                logger.write('\n X11 cursor "%s" and Symlinks --> Done !!\n' %outfilename)
                            

        def pack_X11( themnam, desc ):
                """ Packages X11 theme. """
                global OUTPUT_DIR, OUTPUT_BASE_DIR, TMP_DIR, logger
                
                ## Create index.theme file.
                themefilestr = "[Icon Theme]\n" +\
                                "Name=%s\n" %themnam +\
                                "Comment=%s\n-*Converted by Metamorphosis, Copyright 2018\n" %desc +\
                                "Example=default\n" +\
                                "Inherits=core"
                
                with open('%s/index.theme' %OUTPUT_DIR, 'w') as ft:
                        ft.write(themefilestr)
                with open('%s/cursor.theme' %OUTPUT_DIR, 'w') as ft:
                        ft.write(themefilestr)
                        
                ## Create archive.
                path_arch = ' "%s/%s.tar.gz"' %(TMP_DIR, themnam)
                path_where = ' "%s" "%s"' %(OUTPUT_BASE_DIR, themnam)
                proc = Popen( 'tar -a -cf' + path_arch + ' -C' + path_where , shell = True, stdout = PIPE, stderr = PIPE )
                out, err = proc.communicate()
                retcode = proc.wait()
                
                if retcode != 0:
                        err = ''.join(out.decode('ascii').splitlines())
                        if err == ' ':
                                err = 'tar not installed or generic process error'
                        logger.write(' "%s" packaging skipped --> %s\n' %(themnam, err)) 
                
                logger.close()
                


## ___________________________
##| Image conversion to Icon  |----------------------------------------------------------------------------------------------------------------------------
##|___________________________| 
##
class Icon(object):
    
        def convert( ):
                """ ICO conversion manager. """
                global ORIGINAL_DIR, logger
                
                def natural_key(string_):
                        """ Natural sorting function. """
                        return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string_)]
                
                listfiles = [file for file in os.listdir(ORIGINAL_DIR) if "_" in file]
                listfiles = sorted(listfiles, key = natural_key)

                logger.write('\n<------>< Icons Creation ><------>\n')
                index = []
                for name_ima in listfiles:
                        name_ico = name_ima.replace('.png','.ico')
                        num = re.search('img(.*)-', name_ima).group(1)
                        if num not in index:
                                index.append(num)
                                logger.write('\nConversion to Icon of set Images index: %s\n' %num)
                        message = Icon.exec_convert( name_ico, name_ima )
                        logger.write(' ' + message + '\n')


        def exec_convert( name_ico, name_ima ):
                """ Executes Iconolatry for conversion PNGs to ICOs. """
                global ICOCUR_DIR, ORIGINAL_DIR

                path_icon = [ ICOCUR_DIR + os.sep + name_ico ]
                path_image = [ [ORIGINAL_DIR + os.sep + name_ima] ]
                message = Iconolatry.WRITER().ToIco( False, path_image, path_icon )

                return message
                

## ____________________
##| Create ANI cursor  |-----------------------------------------------------------------------------------------------------------------------------------
##|____________________| 
##
class ANICursor(object):
        
        def pack_ANI( name_arch, comments ):
                """ Packages ANI theme. """
                global TMP_DIR, OUTPUT_BASE_DIR
                
                ## Create file .inf.
                ANICursor.inf_file( name_arch, comments )
                ## Package.
                input_dir = OUTPUT_BASE_DIR + os.sep + name_arch
                zipname = TMP_DIR + os.sep + name_arch
                make_archive(zipname, 'zip', root_dir = input_dir, base_dir = None)
                

        def find_inamiart( data ):
                """ Finds 'INAM' and 'IART' string values. """
                try:
                        pos_inam = re.search(b'INAM', data).start()
                        try:
                                pos_iart = re.search(b'IART', data).start()
                                if pos_inam < pos_iart:
                                        ## 'INAM' - 'IART'. 
                                        inam = data[pos_inam + 8 : pos_iart]
                                        offiart, = unpack_from('<H', data[pos_iart + 4 : pos_iart + 8])
                                        iart = data[pos_iart + 8 : pos_iart + 8 + offiart]
                                else:
                                        ## 'IART' - 'INAM'.
                                        iart = data[pos_iart + 8 : pos_inam]
                                        offinam, = unpack_from('<H', data[pos_inam + 4 : pos_inam + 8])
                                        inam = data[pos_inam + 8 : pos_inam + 8 + offinam]
                        except AttributeError:
                                ## 'INAM' (only).
                                offinam, = unpack_from('<H', data[pos_inam + 4 : pos_inam + 8])
                                inam = data[pos_inam + 8 : pos_inam + 8 + offinam]
                                pass
                except AttributeError:
                        try:
                                ## 'IART' (only).
                                pos_iart = re.search(b'IART', data).start()
                                offiart, = unpack_from('<H', data[pos_iart + 4 : pos_iart + 8])
                                iart = data[pos_iart + 8 : pos_iart + 8 + offiart]
                        except AttributeError:
                                ## no INAM, no IART.
                                inam = iart = ''
                                pass
                                                        
                comment = inam + iart
                return comment
                

        def find_rateseq( data ):
                """ Finds 'rate' and 'seq ' values. """
                try:
                        pos_rate = re.search(b'rate', data).start()
                        try:
                                pos_seq = re.search(b'seq ', data).start()
                                if pos_rate < pos_seq:
                                        ## 'rate' - 'seq '.
                                        rates = data[pos_rate + 8 : pos_seq]
                                        offseq, = unpack_from('<H', data[pos_seq + 4 : pos_seq + 8])
                                        seqs = data[pos_seq + 8 : pos_seq + 8 + offseq]
                                else:
                                        ## 'seq ' - 'rate'.
                                        seqs = data[pos_seq + 8 : pos_rate]
                                        offrate, = unpack_from('<H', data[pos_rate + 4 : pos_rate + 8])
                                        rates = data[pos_rate + 8 : pos_rate + 8 + offrate]
                                        
                                iseqs = [ unpack_from('<L', seqs[ii : 4 + ii]) for ii in range(0, len(seqs), 4) ]
                                iseqs = [ seq[0] for seq in iseqs ]
                        except AttributeError:
                                ## 'rate' (only).
                                iseqs = None
                                offrate, = unpack_from('<H', data[pos_rate + 4 : pos_rate + 8])
                                rates = data[pos_rate + 8 : pos_rate + 8 + offrate]
                                pass
                        
                        irates = [ unpack_from('<L', rates[ii : 4 + ii]) for ii in range(0, len(rates), 4) ]
                        irates = [ rate[0] for rate in irates ]
                        irates = [ int(0.5 * ceil(2.0 * (int(irate) * (1000/60)))) for irate in irates ]  # converted from jiffies to ms.   

                except AttributeError:
                        irates = None
                        try:
                                ## 'seq ' (only).
                                pos_seq = re.search(b'seq ', data).start()
                                offseq, = unpack_from('<H', data[pos_seq + 4 : pos_seq + 8])
                                seqs = data[pos_seq + 8 : pos_seq + 8 + offseq]
                                iseqs = [ unpack_from('<L', seqs[ii : 4 + ii]) for ii in range(0, len(seqs), 4) ]
                                iseqs = [ seq[0] for seq in iseqs ]
                        except AttributeError:
                                ## no 'rate', no 'seq '.
                                iseqs = None
                                pass
                        
                return irates, iseqs

              
        def inf_file( themnam, comments ):
                """ Creates .inf file for Windows installation. """
                global OUTPUT_CURS_DIR, CURSOR_NAMEMAP
                
                ## Create install.inf file.
                schemereg = ['pointer','help','work','busy','cross','text','hand','unavailiable','vert','horz','dgn1','dgn2','move','alternate','link']
                schemecur = [ v[1] for k, v in CURSOR_NAMEMAP.items() if k in [i for j in (range(9), range(10,17,2), range(17,19)) for i in j] ]

                stringcur = ''
                for reg, cur in zip(schemereg, schemecur):
                        if reg in ['unavailiable', 'alternate', 'link']:
                                if reg == 'unavailiable':
                                        stringcur += reg + '= "' + cur + '.ani"\n'
                                elif reg == 'alternate':
                                        stringcur += reg + '\t= "' + cur + '.ani"\n'
                                elif reg == 'link':
                                        stringcur += reg + '\t\t= "' + cur + '.ani"'
                        else:
                                stringcur += reg + '\t\t= "' + cur + '.ani"\n'
                       
                schemeinf = "; %s Cursors Pack installation file\n" %themnam +\
                                '; Right click on the file "Install.inf" and select "Install". Then in the Mouse control panel apply set cursors.\n\n' +\
                                "[Version]\n" + "signature=""$CHICAGO$""\n\n" +\
                                "[DefaultInstall]\n" + "CopyFiles = Scheme.Cur, Scheme.Txt\n" +\
                                                       "AddReg    = Scheme.Reg\n\n" +\
                                "[DestinationDirs]\n" + 'Scheme.Cur = 10,"%CUR_DIR%"\n' +\
                                                        'Scheme.Txt = 10,"%CUR_DIR%"\n\n' +\
                                "[Scheme.Reg]\n" + 'HKCU,"Control Panel\\Cursors\\Schemes","%SCHEME_NAME%",,"' +\
                                                   ''.join('%10%\\%CUR_DIR%\\%{}%,'.format(val) for val in schemereg[0:len(schemereg)-1]) +\
                                                   '%10%\\%CUR_DIR%\\%' + schemereg[-1] + '%"\n\n' +\
                                "; --Common Information\n\n" +\
                                "[Scheme.Cur]\n" + '"' + '.ani"\n"'.join(schemecur) + '.ani"\n\n' +\
                                "[Scheme.Txt]\n" + 'Readme.txt\n\n' +\
                                "[Strings]\n" + 'CUR_DIR\t\t= "Cursors\\%s"\n' %themnam +\
                                                'SCHEME_NAME\t= "%s"\n' %themnam + stringcur

                with open('%s/Install.inf' %OUTPUT_CURS_DIR, 'w') as f:
                        f.write(schemeinf)
                with open('%s/Readme.txt' %OUTPUT_CURS_DIR, 'w') as f:
                        f.write(comments + '\n-*Converted by Metamorphosis, Copyright 2018')


        def int_to_hex( value, byteorder = 'little', padbytes = 2 ):
                """ Transforms an integer into his hex representation (little or big endian).
                    Usually padbytes = 1 (8-bit), 2 (16-bit), 4 (32-bit), 8 (64-bit). """
                lung = (value.bit_length() + 7) // 8
                ## Add padding, if needs.
                pad = padbytes - lung
                if pad < 0: pad = 0
                ## Create hex representation.
                a = value.to_bytes( lung + pad, byteorder = byteorder ) or b'\0'
                hexstring = hexlify(a).decode('ascii')
                return hexstring
        

        def change_hex( data, ini_pos_to_change, fin_pos_to_change, value_to_change ): 
                """ Changes hexadecimal values.
                    If 'ini_pos_to_change' is equal to 'fin_pos_to_change' then 'value_to_change' is a single string ('xx'),
                    if positions to change are more then one, 'values_to_change' is a list of strings ('xxyyzz' --> ['xx','yy','zz']). """
                hex_ini = hexlify(data).decode('ascii')
                s = list(hex_ini)
                ## Modify digits.
                if ini_pos_to_change == fin_pos_to_change:
                        s[ini_pos_to_change] = value_to_change
                elif ini_pos_to_change < fin_pos_to_change:
                        s[ini_pos_to_change : fin_pos_to_change] = list(value_to_change)
                        
                hex_mod = unhexlify(''.join(s))
                return hex_mod
        
        
        def write_icon( fileread, size, f_ani, hotx, hoty ):
                """ Writes ICO data with modifications into ANI file. """
                with open(fileread, 'rb') as f_icon:
                        for line, _ in enumerate(range(0, size, 16)):
                                data = f_icon.read(16)
                                ## Modifications into icon files to transform ICO into CUR.
                                if line == 0:
                                        ## idType modification.
                                        data = ANICursor.change_hex( data, ini_pos_to_change = 4, fin_pos_to_change = 8, value_to_change = '0200' )
                                        ## hotspotX modification.
                                        data = ANICursor.change_hex( data, ini_pos_to_change = 20, fin_pos_to_change = 24, value_to_change = hotx )
                                        ## hotspotY modification.
                                        data = ANICursor.change_hex( data, ini_pos_to_change = 24, fin_pos_to_change = 28, value_to_change = hoty )
                                ## Write icon data into ANI file.
                                f_ani.write(data)
                return f_ani
        

        def write_ani( filewrite, header_ani, config_data, header_icon, hotspotX, hotspotY ):
                """ Writes ANI file. """
                with open(filewrite, 'wb+') as f_ani:
                        ## Write ANI header's into ani file.
                        f_ani.write( unhexlify(header_ani) )
                        ## Write 'icon' identifier with his size identifier and data,
                        ## for all icons to put into ANI file.
                        for element in config_data[4::]:
                                path_icon = element.split(' ')[0]
                                iconSize = os.path.getsize(path_icon)
                                hex_iconSize = ANICursor.int_to_hex( iconSize, byteorder = 'little', padbytes = 4 )
                                f_ani.write( unhexlify(header_icon + hex_iconSize) )
                                f_ani = ANICursor.write_icon( path_icon, iconSize, f_ani, hotspotX, hotspotY )
                                
                        ## Fix riffSize with the correct value after writing ANI file.
                        riffSize = f_ani.tell() - 8                                
                        f_ani.seek(4)     
                        hex_riffSize = ANICursor.int_to_hex( riffSize, byteorder = 'little', padbytes = 4 )
                        f_ani.write( unhexlify(hex_riffSize) )
                        ## Fix listSize with the correct value after writing all icons into ANI file.
                        f_ani.seek(0)
                        offset = re.search(b'fram', f_ani.read()).start() - 4
                        listSize = riffSize - (offset - 4)
                        hex_listSize = ANICursor.int_to_hex( listSize, byteorder = 'little', padbytes = 4 )
                        f_ani.seek(offset)
                        f_ani.write( unhexlify(hex_listSize) )
                       
                        
        def convert_ANI( w_res, h_res, theme_name ):
                """ Creates ANI cursor, writing it byte-to-byte. """
                global CFG_DIR, OUTPUT_CURS_DIR, CURSOR_NAMEMAP

                logger.write('\n<------>< ANI Cursors Creation ><------>\n\n')
                                             
                ## Define global data for 'anih'.
                anihSize = cbSize =     ANICursor.int_to_hex( 36, byteorder = 'little', padbytes = 4 )
                iWidth =                ANICursor.int_to_hex( int(w_res), byteorder = 'little', padbytes = 4 )
                iHeight =               ANICursor.int_to_hex( int(h_res), byteorder = 'little', padbytes = 4 )
                iBitCount =             ANICursor.int_to_hex( 32, byteorder = 'little', padbytes = 4 )
                nPlanes =               ANICursor.int_to_hex( 1, byteorder = 'little', padbytes = 4 )
                bfAttributes =          ANICursor.int_to_hex( 3, byteorder = 'little', padbytes = 4 )

                ## Define data for IART.                
                iart = b'*Converted by Metamorphosis, Copyright 2018*' # note: need even length.
                iart = hexlify(iart).decode('ascii')
                iart_int = int(len(iart)/2)
                iartSize = ANICursor.int_to_hex( iart_int, byteorder = 'little', padbytes = 4 )

                ## Define hex representation of common tags.
                ## riffSize and listSize are initially put to zero.
                header_dict = {'RIFF':'52494646',       'riffSize':'00000000',  'ACON':'41434f4e',      'anih':'616e6968',
                               'rate':'72617465',       'seq ':'73657120',
                               'INFO':'494e464f',       'INAM':'494e414d',      'IART':'49415254',
                               'LIST':'4c495354',       'listSize':'00000000',  'fram':'6672616d',      'icon':'69636f6e'
                              }

                ## Get parameters using config files.
                cfgs = os.listdir(CFG_DIR)

                for cfg in cfgs:
                        with open(CFG_DIR + '/%s' %cfg, 'r') as f_cfg:  
                                config_data = f_cfg.readlines()
                        config_data = [ line.replace('\n','') for line in config_data]

                        ## Define name and path of ANI file.
                        im, st = re.search('img(.*)-(.*).cfg', cfg).groups()
                        name_ani = CURSOR_NAMEMAP[int(im)][1]
                        if int(st) == 2:
                                name_ani += '_pressed'
                                
                        filewrite = OUTPUT_CURS_DIR + os.sep + name_ani + '.ani'
                        
                        ## Define remaining data for 'anih'.
                        nFrames = nSteps =      ANICursor.int_to_hex( int(config_data[0]), byteorder = 'little', padbytes = 4 )
                        ## Convert rate from ms to jiffies.
                        iDispRate = int(0.5 * ceil(2.0 * (int(config_data[1]) / (1000/60))))
                        iDispRate =             ANICursor.int_to_hex( iDispRate, byteorder = 'little', padbytes = 4 )
                        hotspotX =              ANICursor.int_to_hex( int(config_data[2]), byteorder = 'little', padbytes = 2 )
                        hotspotY =              ANICursor.int_to_hex( int(config_data[3]), byteorder = 'little', padbytes = 2 )

                        ## Define data for INAM.
                        inam = theme_name + '-' + name_ani
                        inam_byt = hexlify(bytes(inam, 'utf-8')).decode('ascii')
                        ## Need even length.
                        if len(inam) % 2 != 0:
                                inam = inam_byt + '2a'
                        else:
                                inam = '2a' + inam_byt + '2a'
                        
                        inam_int = int(len(inam)/2)
                        inamSize = ANICursor.int_to_hex( inam_int, byteorder = 'little', padbytes = 4 )

                        ## Define size of all tag INFO.
                        ## header_dict['IART'] + iartSize = 4 + 4 = 8
                        ## header_dict['INFO'] + header_dict['INAM'] + inamSize = 4 + 4 + 4 = 12
                        infoSize = inam_int + iart_int + 8 + 12
                        infoSize = ANICursor.int_to_hex( infoSize, byteorder = 'little', padbytes = 4 )
            
                        ## Start to construct ANI Header.
                        header_ani =  header_dict['RIFF']       + header_dict['riffSize']       + header_dict['ACON']
                        header_ani += header_dict['LIST']       + infoSize
                        header_ani += header_dict['INFO']        
                        header_ani += header_dict['INAM']       + inamSize                      + inam
                        header_ani += header_dict['IART']       + iartSize                      + iart                              
                        header_ani += header_dict['anih']
                        header_ani += anihSize                  + cbSize                        + nFrames               + nSteps
                        header_ani += iWidth                    + iHeight                       + iBitCount             + nPlanes
                        header_ani += iDispRate                 + bfAttributes

                        ## Continue to construct ANI Header with tag 'rate' and 'seq '.
                        seqSize = rateSize = ANICursor.int_to_hex( int(config_data[0]) * 4, byteorder = 'little', padbytes = 4 )
                        header_ani_rate = header_dict['rate']    + rateSize
                        header_ani_seq =  header_dict['seq ']    + seqSize
                                        
                        for element in config_data[4::]:
                                path_icon, framrate = element.split(' ')
                                seq = re.search('_(.*).ico', path_icon.split('/')[-1]).group(1)
                                ## Convert rate from ms to jiffies.
                                framrate = int(0.5 * ceil(2.0 * (int(framrate) / (1000/60))))
                                header_ani_rate += ANICursor.int_to_hex( framrate, byteorder = 'little', padbytes = 4 )
                                header_ani_seq +=  ANICursor.int_to_hex( int(seq), byteorder = 'little', padbytes = 4 )       

                        header_ani +=   header_ani_rate + header_ani_seq

                        ## Continue to construct ANI Header with tag 'icon'.
                        header_ani +=   header_dict['LIST']     + header_dict['listSize']       + header_dict['fram']
                        
                        header_icon =   header_dict['icon'] 

                        ## Do process.
                        ANICursor.write_ani( filewrite, header_ani, config_data, header_icon, hotspotX, hotspotY )
                        logger.write(' %s ----> Done !!\n' %filewrite)
                        
                logger.close()
                
               

## ___________________________________
##| Utilities for cursors convertion  |---------------------------------------------------------------------------------------------------------------------
##|___________________________________| 
## 
class Utility(object):

        def convert_ANI_to_X11( pathpointer, N, folder, w_res, h_res, color, comment_list ):
                """ Creates PNGs from ANI or CUR cursor, then produces X11 cursor. """
                
                global ORIGINAL_DIR, CFG_DIR, CURSOR_NAMEMAP, logger, ICOCUR_DIR
                global mouse_x, mouse_y, image_index, cursor_status, frame_count

                ## Create directories.
                Auxiliary.setup( N )
                
                ## Creation subdirectories under "targets".
                Auxiliary.folder_2lev( folder )
                
                ## Get index of pointer.
                name, extens = pathpointer.split(os.sep)[-1].split('.')
                try:
                        image_index = [k for k, v in CURSOR_NAMEMAP.items() if name == v[1]][0]
                except:
                        logger.write('\n !!! Cursor "%s" Skipped --> Have not standard Windows name.\n' %'.'.join([name, extens]))
                        logger.close()
                        return comment_list
                        
                ## Read data from file.
                with open(pathpointer, 'rb') as file:
                        data = file.read()
        
                cursor_status = 1  # imposed always 1, not exist status pressed for .ani and .cur.
                                
                if extens.lower() == 'cur':
                        animation_type = 0       ## imposed NONE for .cur.
                        frame_interval = 1000000 ## imposed Inf for .cur.

                        curs_readed, log_err = Iconolatry.READER().FromIcoCur( data, rebuild = True )
                        if log_err == '':
                                for cur in curs_readed:
                                        ima, frame_count, image_width, image_height, mouse_x, mouse_y = cur
                                        
                                        ## Eventually resize.
                                        ima = Auxiliary.resize_make( w_res, h_res, [ima] )
                                        ## Eventually change color.
                                        ima = Auxiliary.colorize( color, ima[0] )
                                        ## Save image (conversion .cur --> .png).
                                        ima.save('%s/img%d-%d_%d.png' %(ORIGINAL_DIR, image_index, cursor_status, frame_count - 1), 'PNG')
                                        ## Create .conf file.
                                        with open('%s/img%d-%d.cfg' %(CFG_DIR, image_index, cursor_status), 'w') as cfg:
                                                cfg.write('%d %d %d %s/img%d-%d_%d.png %d\n' %(image_width, mouse_x, mouse_y, ORIGINAL_DIR, image_index,
                                                                                               cursor_status, frame_count - 1, frame_interval))
                        else:
                                logger.write(log_err)
                                       
                elif extens.lower() == 'ani':
                        animation_type = 2  ## imposed LOOP for .ani.
                                
                        ## Find 'anih' parameters.
                        pos_anih = re.search(b'anih', data).start()
                        frame_count_real, = unpack_from('<L', data[pos_anih + 12 : pos_anih + 16])
                        frame_count = 1   ## Imposed for resize images of ANIs one by one.
                        image_width, image_height = unpack_from('<2L', data[pos_anih + 20 : pos_anih + 28])
                        frame_interval, = unpack_from('<L', data[pos_anih + 40 : pos_anih + 44])
                        frame_interval = int(0.5 * ceil(2.0 * (int(frame_interval) * (1000/60)))) # converted from jiffies to ms.

                        irates, iseqs = ANICursor.find_rateseq( data )
                        comment = ANICursor.find_inamiart( data )
                        comment = str(comment, 'utf-8').replace('\x00','') + ';'

                        ## Find 'icon' data.
                        posico = [ ic.start() for ic in re.finditer(b'icon', data) ]
                        
                        for ii in range(frame_count_real):
                                try:
                                        curs_readed, log_err = Iconolatry.READER().FromIcoCur( data[posico[j] + 8 : posico[j + 1]], rebuild = True )
                                except:
                                        ## To get the last figure. 
                                        curs_readed, log_err = Iconolatry.READER().FromIcoCur( data[posico[ii] + 8 : len(data)], rebuild = True )
                                        
                                if log_err == '':
                                        for cur in curs_readed:
                                                ima, _, _, _, mouse_x, mouse_y = cur
                                                
                                                ## Eventually resize.
                                                ima = Auxiliary.resize_make( w_res, h_res, [ima] )
                                                ## Eventually change color.
                                                ima = Auxiliary.colorize( color, ima[0] )
                                                ## Save images (conversion .cur --> .png).
                                                ima.save('%s/img%d-%d_%d.png' %(ORIGINAL_DIR, image_index, cursor_status,
                                                                                (iseqs[ii] if iseqs != None else ii)), 'PNG')
                                else:
                                        logger.write(log_err)
                                        
                                ## Create .conf files.
                                with open('%s/img%d-%d.cfg' %(CFG_DIR, image_index, cursor_status), 'a') as cfg:
                                        cfg.write('%d %d %d %s/img%d-%d_%d.png %d\n' %(image_width, mouse_x, mouse_y, ORIGINAL_DIR,
                                                                                       image_index, cursor_status,
                                                                                       (iseqs[ii] if iseqs != None else ii),
                                                                                       (irates[ii] if irates != None else frame_interval)))
                        ## Re-assign right variable.
                        frame_count = frame_count_real
                        ## Get ANI's total comment.
                        if comment not in comment_list:
                                comment_list.append(comment)
                        
                ## Write into log file general info.
                logger.write('\nImage #%d:\n\n Status: %u\n Width: %u\n Height: %u\n Frame count: %u\n Frame interval: %u\n Animation type: %u\n \
Mouse position: (%u,%u)\n' %(image_index, cursor_status, image_width, image_height, frame_count, frame_interval, animation_type, mouse_x, mouse_y))
                
                ## Generate X11 cursor.
                X11Cursor.convert_X11( )
                
                return comment_list


## _______
##| Main  |------------------------------------------------------------------------------------------------------------------------------------------------
##|_______|
##
class Main(object):
        
        def choice( message, list_of_choice ):
                """ Gets user-defined parameters. """
                while True:
                        varchoice = input('%s %s:\n' %(message, '['+ ' - '.join(list_of_choice) +']'))
                        if varchoice in list_of_choice:
                                break
                        else:
                                print ('??? Insert correctly...')
                return varchoice

        def check_magic( path, file ):
                """ Checks if file is X11 cursor. """
                path_file = os.path.join(path, file)
                magic = Popen(['file', path_file], stdout = PIPE).communicate()[0].strip().decode('utf-8').split(': ')[1]
                if magic == 'X11 cursor':
                        return True
                else:
                        return False

        def clean_all( remove_all = True ):
                """ Deletes used files after processing. """
                global OUTPUT_BASE_DIR, CFG_DIR, ORIGINAL_DIR, ICOCUR_DIR
                
                rmtree(ORIGINAL_DIR, onerror = Auxiliary.remove_readonly)
                rmtree(CFG_DIR, onerror = Auxiliary.remove_readonly)
                rmtree(ICOCUR_DIR, onerror = Auxiliary.remove_readonly)
                if remove_all:
                        rmtree(OUTPUT_BASE_DIR, onerror = Auxiliary.remove_readonly)
                

        def process_setup( ):
                """ Creates initial parameters for process. """
                nproc, old_nproc, nproc_sub, old_nproc_sub = (0 for _ in range(4))
                old_folder = ''
                times_sub, comment_list, used_list, flag_glb = ([] for _ in range(4))
                flag_compl = True
                is_folder = (False, False)
                return nproc, old_nproc, nproc_sub, old_nproc_sub, is_folder, old_folder, times_sub, flag_compl, comment_list, used_list, flag_glb
        
        def process_time( atime ):
                """ To format process time. """
                minutes, seconds = divmod(atime, 60)
                hours, minutes = divmod(minutes, 60)
                return hours, minutes, seconds

        def process_headernum( number ):
                """ Prints number of process. """
                n0 = ' ██████╗\n██╔═████╗\n██║██╔██║\n████╔╝██║\n╚██████╔╝\n ╚═════╝'
                n1 = ' ██╗\n███║\n╚██║\n ██║\n ██║\n ╚═╝'
                n2 = '██████╗\n╚════██╗\n █████╔╝\n██╔═══╝\n███████╗\n╚══════╝'
                n3 = '██████╗\n╚════██╗\n █████╔╝\n ╚═══██╗\n██████╔╝\n╚═════╝'
                n4 = '██╗  ██╗\n██║  ██║\n███████║\n╚════██║\n     ██║\n     ╚═╝'
                n5 = '███████╗\n██╔════╝\n███████╗\n╚════██║\n███████║\n╚══════╝'
                n6 = ' ██████╗\n██╔════╝\n███████╗\n██╔═══██╗\n╚██████╔╝\n ╚═════╝'
                n7 = '███████╗\n╚════██║\n    ██╔╝\n   ██╔╝\n   ██║\n   ╚═╝'
                n8 = ' █████╗\n██╔══██╗\n╚█████╔╝\n██╔══██╗\n╚█████╔╝\n ╚════╝'
                n9 = ' █████╗\n██╔══██╗\n╚██████║\n ╚═══██║\n █████╔╝\n ╚════╝'
                np = '\n\n\n\n██╗\n╚═╝'


                dict_header = {'0':n0, '1':n1, '2':n2, '3':n3, '4':n4, '5':n5, '6':n6, '7':n7, '8':n8, '9':n9, '.':np}
                digits = list(str(number))

                lung = len(digits)
                asciiart_number = []
                if lung > 1:
                        allchunks = [ dict_header[digit].split('\n') for digit in digits ]

                        for items in zip(*allchunks):
                                obj = ''
                                for item in items:
                                        if len(item) != 0 and 4 <= len(item) < 8:
                                                obj += item + '\t\t'
                                        else:
                                                obj += item + '\t'
                                asciiart_number.append(obj)                                        
                        asciiart_number = '\n'.join(asciiart_number)
                else:
                        asciiart_number = dict_header[str(number)]
                asciiart_number = '\n' + asciiart_number + '\n#################################################\n\n'
                return asciiart_number

                
        def process_folder( filename, folder, old_folder, nproc, old_nproc, nproc_sub, old_nproc_sub, is_something, platf_distrib ):
                """ Creates messages during process. """
                flag_compl = True
                                
                if folder != old_folder:
                        print('---> Start Processing #%d: %s <---' %(nproc, folder + ' folder'))
                        old_folder = folder
                        
                        if nproc_sub == 0:
                                nproc_sub += 1
                                print('---> Start Processing #%d.%d: %s <---' %(nproc, nproc_sub, filename))
                                if (platf_distrib == 'Windows' and is_something[0]) or (platf_distrib == 'Linux' and is_something[1]):
                                        ## Not-operation to convert .ani/.cur into .ani/.cur. OR to convert x11 into x11.
                                        print('---> Process #%d.%d Abort, Conversion Not Needed <---' %(nproc, nproc_sub))
                                        flag_compl = False
                                                                                
                        old_nproc_sub = nproc_sub     
                        old_nproc = nproc
                        nproc += 1
                        nproc_sub = 0
                else:
                        old_nproc_sub += 1
                        print('---> Start Processing #%d.%d: %s <---' %(old_nproc, old_nproc_sub, filename))
                        if (platf_distrib == 'Windows' and is_something[0]) or (platf_distrib == 'Linux' and is_something[1]):
                                ## Not-operation to convert .ani/.cur into .ani/.cur.
                                print('---> Process #%d.%d Abort, Conversion Not Needed <---' %(old_nproc, old_nproc_sub))
                                flag_compl = False
                                
                return old_folder, nproc, old_nproc, nproc_sub, old_nproc_sub, flag_compl
        

        def process_complete( themnam, typeplatf, *args ):
                """ Completes process."""
                if typeplatf == 'Linux':
                        X11Cursor.pack_X11( themnam, args[0] )
                elif typeplatf == 'Windows':
                        Icon.convert( )
                        ANICursor.convert_ANI( args[1], args[2], themnam )
                        ANICursor.pack_ANI( themnam, args[0] )
                Main.clean_all( remove_all = True )
                

        def process_filenames( filenames, dirpath ):
                """ Removes duplicates and checks extensions of files. """     
                filenames.sort()
                ## Remove name duplicates.
                for grp_name, grp_files in groupby(filenames, lambda f: os.path.splitext(f)[0]):
                        dupli = list(grp_files)
                        if len(dupli) > 1:
                                filenames.remove(dupli[0])
                                print('!!! Duplicate File ---> File "%s" will not be converted.\n' %dupli[0])
                                
                ## Check extensions.
                filenames = [ file for file in filenames if file.lower().endswith(tuple(['.cursorfx', '.curxptheme', '.ani', '.cur']))
                              or Main.check_magic(dirpath, file) ]
                
                return filenames

                              
        def main( ):
                """ Main Process. """
                global TMP_DIR, ROOT_DIR

                ## Path root.
                ## Linux -->   /home/User/Metamorphosis
                ## Windows --> C:\\Users\\User\\Metamorphosis
                ROOT_DIR = os.path.normpath(os.path.expanduser('~'+ os.sep + 'Metamorphosis'))
                if ROOT_DIR.startswith('\\'):
                        ROOT_DIR = 'C:' + ROOT_DIR
                if not os.path.isdir(ROOT_DIR):
                        print('ROOT folder not exists --> Create "Metamorphosis" folder')
                        return
                                       
                ## Path of jobs directory.
                TMP_DIR = os.path.join(ROOT_DIR, 'conversion')
                ## Path of folder with files to convert.
                FILE_DIR = os.path.join(ROOT_DIR, 'curs2conv')
                if not os.path.isdir(FILE_DIR):
                        print('FILE folder not exists --> Create sub-folder "curs2conv"')
                        return
                
                ## Define width and heigth.
                sz = Main.choice( 'Select size of converted cursors:', ['16','24','32','48','64','96'] )
                width = height = int(sz)
                ## Define color.
                color = Main.choice( 'Select color variation of converted cursors:', ['rgb','rbg','grb','brg','gbr','bgr'] )
                ## Define distribute platform.
                platf_distrib = Main.choice( 'Select OS where use converted cursors:', ['Linux','Windows'] )
                
                ## Do conversion.
                (nproc, old_nproc,
                nproc_sub, old_nproc_sub,
                is_folder, old_folder,
                times_sub, flag_compl,
                comment_list, used_list, flag_glb) = Main.process_setup( )
                
                print('---> Metamorphosis working... <---\n')
               
                for dirpath, dirnames, filenames in os.walk(FILE_DIR):
                        filenames = Main.process_filenames( filenames, dirpath )
                        
                        for filename in filenames:
                                                       
                                path_file = os.path.join(dirpath, filename)
                                folder = dirpath.split('/')[-1]
                                tic = perf_counter()
                                
                                if filename.lower().endswith('.cursorfx'):
                                        print('---> Start Processing #%d: %s <---' %(nproc, filename))
                                        StardockCursor.convert_FX( path_file, nproc, width, height, platf_distrib, color )
                                                                                                                
                                elif filename.lower().endswith('.curxptheme'):
                                        print('---> Start Processing #%d: %s <---' %(nproc, filename))
                                        StardockCursor.convert_XP( path_file, nproc, width, height, platf_distrib, color )
                                                                                
                                elif filename.lower().endswith(tuple(['.ani', '.cur'])):
                                        is_folder = (True, False)
                                        old_folder, nproc, old_nproc, nproc_sub, old_nproc_sub, flag_compl = Main.process_folder( filename, folder, old_folder,
                                                                                                                                  nproc, old_nproc,
                                                                                                                                  nproc_sub, old_nproc_sub,
                                                                                                                                  is_folder, platf_distrib )
                                        flag_glb.append(flag_compl)
                                        if platf_distrib == 'Linux' and flag_compl:
                                                float_proc = float('%d.%d' %(old_nproc, old_nproc_sub))
                                                comment_list = Utility.convert_ANI_to_X11( path_file, float_proc, folder,
                                                                                           width, height, color, comment_list )
                                                ## Get sub-process times.
                                                toc = perf_counter()
                                                times_sub.append(ceil(toc - tic))
                                                
                                else:
                                        pass

                                                

                                ## Get processing time (no folders).   
                                if times_sub == [] and flag_compl:
                                        toc = perf_counter()
                                        hours, minutes, seconds = Main.process_time( ceil(toc - tic) )
                                        print('---> Process #%d Complete in %d:%02d:%02d <---' %(nproc, hours, minutes, seconds))
                                        nproc += 1

                        ## Complete process (folders).                
                        if is_folder == (True, False) and (True in flag_glb):
                                X11Cursor.pack_X11( folder, '\n'.join(comment_list) )
                                Main.clean_all( remove_all = True )

                        ## Get processing time (folders).         
                        if times_sub != []:
                                hours, minutes, seconds = Main.process_time( sum(times_sub) )
                                print('---> Process #%d Complete in %d:%02d:%02d <---' %(old_nproc, hours, minutes, seconds))
                        ## Reset variables for successive loop step.
                        times_sub, comment_list, used_list, flag_glb = ([] for _ in range(4))
                                                
                print("\n---> Metamorphosis finished. <---")
                                        
##----------------------------------------------------------------------------------------------------------------------------------------------------------
if __name__ == 'Metamorphosis':
        Main.main( )                       
##----------------------------------------------------------------------------------------------------------------------------------------------------------        
