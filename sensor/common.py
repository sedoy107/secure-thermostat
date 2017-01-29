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


from datetime import time
import time
import hashlib
import cPickle as pic
import sys
import config

class ParameterError(Exception):
    PREFIX = "Parameter error"
    BAD_PARAMETER = 0xff
    NONE_VALUE = 0xfd
    KNOWN_ERRORS = {NONE_VALUE:'NONE_VALUE', BAD_PARAMETER:'BAD_PARAMETER'}
    """ COMMON PART FOR EXCEPTION CLASS 
    '   IF an exception needs to be declared, all you need to do is just define the 
    '   PREFIX, error constants and KNOWN_ERRORS which must contain the defined error codes.
    '   The part below can be copied and pasted to a new exception class
    """
    def __init__(self, msg, errno=None):
        self.msg = msg
        self.errno = errno
    def __str__(self):
        if self.errno == None:
            return repr("{0}: {1}".format(self.__class__.PREFIX, self.msg))
        elif self.errno in self.__class__.KNOWN_ERRORS:
            return repr("{0}(#{1}: {2}): {3}".format(self.__class__.PREFIX, self.errno, self.__class__.KNOWN_ERRORS[self.errno], self.msg))
        else:
            raise Exception("Bad error code {0}. KNOWN_ERRORS = {1}".format(self.errno, self.__class__.KNOWN_ERRORS))
    def getError(self):
        return self.errno
    @staticmethod
    def test(code=None):
        try:
            raise ICSTypeError('Hello world', code)
        except ICSTypeError as err:
            print err
            raise err

def pickle(v):
    try:
        obj = pic.dumps(v)
        return obj
    except pickle.PicklingError:
        sys.stderr.write("Error in cPickle: unserializabla object\n")
        return None
        
def unpic(v):
    try:
        obj = pic.loads(v)
        return obj
    except pic.UnpicklingError:
        sys.stderr.write("Error in cPickle: deserialization failed\n")
        return None
    except EOFError:
        sys.stderr.write("Warning: no output printed\n")
        return None
    except AttributeError:
        sys.stderr.write("Error in cPickle: deserializable object is not declared in the given scope\n")
        return None

def timestamp(fmt=config.DATE_FORMAT, t=None):
    if t == None:
        t = time.time()
    return time.strftime(fmt, time.localtime(t))

def sha512(data):
    hash_obj = hashlib.sha512(data)
    return hash_obj.hexdigest()

