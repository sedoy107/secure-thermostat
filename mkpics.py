'''
	This file is part of Secure Thermostat project.
    Copyright (C) 2017  Sergey Gorbov

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''


from PIL import Image
from config import *

def make_pics(): 
    # 1. resizeing the background picture
    bg_in = Image.open(BG['PIC'])
    bg_out = bg_in.resize(BG['SIZE'], Image.ANTIALIAS)
    bg_out.save(BASE_PATH+BG['OUT'])

    # 2. Based on the resized picture create blended lower and upper panels
    lp_mask = Image.open(LP['PIC'])
    lp_in = bg_out.copy()
    lp_out = lp_in.crop((0, BG['SIZE'][1]-LP['SIZE'][1], BG['SIZE'][0], BG['SIZE'][1]))
    lp_out.paste(lp_mask, (0,0), lp_mask)
    lp_out.save(BASE_PATH+LP['OUT'])

    up_mask = Image.open(UP['PIC'])
    up_in = bg_out.copy()
    up_out = up_in.crop((0, 0, BG['SIZE'][0], UP['SIZE'][1]))
    up_out.paste(up_mask, (0,0), up_mask)
    up_out.save(BASE_PATH+UP['OUT'])
