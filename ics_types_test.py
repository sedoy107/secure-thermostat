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


import ics_types as T
from common import *

a1 = T.users_table(1,2,3)
a2 = T.sensors_table(1,2,3,4,5,6,7)
a4 = T.clients_history_table(1,2,3,4)
a6 = T.hvac_job_history_table(1,2,3,4,5,6,7,8,9,0)
a7 = T.hvac_jobs_table(1,2,3,4,5,timestamp(),timestamp(),8,9,0,1,2)
a8 = T.hvacs_table(1,2,3,4,5,6,7,8,9,0,1)
a9 = T.hvacs_history_table(1,2,3)
a10 = T.sensors_history_table(1,2,3,4,5)
a11 = T.current_clients_table(1,2,3,4)
a12 = T.current_hvacs_table(1,2,3,4,5,6,7,8,9)
a13 = T.current_sensors_table(1,2,3,4,5,6)

#~ a1.table = 1
#~ T.verify(a1)
