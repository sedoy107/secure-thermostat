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


from datetime import datetime
import random
from common import *
import config


'''
' This file defines tables used inside a database as structs
' While you convert database tables into python classes:
'   1. Class naming convention: <tablename>_table
'   2. Preserve the names of the original fields
'''

# Table name constants
T_USERS = 'users'
T_SENSORS = 'sensors'
T_METADATA = 'metadata'
T_clients_history = 'clients_history'
T_LOADED_MODULES = 'loaded_modules'
T_HVAC_JOB_HIS = 'hvac_job_history'
T_HVAC_JOBS = 'hvac_jobs'
T_HVACS = 'hvacs'
T_SENSORS_HISTORY = 'sensors_history'
T_HVACS_HISTORY = 'hvacs_history'
T_CURR_CLIENTS = 'current_clients'
T_CURR_SENSORS = 'current_sensors'
T_CURR_HVACS = 'current_hvacs'

ICS_TYPES = [T_USERS, T_SENSORS, T_METADATA, T_clients_history, T_LOADED_MODULES, T_HVAC_JOB_HIS, T_HVAC_JOBS, T_HVACS,
             T_SENSORS_HISTORY, T_HVACS_HISTORY, T_CURR_CLIENTS, T_CURR_SENSORS, T_CURR_HVACS]


class ICSTypeError(Exception):
    PREFIX = 'ICS type error'
    INVALID_TABLE = 0xff
    INVALID_KEY = 0xfe
    ATTRIBUTE_MISSING = 0xfd
    KNOWN_ERRORS = {INVALID_TABLE: 'INVALID_TABLE', INVALID_KEY: 'INVALID_KEY', ATTRIBUTE_MISSING: 'ATTRIBUTE_MISSING'}
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
            return repr(
                "{0}(#{1}: {2}): {3}".format(self.__class__.PREFIX, self.errno, self.__class__.KNOWN_ERRORS[self.errno],
                                             self.msg))
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


class users_table:
    TABLE = T_USERS
    KEY = 'username'

    def __init__(self, username, pass_hash, timestamp, salt=str(random.randint(1 << 32,1 << 48))):
        self.table = self.__class__.TABLE
        self.key = self.__class__.KEY
        self.salt = salt
        self.username = username
        self.pass_hash = sha512(self.username + self.salt + pass_hash)
        self.timestamp = timestamp
        verify(self)


class sensors_table:
    TABLE = T_SENSORS
    KEY = 'sensor_id'

    def __init__(self, stype, host, port, username, password, path, protocol):
        self.table = self.__class__.TABLE
        self.key = self.__class__.KEY
        self.sensor_id = "{0}:{1}:{2}".format(host, port, path)
        self.stype = stype
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.path = path
        self.protocol = protocol
        verify(self)


class clients_history_table:
    TABLE = T_clients_history
    KEY = 'entry_id'

    def __init__(self, entry_id, username, timestamp, session_end_date):
        self.table = self.__class__.TABLE
        self.key = self.__class__.KEY
        self.entry_id = entry_id
        self.username = username
        self.timestamp = timestamp
        self.session_end_date = session_end_date
        verify(self)



class hvac_job_history_table:
    TABLE = T_HVAC_JOB_HIS
    KEY = 'job_id'

    def __init__(self, job_id, job_type, publisher, start_time, end_time, period, hvac_fan, hvac_mode, hvac_temp, hvac_delta):
        self.table = self.__class__.TABLE
        self.key = self.__class__.KEY
        self.job_id = job_id
        self.job_type = job_type
        self.publisher = publisher
        self.start_time = start_time
        self.end_time = end_time
        self.period = period
        self.hvac_fan = hvac_fan
        self.hvac_mode = hvac_mode
        self.hvac_temp = hvac_temp
        self.hvac_delta = hvac_delta
        verify(self)


class hvac_jobs_table:
    TABLE = T_HVAC_JOBS
    KEY = 'job_id'

    def __init__(self, job_id, job_type, auth_id, publisher, start_time, timestamp, period, hvac_id, hvac_fan, hvac_mode, hvac_temp, hvac_delta):
        self.table = self.__class__.TABLE
        self.key = self.__class__.KEY
        self.job_id = job_id
        self.job_type = job_type
        self.auth_id = auth_id
        self.publisher = publisher
        self.start_time = start_time
        self.timestamp = timestamp
        self.period = period
        self.hvac_id = hvac_id
        self.hvac_fan = hvac_fan
        self.hvac_mode = hvac_mode
        self.hvac_temp = hvac_temp
        self.hvac_delta = hvac_delta
        verify(self)


class hvacs_table:
    TABLE = T_HVACS
    KEY = 'hvac_id'

    def __init__(self, host, port, username, password, path, protocol, cool_wattage, heat_wattage, cool_kwph, heat_kwph, cool_usage, heat_usage, description):
        self.table = self.__class__.TABLE
        self.key = self.__class__.KEY
        self.hvac_id = "{0}:{1}".format(host, port)
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.path = path
        self.protocol = protocol
        self.cool_wattage = cool_wattage
        self.heat_wattage = heat_wattage
        self.cool_kwph = cool_kwph
        self.heat_kwph = heat_kwph
        self.cool_usage = cool_usage
        self.heat_usage = heat_usage
        self.description = description
        verify(self)


class sensors_history_table:
    TABLE = T_SENSORS_HISTORY
    KEY = 'entry_id'

    def __init__(self, entry_id, sensor, timestamp):
        self.table = self.__class__.TABLE
        self.key = self.__class__.KEY
        self.entry_id = entry_id
        self.sensor = sensor
        self.timestamp = timestamp
        verify(self)


class hvacs_history_table:
    TABLE = T_HVACS_HISTORY
    KEY = 'entry_id'

    def __init__(self, entry_id, hvac, timestamp):
        self.table = self.__class__.TABLE
        self.key = self.__class__.KEY
        self.entry_id = entry_id
        self.hvac = hvac
        self.timestamp = timestamp
        verify(self)


class current_clients_table:
    TABLE = T_CURR_CLIENTS
    KEY = 'auth_id'

    def __init__(self, auth_id, username, activity_tstamp, login_tstamp):
        self.table = self.__class__.TABLE
        self.key = self.__class__.KEY
        self.auth_id = auth_id
        self.username = username
        self.activity_tstamp = activity_tstamp
        self.login_tstamp = login_tstamp
        verify(self)


class current_sensors_table:
    TABLE = T_CURR_SENSORS
    KEY = 'sensor_id'

    def __init__(self, sensor_id, status, priority, timestamp, start_time, raw_data):
        self.table = self.__class__.TABLE
        self.key = self.__class__.KEY
        self.sensor_id = sensor_id
        self.status = status
        self.priority = priority
        self.timestamp = timestamp
        self.start_time = start_time
        self.raw_data = raw_data
        verify(self)


class current_hvacs_table:
    TABLE = T_CURR_HVACS
    KEY = 'hvac_id'

    def __init__(self, host, port, timestamp, start_time, sensor_id, fan, heat, cool, delta):
        self.table = self.__class__.TABLE
        self.key = self.__class__.KEY
        self.hvac_id = "{0}:{1}".format(host, port)
        self.host = host
        self.port = port
        self.timestamp = timestamp
        self.start_time = start_time
        self.sensor_id = sensor_id
        self.fan = fan
        self.heat = heat
        self.cool = cool
        self.delta = delta
        self.h_timeout_key = 0
        self.c_timeout_key = 0
        verify(self)


# Type verification function
def verify(obj):
    if not hasattr(obj, 'table'):
        raise ICSTypeError('attribute <table> not found', ICSTypeError.ATTRIBUTE_MISSING)
    if not hasattr(obj, 'key'):
        raise ICSTypeError('attribute <key> not found', ICSTypeError.ATTRIBUTE_MISSING)
    if not obj.table in ICS_TYPES:
        raise ICSTypeError(
            'attribute <table> is not in the list of allowed ics types: {0}. ICS_TYPES: {1}'.format(obj.table,
                                                                                                    ICS_TYPES),
            ICSTypeError.INVALID_TABLE)
    if not obj.table == obj.__class__.TABLE:
        raise ICSTypeError(
            'attribute <table> does not match with the static attribyte TABLE: {0} != {1}'.format(obj.table,
                                                                                                  obj.__class__.TABLE),
            ICSTypeError.INVALID_TABLE)
    if not obj.key == obj.__class__.KEY:
        raise ICSTypeError('attribute <key> does not match with the static attribyte KEY: {0} != {1}'.format(obj.table,
                                                                                                             obj.__class__.TABLE),
                           ICSTypeError.INVALID_TABLE)
    return True


# get a list of attributes (key,value) of an object
def toString(obj):
    attr = vars(obj).items()
    # print attr
    m = '\n'
    for i in range(0, len(attr)):
        try:
            o = unpic(attr[i][1]) 
        except TypeError:
            o = None
        except ValueError:
            o = None
        if o == None:
            m += str(attr[i][0]) + " = " + str(attr[i][1]) + '\n'
        else:
            m += str(attr[i][0]) + " = " + str(o) + '\n'
    return m
