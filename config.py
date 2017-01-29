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
# Configuration file
'''
Use search in this file and find all occurences of CHANGE. This will navigate you through 
the fields that must be specified individually.
'''

# Parameters for MySQL database
DB_NAME = "thermostat"
DB_HOST = "localhost" # This can remain localhost unless you plan to have db on remote location.
DB_USERNAME = ""  # CHANGE
DB_PASSWORD = ""  # CHANGE

# Parameters for HVAC 
HVAC_DEAMON_PORT = 6000        # 
HVAC_DEAMON_HOST = '127.0.0.1' # This must bind only localhost. Domain sockets also could be used.

# HVAC Parameters
TEMP_MIN = 60    # Min and Max possible temperatures
TEMP_MAX = 90    # for your thermostat
DELTA_MIN = 0.5     # 
DELTA_MAX = 2.0     #
DELTA = 1.5         # DELAT is within DELATA_MIN and DELTA_MAX
HVAC_H_TIMEOUT = 120   # HVAC TIMEOUT when a heater turns off
HVAC_C_TIMEOUT = 60    # same thing but for cooler.

# Authentication restrictions
DIGEST_LENGTH = 128
USERNAME_LENGTH = 100 # Must be <= then the max length value for username in the database
AUTH_ID_MIN = 0
AUTH_ID_MAX = 1 << 32

# Protocol constants
MODBUS = 'MODBUS'
SSHRPC = 'SSHRPC'
PROTOCOLS = [MODBUS, SSHRPC]

# Format for time
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
USAGE_TIME_FMT = '%Y-%m-%d'

# Job Types
CURRENT = 'CURRENT'
DELAYED = 'DELAYED'
JOB_TYPES = [CURRENT, DELAYED]

# Modbus parameters
MODBUS_PORT = 502
MODBUS_HOST = '192.168.1.59'

# Daemon settings
JOB_QUERY_PERIOD = 10
SENSOR_QUERY_PERIOD = 9 
CACHE_PERIOD = 5
CACHE_LIFETIME = 12

# User login timeout
SESSION_TIME = 300

# Back time for cleaning operation
BACK_TIME = 3

# Server account for clients
SRV_ACCOUNT = '' # CHANGE
SRV_PASSWORD = None # None must be set for those host that have exchanged the ssh keys
# This field must lead to user_interface.py file
SRV_USER_INTERFACE_PATH = '/home/pi/Thermostat_master/user_interface.py' # CHANGE

# GUI 
# Can be adjusted for each individual screen.
Q_INTERVAL = 10 	# Server quering period
MAIN_X = 800
MAIN_Y = 475
TEMP_FLOOR = 1000	# Temperature number flooring

# Job submission
SUBMISSION_DELAY = 5.0

# Background and panels
BACKGROUND_PICTURE_NAME = 'ny.jpg' # specify backgound picture name here
BASE_PATH = './assets/pics/'
HORIZONTAL_BACKGROUND = BASE_PATH + 'HorizontalBackground.jpg'
HORIZONTAL_LOWER_PANEL = BASE_PATH + 'HorizontalLowerPanel.jpg'
HORIZONTAL_UPPER_PANEL = BASE_PATH + 'HorizontalUpperPanel.jpg'

BG = {'PIC':BASE_PATH+BACKGROUND_PICTURE_NAME, 'SIZE':(MAIN_X, MAIN_Y), 'OUT':'HorizontalBackground.jpg'}
LP = {'PIC':BASE_PATH+'HorizontalLowerPanelTemplate.png', 'SIZE':(MAIN_X, 120), 'OUT':'HorizontalLowerPanel.jpg'}
UP = {'PIC':BASE_PATH+'HorizontalUpperPanelTemplate.png', 'SIZE':(MAIN_X, 58), 'OUT':'HorizontalUpperPanel.jpg'}

# Cursor
# This works only on gtk3 and higher. Can be left intact
IS_CURSOR_HIDDEN = True

# Credentials file
# If you do not want to type your creds everytime you start your thermostat then specify this field as a valid file name.
# If you do not want credentials saved in plain text on your local storage then make it equal '.', this way credential caching will fail
CRED_FILE = 'cred_file'
