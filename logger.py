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


import logging

def create_log(Name="unnamed_log", File=None, Level=1):
    #formatter = logging.Formatter(fmt='%(asctime)s - %(lineno)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter(fmt='%(lineno)s - %(levelname)s - %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger = logging.getLogger(Name)
    logger.setLevel(Level)
    logger.addHandler(handler)
    if File:
        #open(File, 'w').close()
        fh = logging.FileHandler(File)
        fh.level = Level
        fh.formatter = formatter
        logger.addHandler(fh)
    
    return logger

def add_file(log, File, Level=1):
    logger = logging.getLogger(log)
    open(File, 'w').close()
    fh = logging.FileHandler(File)
    fh.level = Level
    logger.addHandler(fh)
