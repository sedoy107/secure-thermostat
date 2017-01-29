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


import cPickle as pic
import base64
import ics_types as T
import sshrpc
import sys
from common import *


def read_bs18d20(path):
    try:
        f = open(path, 'r')
        raw_data = f.read()
        f.close()
        return raw_data
    except IOError:
        sys.stderr.write("No such sensor file: %s" % path)
    except TypeError:
        sys.stderr.write("Bad string: %s" % path)


if __name__ == '__main__':
    sshrpc.init()
