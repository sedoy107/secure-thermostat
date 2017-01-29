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
import config
from common import *
from scheduler import Scheduler
import atomic

class UIError(Exception):
    PREFIX = "User interface error"
    SSH_SESSION_MISSING = 0xff
    SSH_SESSION_ERROR = 0xfe
    SYSTEM_NOT_CONNECTED = 0xfd
    REMOTE_EXCEPTION = 0xfc
    CREDENTIALS_ERROR = 0xfb
    KNOWN_ERRORS = {SSH_SESSION_MISSING:'SSH_SESSION_MISSING', SSH_SESSION_ERROR:'SSH_SESSION_ERROR', SYSTEM_NOT_CONNECTED:'SYSTEM_NOT_CONNECTED', REMOTE_EXCEPTION:'REMOTE_EXCEPTION',
                    CREDENTIALS_ERROR:'CREDENTIALS_ERROR'}
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

class ThermostatInterface:
    def __init__(self):
        self.auth_id = None
        self.username = None
        self.pass_hash = None
        
        self.sysint = None
        
        self.t_indicator = config.TEMP_MIN
        self.t_field = config.TEMP_MIN
        
        self.hvacs = {}
        self.sensors = {}
        
        self.cur_hvacs = {}
        self.cur_sensors = {}
        
        self.hist_hvacs = {}
        self.hist_sensors = {}
        
        # "Now monitoring" HVAC_ID
        self.nm_hvac = None
        self.jobs = {}
        
        self.job = atomic.AtomicUnit(None)
        
        self.status_fan = 0
        self.status_cool = 0
        self.status_heat = 0
        self.status_system = 0
        self.status_hvac = 0
        self.status_sensor = 0
    # Connects to the remote system and sends the EVT_SYSTEM_CONNECTED event to the GUI
    def connect(self, host, port, username, pass_hash):
        if self.sysint == None:
            self.sysint = SystemInterface(host, port)
        self.sysint.connect(host, port)
        self.username = username
        self.pass_hash = pass_hash
        try:
            self.auth_id = self.sysint.execute('user_interface.CLIENT.login', self.auth_id, self.username, self.pass_hash)
        except sshrpc.SSHRPCError as err:
            print err
            if err.getError() == sshrpc.SSHRPCError.REMOTE_EXCEPTION:
                self.disconnect()
                raise UIError("Remote exception occured, ssh session terminated", UIError.SSH_SESSION_ERROR)
            else:
                raise UIError("Problem with ssh session occured", UIError.SSH_SESSION_ERROR)
    # Disconects the remocte system and triggers the EVT_SYSTEM_DISCONNECTED to the GUI
    def disconnect(self):
        self.sysint.disconnect()
        self.sysint = None
        self.auth_id = None
        self.username = None
        self.pass_hash = None
    # This method reads all the essential data from the system server
    def query_essentials(self):
        if self.sysint is None:
            raise UIError("System must be connected first", UIError.SYSTEM_NOT_CONNECTED)
        try:
            self.jobs, self.hvacs, self.sensors, self.cur_hvacs, self.cur_sensors, self.hist_hvacs, self.hist_sensors = self.sysint.execute('user_interface.CLIENT.get_essentials', self.auth_id, self.username, self.pass_hash)
        except sshrpc.SSHRPCError as err:
            if err.getError() == sshrpc.SSHRPCError.REMOTE_EXCEPTION:
                self.disconnect()
                raise UIError("Remote exception occured, ssh session terminated", UIError.SSH_SESSION_ERROR)
            else:
                raise UIError("Problem with ssh session occured", UIError.SSH_SESSION_ERROR)
    def SyncJob(self):
        # Looping through jobs
        for k,v in self.jobs.iteritems():
            # Finding the CURRENT job for the right HVAC
            if v.job_type == config.CURRENT and str(v.hvac_id) == str(self.nm_hvac.hvac_id):
                self.job.set(v)
                return v
    

class SystemInterface:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        
        self.remote_session = None
    # Creates an sshrpc session
    def connect(self, host, port):
        self.remote_session = sshrpc.sshrpc(host, port, config.SRV_ACCOUNT, config.SRV_PASSWORD)
    def execute(self, function, *params):
        if self.remote_session == None:
            raise UIError("Remote ssh session must be created first", UIError.SSH_SESSION_MISSING)
        try:
            obj = self.remote_session.execute("python {0}".format(config.SRV_USER_INTERFACE_PATH), function, *params)
            return obj
        except sshrpc.SSHRPCError as err:
            if err.getError() == sshrpc.SSHRPCError.REMOTE_EXCEPTION:
                raise UIError(err.msg, UIError.REMOTE_EXCEPTION)
            else:
                raise err
    # Closes the sshrpc session
    def disconnect(self):
        self.remote_session.close()
    

class HvacInterface:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.hvac_id = None
        self.sensor = {}
        
        self.heat = 0
        self.fan = 0
        self.cool = 0

class SensorInterface:
    def __init__(self, host, port, path):
        self.host = host
        self.port = port
        self.path = path
        self.sensor_id = None
        
        self.temp = 0
