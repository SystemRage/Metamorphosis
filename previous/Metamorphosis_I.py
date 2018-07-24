
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

__name__        = "Metamorphosis"
__version__     = "I (Egg)"
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
        
        def limit_loop( script ):
                """ Define all start index of loops ('repeat N'),
                    all stop index ('end repeat') and all number of repetitions ('N'). """
                ini = []
                fin = []
                rip = []
                for i, v in enumerate(script):
                        if v.startswith('repeat'):
                                ini.append(i)
                                a, b = re.split('\s', v)
                                rip.append(int(b))
                        elif v.startswith('end'):
                                fin.append(i)
                return ini, rip, fin

        def flatten_loop( thelist ):
                """ Transform a list of lists in a flat list. """
                for elem in thelist:
                        if hasattr(elem, '__iter__') and not isinstance(elem, (str, bytes)):
                                yield from Repeat.flatten_loop(elem)
                        else:
                                yield elem

        def expand_loop( script ):
                """ Expand not nested or nested loops or any combination of both. """
                start, nloop, stop = Repeat.limit_loop( script )
                
                while start != []:
                        ## Calculate distances between first stop index with all start index.
                        dist = [stop[0] - start[i] for i in range(len(start))]
                        ## Find index where there is min positive distance.
                        min_dist = min(i for i in dist if i > 0)
                        index_min_dist = dist.index(min_dist)
                        ## Create loop extension and calculate number elements to insert. 
                        piece = script[ start[index_min_dist] + 1 : stop[0] ] * nloop[index_min_dist]
                        n_adj = (stop[0] - (start[index_min_dist] + 1)) * nloop[index_min_dist]
                        ## Remove in the script the loop in exam and calculate number of elements erased.
                        script[ start[index_min_dist] : stop[0] + 1 ] = []
                        n_remov = stop[0] + 1 - start[index_min_dist]
                        ## Insert loop extension at right place and flatten.
                        script.insert(start[index_min_dist], piece)
                        script = list(Repeat.flatten_loop( script ))
 
                        shift = n_adj - n_remov
                        ## Shift all start index after the used one.
                        shifted_start = [ x + shift for x in start[index_min_dist + 1::] ]
                        start = start[0 : index_min_dist + 1] + shifted_start
                        ## Shift all stop index after the first.
                        shifted_stop = [ x + shift for x in stop[1::] ]
                        stop = stop[0 : 1] + shifted_stop
                        ## Update lists removing used elements.
                        start.pop(index_min_dist)
                        stop.pop(0)
                        nloop.pop(index_min_dist)

                return script
        

## ______________________________________
##| Other functions used for conversion  |------------------------------------------------------------------------------------------------------------------
##|______________________________________|
##        
class SupportFunc(object):
        
        def namecurs():
                """ Cursor names.
                    the list of output file names are based on http://fedoraproject.org/wiki/Artwork/EchoCursors/NamingSpec.
                    NameCursorFX:((NameCursorXP), (NameCursorWindows), (LinkforLinux), (NamesCursorLinux)) """
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
        
        
        def parameters( nproc, platf ):
                """ Define general parameters and directories. """
                global AUTO_CROP, TMP_DIR, OUTPUT_BASE_DIR, ORIGINAL_DIR, ICON_DIR, CFG_DIR, SCRIPT_LINE_PATTERN
                
                ## Remove transparent border.
                AUTO_CROP = True
                
                ## Directories clean.
                if nproc == 1:
                        try:
                                rmtree(TMP_DIR, onerror = SupportFunc.remove_readonly)
                        except:
                                pass
                        
                ## Create directories.
                OUTPUT_BASE_DIR = os.path.join(TMP_DIR, 'targets')
                ORIGINAL_DIR = os.path.join(TMP_DIR, 'originals')
                CFG_DIR = os.path.join(TMP_DIR, 'cfgs')
                ICON_DIR = os.path.join(TMP_DIR, 'icons')
                
                ## OUTPUT_DIR will be created later, because we need to retrieve the theme_name first.
                ## Create "conversion" directory and subdirectories "targets", "originals", "icons" (only when Windows), "cfgs".
                SupportFunc.try_mkdir(TMP_DIR)
                SupportFunc.try_mkdir(OUTPUT_BASE_DIR)
                SupportFunc.try_mkdir(ORIGINAL_DIR)
                SupportFunc.try_mkdir(CFG_DIR)
                ICON_DIR = None                
                SCRIPT_LINE_PATTERN = re.compile(r'(\d+)(?:-(\d+))?(?:,(\d+))?')
                                
        
        def try_mkdir( d ):
                """ Create job folders. """
                try:
                        os.makedirs(d)
                except OSError:
                        pass

        def remove_readonly( func, path, excinfo ):
                """ Remove read only permission. """
                os.chmod(path, S_IWRITE)
                func(path)
                
        def choice( message, list_of_choice ):
                """ Gets user-defined parameters. """
                while True:
                        varchoice = input('%s %s:\n' %(message, '['+ ' - '.join(list_of_choice) +']'))
                        if varchoice in list_of_choice:
                                break
                        else:
                                print ('??? Insert correctly...')
                return varchoice
                

        def ico_resize( image, maxsize, method = Image.ANTIALIAS ):
                """ im = ico_resize(im, (maxsizeX, maxsizeY), method = Image.BICUBIC)
                Resizes a PIL image to a maximum size specified while maintaining
                the aspect ratio. Similar to Image.thumbnail(), but allows
                usage of different resizing methods and does not modify the image in place;
                Then create an exact square image. """
                
                w, h = image.size
                imAspect = float(w)/float(h)
                outAspect = float(maxsize[0])/float(maxsize[1])
                if imAspect >= outAspect:
                        ## Set w to maxWidth.
                        ## Set h to (maxWidth / imAspect).
                        image = image.resize( (maxsize[0], int((float(maxsize[0])/imAspect) + 0.5)), method )
                else:
                        ## Set w to (maxHeight * imAspect).
                        ## Set h to maxHeight.
                        image = image.resize( (int((float(maxsize[1])*imAspect) + 0.5), maxsize[1]), method )
                        
                ## Create background transparent image.
                background = Image.new('RGBA', maxsize, (255, 255, 255, 0))
                background.paste( image, ((maxsize[0] - image.size[0]) // 2, (maxsize[1] - image.size[1]) // 2) )
                        
                return background
        

        def make_resize( w_res, h_res, img_list ):
                """ Apply resize with icon dimensions to image list and adjust hotspots. """
                global mouse_x, mouse_y, frame_count
                
                w_norm, h_norm = img_list[0].size
                scale_x = w_res / w_norm
                scale_y = h_res / h_norm
                
                for i in range(frame_count):
                        img_list[i] = SupportFunc.ico_resize(img_list[i], (w_res, h_res), method = Image.ANTIALIAS)
                        
                ## Scale hotspots.                                
                mouse_x = int(0.5 * ceil(2.0 * (mouse_x * scale_x)))
                mouse_y = int(0.5 * ceil(2.0 * (mouse_y * scale_y)))
                
                return img_list
        

        def single_imag( image_width, image_height, imgstrip ):
                """ Get images from strip image. """
                global frame_count
                
                frame_width = int(image_width / frame_count)
                frame_height = image_height
                                
                img_list = []
                for i in range(frame_count):
                        img_list.append(imgstrip.crop((frame_width * i, 0, frame_width * (i+1), image_height)))
                        
                return img_list


        def crop( img_list ):
                """ Crop border. """
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
                        for i in range(frame_count):
                                img_list[i] = img_list[i].crop(bbox) 
                        mouse_x -= bbox[0]
                        mouse_y -= bbox[1]
                        
                return img_list
        

        def script_parser( script_data, cfg, logger, platf, xsize ):
                """ Create the sequence script defined. """
                global SCRIPT_LINE_PATTERN, frame_interval, frame_count, mouse_x, mouse_y, image_index, cursor_status, ICON_DIR, ORIGINAL_DIR
                
                script_parsed = False
                script_flag = True
                try:
                        if script_data == None:
                                pass
                        else:
                                
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
                                                if platf == 'Linux':
                                                        for i in range(start_frame, end_frame + step, step):
                                                                cfg.write('%d %d %d %s/img%d-%d_%d.png %d\n' %(xsize, mouse_x, mouse_y, ORIGINAL_DIR,
                                                                                                               image_index, cursor_status, i-1, interval))
                                        else:
                                                script_flag = False
                                                break
                                                
                                script_parsed = script_flag
                except:
                        logger.write(' Script Error --> Cannot parse script line: %s\n' %x)
                        pass

                return script_parsed
        

        def animation_parser( cfg, logger, platf, xsize ):
                """ Create the sequence animation defined. """
                global animation_type, frame_interval, frame_count, mouse_x, mouse_y, image_index, cursor_status, ICON_DIR, ORIGINAL_DIR

                if animation_type == 0:         # ANIMATION_TYPE_NONE
                        if platf == 'Linux':
                                for i in range(frame_count):
                                        cfg.write('%d %d %d %s/img%d-%d_%d.png %d\n' %(xsize, mouse_x, mouse_y, ORIGINAL_DIR, image_index, cursor_status,
                                                                                       i, (frame_interval if (i < frame_count-1) else 1000000)))
                elif animation_type == 2:       # ANIMATION_TYPE_LOOP
                        if platf == 'Linux':
                                for i in range(frame_count):
                                        cfg.write('%d %d %d %s/img%d-%d_%d.png %d\n' %(xsize, mouse_x, mouse_y, ORIGINAL_DIR, image_index,
                                                                                       cursor_status, i, frame_interval))
                elif animation_type == 3:       # ANIMATION_TYPE_ALTERNATE
                        if platf == 'Linux':
                                for i in range(frame_count):
                                        cfg.write('%d %d %d %s/img%d-%d_%d.png %d\n' %(xsize, mouse_x, mouse_y, ORIGINAL_DIR, image_index,
                                                                                       cursor_status, i, frame_interval))
                                for i in range(frame_count - 2, 0, -1):
                                        cfg.write('%d %d %d %s/img%d-%d_%d.png %d\n' %(xsize, mouse_x, mouse_y, ORIGINAL_DIR, image_index,
                                                                                       cursor_status, i, frame_interval))            
                else:
                        logger.write(' Animation --> Unknown animation type: %d\n' %animation_type)
                        

## _________________________________
##| Cursor themes extraction data  |-----------------------------------------------------------------------------------------------------------------------
##|________________________________|
##
class Cursor(object):      
        
        def convert_FX( fileFX, N, w_res, h_res, platf ):
                """ Extract data from file theme CURSORFX """
                
                global TMP_DIR, OUTPUT_BASE_DIR, ORIGINAL_DIR, CFG_DIR, OUTPUT_DIR, OUTPUT_CURS_DIR
                global mouse_x, mouse_y, frame_count, animation_type, frame_interval, image_index, cursor_status, theme_name
                             
                ## Import directories.
                SupportFunc.parameters( N, platf )
                CURSOR_NAMEMAP = SupportFunc.namecurs()
                
                ## Open logging file.
                logger = open('%s/%s' %(TMP_DIR, 'logconv.txt'), 'a', encoding = 'utf-8')
               
                with open(fileFX, 'rb') as f:
                        data = f.read()

                ## Extract header data.
                logger.write('\n#################################################\n\n')
                version, header_size, data_size, theme_type = unpack_from('<4I', data, 0)
                info_size, = unpack_from('<I', data, header_size - 4)

                logger.write( 'Header Info:\n\n Version: %u\n Header Size: %u\n Data Size: %u\n Theme Type: %u\n Info size: %u\n\n'
                               %(version, header_size, data_size, theme_type, info_size) )
                
                ## Extract remaining data.
                data = decompress(data[header_size:])
                try:
                        assert len(data) == data_size
                except:
                        logger.write('Conversion Abort --> File %s Corrupted\n' %fileFX)
                                
                ## Get theme info.
                info = data[:info_size].decode('utf-16le').split('\0')[:-1]
                ## Fill with ' ' if theme info data missing (theme info is a list of 3 elements).
                while len(info) < 3:
                        info.append(' ')
                comment = ' - '.join(info)
                logger.write('Theme info: %s\n' %comment)
                                        
                ## Get the theme name.
                if info[0].strip() == 'Missing Data':
                        ## If theme name missing in data stream, get it from file name.
                        theme_name = fileFX.split(os.sep)[-1].split('.')[0]
                else:
                        theme_name = info[0].strip()
                theme_name = theme_name.replace(',','_').replace(' ','')

                ## Creation subdirectory under "targets".
                OUTPUT_DIR = OUTPUT_BASE_DIR + os.sep + theme_name
                SupportFunc.try_mkdir(OUTPUT_DIR)
                if platf == 'Linux':
                        OUTPUT_CURS_DIR = OUTPUT_DIR + os.sep + 'cursors'
                        SupportFunc.try_mkdir(OUTPUT_CURS_DIR)
                else:
                        OUTPUT_CURS_DIR = None
                logger.write('<------>< Image Extraction ><------>\n')
               
                ## Start processing image data.
                cur_pos = info_size
                while cur_pos < len(data):

                        # Extract image data.
                        pointer_type, size_of_header_without_script_1, size_of_header_and_image = unpack_from('<3I', data, cur_pos)

                        if pointer_type != 2:
                                logger.write('Cursor Skipped --> Found (%d), not a pointer image\n' %pointer_type)
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
                                                                                                            image_index, cursor_status, unknown_2, frame_count, image_width,
                                                                                                            image_height, frame_interval, unknown_3, animation_type,
                                                                                                            mouse_x, mouse_y, size_of_script))
                        
                        try:
                                assert size_of_header_without_script_1 == size_of_header_without_script_2
                                assert size_of_header_with_script == size_of_header_without_script_1 + size_of_script
                                assert size_of_header_and_image == size_of_header_with_script + size_of_image
                                assert size_of_image == image_width * image_height * 4
                        except:
                                logger.write(' Cursor skipped --> Image #%d Corrupted\n' %image_index )
                                cur_pos += size_of_header_and_image
                                continue
                                

                        ## Get strip image frames. (format: img0-1.png)
                        imgstrip = Image.frombytes('RGBA', (image_width, image_height), data[cur_pos + size_of_header_with_script : cur_pos + size_of_header_and_image],
                                                    'raw', 'BGRA', 0, -1)
                        imgstrip.save('%s/img%d-%d.png' %(ORIGINAL_DIR, image_index, cursor_status)) 

                        ## Get single images from strip frames.
                        img_list = SupportFunc.single_imag( image_width, image_height, imgstrip )
                                                        
                        ## Crop transparent border.
                        img_list = SupportFunc.crop( img_list )
                        
                        ## Resize.
                        img_list = SupportFunc.make_resize( w_res, h_res, img_list )
                        
                        ## Save images. (format: img0-1_0.png)
                        for i in range(frame_count):
                                img_list[i].save('%s/img%d-%d_%d.png' %(ORIGINAL_DIR, image_index, cursor_status, i))  
                                

                        ## ---> Parse script. <---
                        ## Create config file. ( format: numberFrames\n rateFrames\n hotspotx\n hotspoty\n scriptORanimationSequence\n )
                        cfg = open('%s/img%d-%d.cfg' %(CFG_DIR, image_index, cursor_status), 'w')

                        if size_of_script > 0:
                                script_data = data[cur_pos + size_of_header_without_script : cur_pos + size_of_header_with_script].decode('utf-16le')[:-1].replace(';','\n').split()
                                ## Write script into log file.
                                logger.write(' Script:\n %s\n' %('\n '.join(script_data)))
                                ## Eventually expand loops.
                                if 'end repeat' in script_data:
                                        script_data = Repeat.expand_loop( script_data )
                        elif size_of_script == 0:
                                script_data = None
                                        
                        script_parsed = SupportFunc.script_parser( script_data, cfg, logger, platf, w_res )
                        
                        if not script_parsed:
                                if size_of_script > 0:
                                        ## Script not correctly formatted.
                                        logger.write(' Script Error --> Fall back to default script animation for img%d-%d\n' %(image_index, cursor_status))
                                        cfg.seek(0)
                                elif size_of_script == 0:
                                        ## Script not present.
                                        logger.write(' Script not Existent --> Fall back to default script animation for img%d-%d\n' %(image_index, cursor_status))
                                        cfg.seek(0)
                                        
                                ## Not use a script but a default animation.
                                SupportFunc.animation_parser( cfg, logger, platf, w_res )
                                    
                        cfg.close()
                        ## Generate X11 cursor (for Linux user) from current image.
                        if platf == 'Linux':
                                X11.convert( CURSOR_NAMEMAP, logger )
                                
                        cur_pos += size_of_header_and_image
                        
                ## Package and remove old files.
                if platf == 'Linux':
                        X11.pack( theme_name, comment )
                        X11.remove()
                logger.close()
                
                

        def convert_XP( fileXP, N, w_res, h_res, platf ):
                """ Extract data from file theme CURXPTHEME"""
                
                global TMP_DIR, OUTPUT_BASE_DIR, ORIGINAL_DIR, CFG_DIR, OUTPUT_DIR, OUTPUT_CURS_DIR
                global mouse_x, mouse_y, frame_count, animation_type, frame_interval, image_index, cursor_status, theme_name
                             
                ## Import directories.
                SupportFunc.parameters( N, platf )
                CURSOR_NAMEMAP = SupportFunc.namecurs()

                ## Open logging file.
                logger = open('%s/%s' %(TMP_DIR, 'logconv.txt'), 'a', encoding = 'utf-8')
                logger.write('\n#################################################\n\n')
                
                ## Open Theme file.
                archive = ZipFile(fileXP, 'r')
                flag_scheme = False
                try:
                        scheme = archive.read('Scheme.ini')
                        scheme = scheme.decode('latin-1').replace(';','\r\n').split('\r\n')
                        ## Correction for multi return carriage.
                        scheme = [line for line in scheme if line != '']
                        
                        flag_scheme = True
                except:
                        logger.write('Conversion Abort --> Scheme.ini Not Found into %s\n' %fileXP)
                        pass
                        
                if flag_scheme:
                        ## Get description content.
                        descr_data = scheme[ scheme.index('[Description]') + 1 :: ]
                        ## Get theme name from file name.
                        theme_name = fileXP.split(os.sep)[-1].split('.')[0]
                        theme_name = theme_name.replace(',','_').replace(' ','')
                        logger.write('Theme Name: %s\n' %theme_name)
                        ## Get comments from description.
                        goodlines = [line.strip() for line in descr_data if line.strip() != '']
                        if goodlines == []:
                                comment = ''
                        else:
                                comment = ' - '.join(goodlines)
                                logger.write('Theme Info: %s\n' %comment) 
                                        
                        ## Creation subdirectory under "targets".
                        OUTPUT_DIR = OUTPUT_BASE_DIR + os.sep + theme_name
                        SupportFunc.try_mkdir(OUTPUT_DIR)
                        if platf == 'Linux':
                                OUTPUT_CURS_DIR = OUTPUT_DIR + os.sep + 'cursors'
                                SupportFunc.try_mkdir(OUTPUT_CURS_DIR)
                        else:
                                OUTPUT_CURS_DIR = None
                                
                        logger.write('<------>< Image Extraction ><------>\n')
                                      
                        ## Get data index in 'Scheme.ini'.
                        indx = [ scheme.index(line) for line in scheme if line.startswith('[') and line != '[General]' ]

                        ## Do processing.
                        for j in range(len(indx) - 1):
                                
                                if not scheme[indx[j]].endswith('_Script]'):
                                        ## Get data image.
                                        imag_data = scheme[indx[j] + 1 : indx[j + 1]]
                                        name = scheme[indx[j]].replace('[','').replace(']','')
                                        if name.endswith('_Down'):
                                                name = name.replace('_Down','')
                                        
                                        image_index = [k for k, v in CURSOR_NAMEMAP.items() if name == v[0]][0]
                                       
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
                                                        logger.write(' Cursor #%d Skipped --> Image Missing\n' %image_index)
                                                        continue
                                        elif cursor_status == 0:
                                                logger.write(' Cursor #%d Skipped --> Image Error\n' %image_index)
                                                continue
                                                                  
                                        ## Save image strip.
                                        imgstrip.save('%s/img%d-%d.png' %(ORIGINAL_DIR, image_index, cursor_status)) 
                                        
                                        ## Get single images from strip frames.
                                        image_width, image_height = imgstrip.size
                                        img_list = SupportFunc.single_imag( image_width, image_height, imgstrip )

                                        ## Crop transparent border.
                                        img_list = SupportFunc.crop( img_list )
                                        
                                        ## Resize.
                                        img_list = SupportFunc.make_resize( w_res, h_res, img_list )
                                        
                                        ## Save images.
                                        for i in range(frame_count):
                                                img_list[i].save('%s/img%d-%d_%d.png' %(ORIGINAL_DIR, image_index, cursor_status, i))

                                        ## Create config file with a default animation.
                                        if script_status == 0:
                                                cfg = open('%s/img%d-%d.cfg' %(CFG_DIR, image_index, cursor_status), 'w')
                                                logger.write(' Script not Existent --> Fall back to default script animation for img%d-%d\n' %(image_index, cursor_status))
                                                SupportFunc.animation_parser( cfg, logger, platf, w_res )
                                                cfg.close()
                                                ## Generate X11 cursor (for Linux user) from current image.
                                                if platf == 'Linux':
                                                        X11.convert( CURSOR_NAMEMAP, logger )                                                                                            
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
                                                        script_data = Repeat.expand_loop( script_data )
                                                
                                                script_parsed = SupportFunc.script_parser( script_data, cfg, logger, platf, w_res )

                                                if not script_parsed: 
                                                        ## Script not correctly formatted.
                                                        logger.write(' Script Error --> Fall back to default script animation for img%d-%d\n' %(image_index, cursor_status))
                                                        cfg.seek(0)
                                                                
                                                        ## Not a script but use a default animation.
                                                        SupportFunc.animation_parser( cfg, logger, platf, w_res )
                                                                
                                                cfg.close()
                                                ## Generate X11 cursor (for Linux user) from current image.
                                                if platf == 'Linux':
                                                        X11.convert( CURSOR_NAMEMAP, logger )
                                                        
                ## Package and remove old files.
                if platf == 'Linux':
                        X11.pack( theme_name, comment )
                        X11.remove()
                logger.close()
                
                
                
## _________________
##| X11 Conversion |---------------------------------------------------------------------------------------------------------------------------------------
##|________________| 
##
class X11(object):

        def convert( CURSOR_NAMEMAP, logger ):
                """ Create X11 cursors. """
                global image_index, cursor_status, CFG_DIR, OUTPUT_DIR, OUTPUT_CURS_DIR
                ## Get elements from namemap.
                (outfilename, links) = CURSOR_NAMEMAP[image_index][2:4]
                ## Pressed cursors management.
                ## for CursorFX --> CURSOR_STATUS_NORMAL = 1, CURSOR_STATUS_PRESSED = 2
                if cursor_status == 2: 
                        outfilename += '_pressed'
                        links = []
                ## xcursorgen job.
                try:
                        os.system('xcursorgen "%s/img%d-%d.cfg" "%s/%s"' %(CFG_DIR, image_index, cursor_status, OUTPUT_CURS_DIR, outfilename))
                except:
                        logger.write(' Cursor #%d Skipped --> xcursorgen not installed\n' %image_index)
                                     
                for link in links:
                        try:
                            os.symlink(outfilename, '%s/%s' %(OUTPUT_CURS_DIR, link))
                        except:
                            logger.write(' Failed in creating symlink: %s -> %s\n' %(outfilename, link))
                logger.write('\n X11 cursor %s and Symlinks --> Done !!\n' %outfilename)
                            

        def pack( themename, desc ):
                """ Package X11 theme. """
                global OUTPUT_DIR, OUTPUT_BASE_DIR, TMP_DIR
                ## Create index.theme file.
                themefilestr = "[Icon Theme]\n" +\
                                "Name=%s\n" %themename +\
                                "Comment=%s -*Converted by Metamorphosis, Copyright 2018\n" %desc +\
                                "Example=default\n" +\
                                "Inherits=core"
                
                with open('%s/index.theme' %OUTPUT_DIR, 'w') as ft:
                        ft.write(themefilestr)
                with open('%s/cursor.theme' %OUTPUT_DIR, 'w') as ft:
                        ft.write(themefilestr)
                        
                ## Create archive.
                os.system('tar -a -cf "%s/%s.tar.gz" -C "%s" "%s"' %(TMP_DIR, themename, OUTPUT_BASE_DIR, themename))
                

        def remove():
                """ Delete used files after processing. """
                global OUTPUT_BASE_DIR, CFG_DIR, ORIGINAL_DIR
                rmtree(ORIGINAL_DIR, onerror = SupportFunc.remove_readonly)
                rmtree(CFG_DIR, onerror = SupportFunc.remove_readonly)
                rmtree(OUTPUT_BASE_DIR, onerror = SupportFunc.remove_readonly)                        

## _______
##| Main  |------------------------------------------------------------------------------------------------------------------------------------------------
##|_______|
##
if __name__ == 'Metamorphosis':

        global TMP_DIR, ROOT_DIR

        ## Get platform.
        platf = SupportFunc.choice( 'Select OS of cursors:', ['Linux'] )

        ## Path root.
        ## Linux -->   /home/User/Metamorphosis
        ROOT_DIR = os.path.normpath(os.path.expanduser('~'+ os.sep + 'Metamorphosis'))
        if ROOT_DIR.startswith('\\'):
                ROOT_DIR = 'C:' + ROOT_DIR
               
        ## Path of jobs directory.
        TMP_DIR = os.path.join(ROOT_DIR, 'conversion')
        ## Path of folder with files to convert.
        FILE_DIR = os.path.join(ROOT_DIR, 'curs2conv')
        
        ## Define width and heigth.
        width = height = 32
        
        ## Do conversion.
        nproc = 1
        for file in os.listdir(FILE_DIR):
                path_file = FILE_DIR + os.sep + file
                
                print('---> Start Processing #%d <---' %nproc)
                tic = perf_counter()

                if path_file.lower().endswith('.cursorfx'):
                        Cursor.convert_FX( path_file, nproc, width, height, platf )
                elif path_file.lower().endswith('.curxptheme'):
                        Cursor.convert_XP( path_file, nproc, width, height, platf )

                ## Get processing time.
                toc = perf_counter()
                minutes, seconds = divmod(ceil(toc - tic), 60)
                hours, minutes = divmod(minutes, 60)
                
                print('---> Processing #%d Complete in %d:%02d:%02d <---\n' %(nproc, hours, minutes, seconds))
                nproc += 1
                
##---------------------------------------------------------------------------------------------------------------------------------------------------------        
