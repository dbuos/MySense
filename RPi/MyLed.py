#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
#
# Copyright (C) 2017, Behoud de Parel, Teus Hagen, the Netherlands
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# $Id: MyLed.py,v 1.7 2017/08/24 18:33:32 teus Exp teus $

# Turn Grove led on, off or blink for an amount of time

""" Turn Grove led on, off or blink for an amount of time
    MyLed [--on|--off|--blink N,M,O|--led Dn|--button Dm]
    default: led off
    blink: N (dflt 1) secs on (dflt 1), M secs off, O period in minutes (dlft 30m)
    led: Grove socket nr (dflt D6)
    button: Grove socket nr (dflt: None) time button is pressed
    fan: switch fan on or off
    relay: fan relay Grove socket (dflt  D2)
"""
from __future__ import print_function

progname='$RCSfile: MyLed.py,v $'[10:-4]
__version__ = "0." + "$Revision: 1.7 $"[11:-2]
__license__ = 'GPLV4'
grovepi = None
import sys
try:
    import atexit
    import argparse
    grovepi = __import__('grovepi')
except ImportError:
    print("ERROR: One of the modules missing")
    exit(1)

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    exit(1)

SOCKET = 'D6'
LED = 'OFF'
BLINK=[]
BUTTON = 'D0'
RELAY = 'D2'
FAN = None
ON = 1
OFF = 0

def get_arguments():
    global LED, SOCKET, BLINK, BUTTON, FAN, RELAY
    parser = argparse.ArgumentParser(prog=progname, description='System led ON/OFF switch, and time button is pressed - Behoud de Parel', epilog="Copyright (c) Behoud de Parel\nAnyone may use it freely under the 'GNU GPL V4' license.")
    parser.add_argument("--light", help="Switch system led ON or OFF (dlft).", default=LED, choices=['ON','on','OFF','off'])
    parser.add_argument("--blink", help="Switch system led on/off for a period of time (e.g. 1,1,30 : 1 sec ON, optional 1 sec (dflt) OFF, optional max period 30 (dflt) minutes).",default='0,0,30')
    parser.add_argument("--led", help="Led socket number, e.g. D6 (dflt)", default=SOCKET,choices=['D3','D4','D5','D6','D7'])
    parser.add_argument("--button", help="Button socket number, e.g. D5 (dflt=None)", default=BUTTON,choices=['D3','D4','D5','D6','D7'])
    parser.add_argument("--relay", help="Relay socket number, e.g. D2 (dflt=%s)" % RELAY, default=RELAY,choices=['D2','D3','D4','D5','D6','D7'])
    parser.add_argument("--fan", help="Switch fan ON or OFF (dflt no fan)", default=None,choices=['ON','on','OFF','off'])
    args = parser.parse_args()
    SOCKET = int(args.led[1])
    LED = OFF
    if args.light.upper() == 'ON': LED = ON
    RELAY = int(args.relay[1])
    FAN = None
    if args.fan != None:
        if args.fan.upper() == 'ON': FAN = ON
        elif args.fan.upper() == 'OFF': FAN = OFF
    BLINK = args.blink.split(',')
    if len(BLINK) == 0:
        BLINK[0] = 0
    else:
        BLINK[0] = float(BLINK[0])
    if len(BLINK) < 1:
        BLINK[1] = 0
    else:
        BLINK[1] = float(BLINK[1])
    if len(BLINK) != 3:
        BLINK[2] = 30*60
    else:
        BLINK[2] = int(BLINK[2])*60
    if BLINK[0] != 0:
        LED = 1
    BUTTON = int(args.button[1])

def Led_Off():
    global grovepi
    grovepi.digitalWrite(SOCKET,OFF)
    exit(0)

from time import time
started = time()

PRESSED = OFF
def pressed():
    global PRESSED, started, LED, BLINK, grovepi, SOCKET
    if not BUTTON: return False
    while True:
        try:
            NEW = grovepi.digitalRead(BUTTON)
        except IOError:
            eprint("Button IOError")
        if PRESSED and (not NEW):
            print("%d" % int(time()-started))
            grovepi.digitalWrite(SOCKET,0)
            return True
        if (not PRESSED) and (not NEW):
            # wait for button press and try again
            sleep(5)
            continue
        if (not PRESSED) and NEW:
            PRESSED = NEW
            started = time()
            BLINK = [0.5,0.5,30]
            LED = ON
        elif (time() - started) > 20:
            BLINK = [1.5,0.3,30] ; LED = ON
        elif (time() - started) > 10:
            BLINK = [1,0.5,30] ; LED = ON
        elif (int(time()-started)) >= 5:
            BLINK = [2,1,30]
            LED = ON
        return False
   
get_arguments()

if FAN == None:
    grovepi.pinMode(SOCKET,'OUTPUT')
else:
    grovepi.pinMode(RELAY,'OUTPUT')

if BUTTON:
    import signal
    grovepi.pinMode(BUTTON,'INPUT')
    signal.signal(signal.SIGHUP,Led_Off)
    #signal.signal(signal.SIGKILL,Led_Off)
    atexit.register(Led_Off)

from time import sleep
sleep(0.5)

while True:
    try:
        if FAN != None:
            grovepi.digitalWrite(RELAY,FAN)
            break
        if pressed(): break
        if time() - started >= BLINK[2]:
            grovepi.digitalWrite(SOCKET,OFF)
            break
        grovepi.digitalWrite(SOCKET,LED)
        if not BLINK[0]:
            break
        sleep(BLINK[LED])
        LED = not LED
    except IOError:
        eprint("IO ERROR")
    except KeyboardInterrupt:
        grovepi.digitalWrite(SOCKET,OFF)
        exit(0)
    except:
        grovepi.digitalWrite(SOCKET,OFF)
        
