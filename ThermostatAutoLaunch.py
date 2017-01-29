#! /usr/bin/python
import os
from threading import Thread
os.system("cd")
os.system("cd Desktop")
os.system("sudo pkill -TERM python")
Thread(target=os.system, args=("sudo python /home/hvac/hvac_daemon.py",)).start()
Thread(target=os.system, args=("python /home/pi/Thermostat_master/daemon.py",)).start()
Thread(target=os.system, args=("cd /home/pi/Thermostat_master && python tgui.py",)).start()
raw_input("Wait")
