# PyCom Micro Python / Python 3
# Copyright 2018, Teus Hagen, ver. Behoud de Parel, GPLV4
# some code comes from https://github.com/TelenorStartIoT/lorawan-weather-station
# $Id: MySense.py,v 5.5 2019/04/27 12:47:52 teus Exp teus $
#
__version__ = "0." + "$Revision: 5.5 $"[11:-2]
__license__ = 'GPLV4'

from time import sleep_ms, time
from machine import Pin # user button/led/accu
from machine import I2C
import struct
from micropython import const
from led import LED
import _thread
# _thread.stack_size(6144)
NoThreading = False
import os
PyCom = 'PyCom %s' % os.uname()[1]
del os
# Turn off hearbeat LED
import pycom
pycom.heartbeat(False)
del pycom

# enabled devices
# devices:
Display = { 'use': None, 'enabled': False, 'fd': None}
Meteo   = { 'use': None, 'enabled': False, 'fd': None}
Dust    = { 'use': None, 'enabled': False, 'fd': None}
Gps     = { 'use': None, 'enabled': False, 'fd': None}
Network = { 'use': None, 'enabled': False, 'fd': None}
Accu    = { 'use': None, 'enabled': False, 'fd': None} # ADC pin P17 voltage
import whichUART
UARTobj = None  # result from whichUART identification
uarts = [None,'dust','gps']
import whichI2C
I2Cobj  = None  # result from whichI2C identification

LAT = const(0)
LON = const(1)
ALT = const(2)
# LoRa ports
# data port 2 old style and ug/m3, 4 new style grain, pm4/5 choice etc
Dprt = (2,4)    # data ports
Iprt = const(3) # info port, meta data

# oled is multithreaded
STOP = False
STOPPED = False
HALT = False  # stop by remote control

# Config interval items
try: from Config import interval
except:
  interval = { 'sample': 60,    # dust sample in secs
             'interval': 5,     # sample interval in minutes
             'gps':      3*60,  # location updates in minutes
             'info':     24*60, # send kit info in minutes
             'gps_next': 0,     # next gps update 0 OFF, 0.1 on
             'info_next': 0,    # next info send time, 0 is OFF
  }
finally:
  for item in ['interval','gps','info']: interval[item] *= 60
  interval['interval'] -= interval['sample']
  if interval['interval'] <= 0: interval['interval'] = 0.1

# device power management dflt: do not unless pwr pins defined
# power mgt of ttl/uarts OFF/on, i2c OFF/on and deep sleep minutes, 0 off
# display: None (always on), False: always off, True on and off during sleep
# To Do: sleep pin P18 use deep sleep or delete config json file
try: from Config import Power
except: Power = { 'ttl': False, 'i2c': False, 'sleep': 0, 'display': None }
finally: Power['sleep'] *= 60

# calibrate dict with lists for sensors { 'temperature': [0,1], ...}
try: from Config import calibrate
except: calibrate = {}      # sensor calibration Tayler array

try: from Config import thisGPS # predefined GPS coord
# location
except: thisGPS = [0.0,0.0,0.0] # completed by GPS
finally:
  lastGPS = thisGPS[0:]
  if interval['gps_next']: interval['gps_next'] = 0.1

# stop processing press user button TO DO
# button = Pin('P11',mode=Pin.IN, pull=Pin.PULL_UP)
# #led = Pin('P9',mode=Pin.OUT)
# #led.toggle()
#
# def pressed(what):
#   global STOP, LED
#   STOP = True
#   print("Pressed %s" % what)
#   LED.blink(5,0.1,0xff0000,False)
#
# button.callback(Pin.IRQ_FALLING|Pin.IRQ_HIGH_LEVEL,handler=pressed,arg='STOP')

# oled display
def oledShow():
  global Display, I2Cobj
  if not Display['fd']: return
  if not Display['use'] or not Display['enabled']: return
  for cnt in range(0,4):
    try:
      Display['fd'].show()
      break
    except OSError as e: # one re-show helps
      if cnt: print("show err %d: " % cnt,e)
      sleep_ms(500)

nl = 16 # line height
LF = const(13)
# text display, width = 128; height = 64  # display sizes
def display(txt,xy=(0,None),clear=False, prt=True):
  global Display, nl
  if Display['use'] == None: initDisplay()
  if Display['enabled'] and Display['use'] and Display['fd']:
    offset = 0
    if xy[1] == None: y = nl
    elif xy[1] < 0:
      if -xy[1] < LF:
        offset = xy[1]
        y = nl - LF
    else: y = xy[1]
    x = 0 if ((xy[0] == None) or (xy[0] < 0)) else xy[0]
    if clear:
      Display['fd'].fill(0)
    if y > 56:
      nl =  y = 16
    if (not offset) and (not clear):
      rectangle(x,y,128,LF,0)
    Display['fd'].text(txt,x,y+offset)
    oledShow()
    if y == 0: nl = 16
    elif not offset: nl = y + LF
    if nl >= (64-13): nl = 16
  if prt: print(txt)

def rectangle(x,y,w,h,col=1):
  global Display
  if not Display['use'] or not Display['enabled']: return
  dsp = Display['fd']
  if not dsp: return
  ex = int(x+w); ey = int(y+h)
  if ex > 128: ex = 128
  if ey > 64: ey = 64
  for xi in range(int(x),ex):
    for yi in range(int(y),ey):
      dsp.pixel(xi,yi,col)

def ProgressBar(x,y,width,height,secs,blink=0,slp=1):
  global LED, STOP
  if x+width >= 128: width = 128-x
  if y+height >= 64: height = 64-y
  rectangle(x,y,width,height)
  if (height > 4) and (width > 4):
    rectangle(x+1,y+1,width-2,height-2,0)
    x += 2; width -= 4;
    y += 2; height -= 4
  elif width > 4:
    rectangle(x+1,y,width-2,height,0)
    x += 2; width -= 4;
  else:
    rectangle(x,y,width,height,0)
  step = width/(secs/slp); xe = x+width; myslp = slp
  if blink: myslp -= (0.1+0.1)
  for sec in range(int(secs/slp+0.5)):
    if STOP:
      return False
    if blink:
      LED.blink(1,0.1,blink,False)
    sleep_ms(int(myslp*1000))
    if x > xe: continue
    rectangle(x,y,step,height)
    oledShow()
    x += step
  return True

def showSleep(secs=60,text=None,inThread=False):
  global nl, STOP, STOPPED
  global Display
  ye = y = nl
  if text:
    display(text)
    ye += LF
  if Display['fd'] and Display['enabled'] and Display['use']:
    ProgressBar(0,ye-3,128,LF-3,secs,0x004400)
    nl = y
    rectangle(0,y,128,ye-y+LF,0)
    oledShow()
  else: sleep_ms(int(secs*1000))
  if inThread:
    STOP = False
    STOPPED = True
    _thread.exit()
  return True

def SleepThread(secs=60, text=None):
  global STOP, NoThreading
  if NoThreading:
    display('waiting ...')
    raise OSError
  STOP = False; STOPPED = False
  try:
    _thread.start_new_thread(showSleep,(secs,text,True))
  except Exception as e:
    print("threading failed: %s" % e)
    STOPPED=True
    NoThreading = True
  sleep_ms(1000)

# initilize I2C, return to I2C class objects
def getI2C(atype=None,debug=False):
  global I2Cobj
  try:
    if not I2Cobj:
      I2Cobj = whichI2C.identifyI2C(identify=True,debug=debug)
    if atype in ['meteo','display']:
      if not atype in I2Cobj.devs.keys():
        if not I2Cobj.i2cType(atype): return False
      elif not I2Cobj.i2cType(atype)['use']: return False
  except: raise OSError("search I2C devices failed")
  return True

# initilize UARTs, return to UART class objects
def getUART(atype=None,debug=False):
  global UARTobj
  if not UARTobj:
    UARTobj = whichUART.identifyUART(identify=True,debug=debug)
  if atype in ['gps','dust']:
    if not atype in UARTobj.devs.keys():
      if not UARTobj.uartType(atype): return False
  return True

# check/set power on device
def PinPower(atype=None,on=None,debug=False):
  global I2Cobj, UARTobj, Power
  if not atype: return False
  if type(atype) is list:
    for item in atype: PinPower(atype=item, on=on, debug=debug)
    return
  elif atype in ['meteo','display']:
    if (not Power['i2c']) or (on == None): return
    getI2C(atype=atype,debug=debug) # influences whole bus
    if I2Cobj:
      return I2Cobj.PwrI2C(I2Cobj.devs[atype]['pins'],on=on)
    else: raise ValueError("I2C power")
  elif atype in ['gps','dust']:
    if (not Power['ttl']) or (on == None): return
    getUART(atype=atype,debug=debug)
    if UARTobj:
      return UARTobj.PwrTTL(UARTobj.devs[atype]['pins'],on=on)
    else: raise ValueError("UART power")

# tiny display Adafruit SSD1306 128 X 64 oled driver
def initDisplay(debug=False):
  global Display
  global I2Cobj
  if not getI2C(atype='display',debug=debug): return False
  if not I2Cobj.DISPLAY[:3] in ['SSD']: return False
  if Display['fd']: return True
  if (Display['use'] == None) and I2Cobj.i2cDisplay:
      Display = I2Cobj.i2cDisplay
      useDisplay = None
      try: from Config import useDisplay
      except: pass
      if useDisplay: Display['use'] = True
      # if useDisplay.upper() == 'SPI': Display['spi'] = True
  if not Display['use']: return True  # initialize only once
  try:
      import SSD1306 as DISPLAY
      width = 128; height = 64  # display sizes
      if 'i2c' in Display.keys(): # display may flicker on reload
        Display['fd'] = DISPLAY.SSD1306_I2C(width,height,
                               Display['i2c'], addr=Display['address'])
        if debug:
          print('Oled %s:' % Display['name'] + ' SDA~>%s, SCL~>%s, Pwr~>%s' % Display['pins'][:3], ' is %d' % I2Cobj.PwrI2C(Display['pins']))
      #elif 'spi' in Display.keys(): # for fast display This needs rework for I2C style
      #  global spi, spiPINS
      #  try:
      #    from Config import S_CLKI, S_MOSI, S_MISO  # SPI pins config
      #  except:
      #    S_SCKI = 'P10'; S_MOSI = 'P11'; S_MISO = 'P14'  # SPI defaults
      #  if not len(spi): from machine import SPI
      #  try:
      #    from Config import S_DC, S_RES, S_CS      # GPIO SSD pins
      #  except:
      #    S_DC = 'P5'; S_RES = 'P6'; S_CS = 'P7'    # SSD defaults
      #  nr = SPIdevs(spiPINs,(S_DC,S_CS,S_RES,S_MOSI,S_CLKI))
      #  if spi[nr] == None:
      #    spi[nr] = SPI(nr,SPI.MASTER, baudrate=100000,
      #                  pins=(S_CLKI, S_MOSI, S_MISO))
      #  Display['fd'] = DISPLAY.SSD1306_SPI(width,height,spi[nr],
      #                  S_DC, S_RES, S_CS)
      #  if debug: print('Oled SPI %d: ' % nr + 'DC ~> %s, CS ~> %s, RES ~> %s,
      #                   MOSI/D1 ~> %s,
      #                   CLK/D0 ~> %s ' % spiPINs[nr] + 'MISO ~> %s' % S_MISO)
      else:
        Display['fd'] = None
        print("No SSD display or bus found")
      if Display['fd']:
        Display['enabled'] = True
        Display['fd'].fill(1); oledShow(); sleep_ms(200)
        Display['fd'].fill(0); oledShow()
  except Exception as e:
      Display['fd'] = None
      print('Oled display failure: %s' % e)
      return False
  return True

# oled on SPI creates I2C bus errors
#  display('BME280 -> OFF', (0,0),True)

# start meteo sensor
def initMeteo(debug=False):
  global Meteo, I2Cobj
  global calibrate
  if Meteo['enabled'] or Meteo['fd']: return True
  if not getI2C(atype='meteo',debug=debug): return False
  else: Meteo = I2Cobj.i2cMeteo
  if not Meteo['use']: return False
  if (Meteo['name'][:3] in ['BME','SHT']) and Meteo['i2c']:
    try:
      if debug: print("Try %s" % Meteo['name'])
      if Meteo['name'] == 'BME280':
          import BME280 as BME
          Meteo['fd'] = BME.BME_I2C(Meteo['i2c'], address=Meteo['address'], debug=debug, calibrate=calibrate)
      elif Meteo['name'] == 'BME680':
          import BME_I2C as BME
          Meteo['fd'] = BME.BME_I2C(Meteo['i2c'], address=Meteo['address'], debug=debug, calibrate=calibrate)
          if not 'gas_base' in Meteo.keys():
            try:
               from Config import M_gBase
               Meteo['gas_base'] = int(M_gBase)
            except: pass
          if 'gas_base' in Meteo.keys():
              Meteo['fd'].gas_base = Meteo['gas_base']
          if not Meteo['fd'].gas_base:
              display('AQI wakeup')
              Meteo['fd'].AQI # first time can take a while
              Meteo['gas_base'] = Meteo['fd'].gas_base
          display("Gas base: %0.1f" % Meteo['fd'].gas_base)
          # Meteo['fd'].sea_level_pressure = 1011.25
      elif Meteo['name'][:3] == 'SHT':
        import Adafruit_SHT31 as SHT
        meteo = 'SHT31'
        Meteo['fd'] = SHT.SHT31(address=Meteo['address'], i2c=Meteo['i2c'], calibrate=calibrate)
      else: # DHT serie deprecated
        LED.blink(5,0.3,0xff0000,True)
        raise ValueError("Unknown meteo %s type" % meteo)
      Meteo['enabled'] = True
      if debug:
        print('Meteo %s:' % Meteo['name'] + ' SDA~>%s, SCL~>%s, Pwr~>%s' % Meteo['pins'][:3], ' is %d' % I2Cobj.PwrI2C(Meteo['pins']))
    except Exception as e:
      Meteo['use'] = False
      display("meteo %s failure" % Meteo['name'], (0,0), clear=True)
      print(e)
  if not Meteo['use']:
    if debug: print("No meteo in use")
    return False
  return True

# UART devices
def initDust(debug=False):
  global calibrate, interval
  global Dust, UARTobj
  if Dust['enabled'] or Dust['fd']: return True
  if not getUART(atype='dust', debug=debug): return False
  Dust = UARTobj.devs['dust']
  Dust['enabled'] = False
  if Dust['use'] and (Dust['name'][:3] in ['SDS','PMS','SPS']):
    # initialize dust: import relevant dust library
    Dust['cnt'] = False # dflt do not show PM cnt
    try:
      if Dust['name'][:3] == 'SDS':    # Nova
        from SDS011 import SDS011 as senseDust
      elif Dust['name'][:3] == 'SPS':  # Sensirion
        from SPS30 import SPS30 as sensedust
      elif Dust['name'][:3] == 'PMS':  # Plantower
        from PMSx003 import PMSx003 as senseDust
      else:
        LED.blink(5,0.3,0xff0000,True)
        raise ValueError("Unknown dust sensor")
      try:
        from Config import Dext # show also pm counts
        if Dext: Dust['cnt'] = True
      except: pass
      # #pcs=range(PM0.3-PM) + average grain size, True #pcs>PM
      Dust['expl'] = False
      try:
        from Config import Dexplicit
        if Dexplicit:  Dust['expl'] = True
      except: pass
      if Dust['uart'] == None: Dust['uart'] = uarts.index('dust')
      Dust['fd'] = senseDust(port=Dust['uart'], debug=debug, sample=interval['sample'], interval=0, pins=Dust['pins'][:2], calibrate=calibrate, explicit=Dust['expl'])
      if debug:
        print('%s UART:' % Dust['name'] + ' Tx~>%s, Rx~>%s, Pwr~>%s' % Dust['pins'][:3], ' is', UARTobj.PwrTTL(Dust['pins']))
    except Exception as e:
      display("%s failure" % Dust['name'], (0,0), clear=True)
      print(e)
      Dust['name'] = ''
    if debug: print('dust: %s' % Dust['name'])
  elif debug: print("No dust in use")
  if Dust['fd']: Dust['enabled'] = True
  return Dust['use']

def DoGPS(debug=False):
  global Gps, thisGPS
  global UARTobj, Power, interval
  if Gps['use'] == None: initGPS(debug=debug)
  if not Gps['fd'] or not Gps['enabled']: return None
  from time import localtime, timezone
  if time() <= interval['gps_next']:
    if debug: print("No GPS update")
    return None
  if debug: print("Try date/RTC update")
  myGPS = [0.0,0.0,0.0]; prev = None
  try:
    prev = UARTobj.PwrTTL(Gps['pins'],on=True)
    if Gps['fd'].quality < 1: display('wait GPS')
    for cnt in range(1,5):
      Gps['fd'].read()
      if Gps['fd'].quality > 0: break
      if debug: print("GPS %d try" % cnt)
    Gps['rtc'] = None
    if Gps['fd'].satellites > 3:
      Gps['fd'].UpdateRTC()
      if Gps['fd'] == None: Gps['rtc'] = True
    else:
      if (Gps['fd'] == None) or debug: display('no GPS')
      return None
    if Gps['rtc'] == True:
      now = localtime()
      if 3 < now[1] < 11: timezone(7200) # simple DST
      else: timezone(3600)
      display('%d/%d/%d %s' % (now[0],now[1],now[2],('mo','tu','we','th','fr','sa','su')[now[6]]))
      display('time %02d:%02d:%02d' % (now[3],now[4],now[5]))
      Gps['rtc'] = False
    if Power['ttl']: UARTobj.PwrTTL(Gps['pins'],on=prev)
    if Gps['fd'].longitude > 0:
      if debug: print("Update GPS coordinates")
      myGPS[LON] = round(float(Gps['fd'].longitude),5)
      myGPS[LAT] = round(float(Gps['fd'].latitude),5)
      myGPS[ALT] = round(float(Gps['fd'].altitude),1)
      if thisGPS[0] < 0.1:
        thisGPS = myGPS[0:] # home location
        if interval['info'] < 60: interval['info_next'] = interval['info'] = 1 # force
    else: return None
    if debug:
      print("GPS: lon %.5f, lat %.5f, alt %.2f" % (myGPS[LON],myGPS[LAT],myGPS[ALT]))
  except:
    Gps['enabled'] = False; Gps['fd'].ser.deinit(); Gps['fd'] = None
    display('GPS error')
    return None
  if interval['gps_next']: interval['gps_next'] = time()+interval['gps']
  return myGPS

# initialize GPS: GPS config tuple (LAT,LON,ALT)
def initGPS(debug=False):
  global lastGPS, thisGPS
  global Gps, UARTobj
  if Gps['enabled'] or Gps['fd']: return True
  if not getUART(atype='gps', debug=debug): return False
  Gps = UARTobj.devs['gps']
  Gps['enabled'] = False; Gps['fd'] = None; Gps['rtc'] = None
  if not Gps['use']:
      display('No GPS'); return False
  try:
      import GPS_dexter as GPS
      if Gps['uart'] == None: Gps['uart'] = uarts.index('gps')
      Gps['fd'] = GPS.GROVEGPS(port=Gps['uart'],baud=9600,debug=debug,pins=Gps['pins'][:2])
      if debug:
        print('%s UART:' % Gps['name'] + ' Rx~>%s, Tx~>%s, Pwr~>%s' % Gps['pins'][:3], ' is ', UARTobj.PwrTTL(Gps['pins']))
      Gps['enabled'] = True
      myGPS = DoGPS(debug=debug)
      if myGPS != None: lastGPS = myGPS
  except Exception as e:
      display('GPS failure', (0,0), clear=True)
      print(e)
      Gps['enabled'] = False; Gps['fd'].ser.deinit(); Gps['fd'] = None
  return Gps['enabled']

# returns distance in meters between two GPS coodinates
# hypothetical sphere radius 6372795 meter
# courtesy of TinyGPS and Maarten Lamers
# should return 208 meter 5 decimals is diff of 11 meter
# GPSdistance((51.419563,6.14741),(51.420473,6.144795))
def GPSdistance(gps1,gps2):
  global LAT, LON
  from math import sin, cos, radians, pow, sqrt, atan2
  delta = radians(gps1[LON]-gps2[LON])
  sdlon = sin(delta)
  cdlon = cos(delta)
  lat = radians(gps1[LAT])
  slat1 = sin(lat); clat1 = cos(lat)
  lat = radians(gps2[LAT])
  slat2 = sin(lat); clat2 = cos(lat)

  delta = pow((clat1 * slat2) - (slat1 * clat2 * cdlon),2)
  delta += pow(clat2 * sdlon,2)
  delta = sqrt(delta)
  denom = (slat1 * slat2) + (clat1 * clat2 * cdlon)
  return int(round(6372795 * atan2(delta, denom)))

def LocUpdate(debug=False):
  global Gps, UARTobj
  global Gps, lastGPS, thisGPS
  if not DoGPS(debug=debug): return lastGPS[0:]
  if GPSdistance(thisGPS,lastGPS) <= 50.0:
    return None
  lastGPS = thisGPS[0:]
  return thisGPS

# called via TTN response
# To Do: make the remote control survive a reboot
def CallBack(port,what):
  global interval, HALT
  global Display, Dust, Meteo
  if not len(what): return True
  if len(what) < 2:
    if what == b'?':
      SendInfo(port); return True
    elif what == b'O':
      if Display['use']:
        Display['fd'].poweroff()
        Power['display'] = False
    elif what == b'o':
      if Display['use']:
        Display['fd'].poweron()
        Powert['display'] = None
    elif what == b'd':
      if Dust['use']:
        Dust['raw'] = True # try: Dust['fd'].gase_base = None
    elif what == b'D':
      if Dust['use']:
        Dust['raw'] = False # try: Dust['fd'].gase_base = None
    elif what == b'm':
        if Meteo['use']: Meteo['raw'] = True
    elif what == b'M':
        if Meteo['use']: Meteo['raw'] = False
    elif what == b'S': HALT = True
    elif what == b'#':  # send partical cnt
        if Dust['name'][:3] != 'SDS': Dust['cnt'] = True
    elif what == b'w': # send partical weight
        Dust['cnt'] = False
    else: return False
    return True
  cmd = None; value = None
  try:
    cmd, value = struct.unpack('>BH',what)
  except:
    return False
  if cmd == b'i':  # interval
    if value*60 > interval['sample']: interval['interval'] = value*60 - interval['sample']

# LoRa setup
def initNetwork(debug=False):
  global Network

  def whichNet(debug=False):
    global Network
    Network['use'] = False
    Network['enabled'] = False
    try:
      from Config import Network as net
      Network['name'] = net
      Network['use'] = True
    except:
      net = None
    if Network['name'] == 'TTN':
      Network['keys'] = {}
      try:
          from Config import dev_eui, app_eui, app_key
          if len(dev_eui) != 16:
            SN = getSN(); dev_eui = dev_eui[0:16-len(SN)]+SN.upper()
          Network['keys']['OTAA'] = (dev_eui, app_eui, app_key)
      except: pass
      try:
          from Config import dev_addr, nwk_swkey, app_swkey
          # to do: dev_addr from SN?
          Network['keys']['ABP'] = (dev_addr, nwk_swkey, app_swkey)
      except: pass
      if not len(Network['keys']):
        pycom.rgbled(0xFF0000)
        display('LoRa config failure')
        return False
      if debug: print("LoRa: ", Network['keys'])
      return True
    print("No network found")
    return False

  if Network['enabled']: return True   # init only once
  if not whichNet(debug=debug): return False
  if Network['name'] == 'TTN':
    if not len(Network['keys']): return False
    from lora import LORA
    Network['fd'] = LORA()
    # Connect to LoRaWAN
    display("Try  LoRaWan", (0,0), clear=True)
    # need 2 ports: data on 4, info/ident on 3
    if Network['fd'].connect(Network['keys'], ports=(len(Dprt)+1), callback=CallBack):
       display("Using LoRaWan")
       Network ['enabled'] = True
    else:
       display("NO LoRaWan")
       Network['fd'] = None
       Network ['enabled'] = False
    sleep_ms(10*1000)
    return Network ['enabled']
  if Network == 'None':
    display("No network!", (0,0), clear=True)
    LED.blink(10,0.3,0xff00ff,True)
    # raise OSError("No connectivity")
    return False
  else: return False

# PM weights
PM1 = const(0)
PM25 = const(1)
PM10 = const(2)
# PM count >= size
PM03c = const(3)
PM05c = const(4)
PM1c = const(5)
PM25c = const(6)
PM5c = const(7)
PM10c = const(8)
def DoDust(debug=False):
  global Dust, nl, STOP, STOPPED, Gps, lastGPS
  global Power, interval
  dData = {}; rData = [None,None,None]
  if Dust['use'] == None: initDust(debug=debug)
  if (not Dust['use']) or (not Dust['enabled']): return rData

  display('PM sensing',(0,0),clear=True,prt=False)
  prev = False
  if Dust['enabled']:
    prev = UARTobj.PwrTTL(Dust['pins'],on=True)
    if not prev:
        sleep_ms(1000)
        Dust['fd'].Standby()
    if Dust['fd'].mode != Dust['fd'].NORMAL:
      Dust['fd'].Normal()
      if not showSleep(secs=15,text='starting up fan'):
        display('stopped SENSING', (0,0), clear=True)
        LED.blink(5,0.3,0xff0000,True)
        return rData
      else:
        if Gps['enabled']:
          display("G:%.4f/%.4f" % (lastGPS[LAT],lastGPS[LON]))
        display('measure PM')
  if Dust['enabled']:
    LED.blink(3,0.1,0x005500)
    # display('%d sec sample' % interval['sample'],prt=False)
    try:
      STOPPED = False
      try:
        SleepThread(interval['sample'],'%d sec sample' % interval['sample'])
      except:
        STOPPED = True
        display('%d sec sample' % interval['sample'])
      dData = Dust['fd'].getData()
      for cnt in range(10):
        if STOPPED: break
        STOP = True
        print('waiting for thread')
        sleep_ms(2000)
      STOP = False
    except Exception as e:
      display("%s ERROR" % Dust['name'])
      print(e)
      LED.blink(3,0.1,0xff0000)
      dData = {}
    LED.blink(3,0.1,0x00ff00)
    if Power['ttl']: UARTobj.PwrTTL(Dust['pins'],on=prev)

  if len(dData):
    for k in dData.keys():
        if dData[k] == None: dData[k] = 0
    try:
      if 'pm1' in dData.keys():   #  and dData['pm1'] > 0:
        display(" PM1 PM2.5 PM10", (0,0), clear=True)
        display("% 2.1f % 5.1f% 5.1f" % (dData['pm1'],dData['pm25'],dData['pm10']))
      else:
        display("ug/m3 PM2.5 PM10", (0,0), clear=True)
        display("     % 5.1f % 5.1f" % (dData['pm25'],dData['pm10']))
        dData['pm1'] = 0
    except:
      dData = {}
  if (not dData) or (not len(dData)):
    display("No PM values")
    LED.blink(5,0.1,0xff0000,True)
  else:
    rData = []
    for k in ['pm1','pm25','pm10']:
      rData.append(round(dData[k],1) if k in dData.keys() else None)

    if Dust['cnt']:
      cnttypes = ['03','05','1','25','5','10']
      if Dust['name'][:3] == 'SPS': cnttypes[4] = '4'
      for k in cnttypes:
        if 'pm'+k+'_cnt' in dData.keys():
            rData.append(round(dData['pm'+k+'_cnt'],1))
        else: rData.append(0.0) # None
      if not Dust['expl']:  # PM0.3 < # pcs <PMi
        rData[3] = round(dData['grain'],2) # PM0.3 overwritten
        # print('pm grain: %0.2f' % dData['grain'])
    LED.off()
  return rData

TEMP = const(0)
HUM  = const(1)
PRES = const(2)
GAS  = const(3)
AQI  = const(4)
def DoMeteo(debug=False):
  global Meteo, I2Cobj
  global nl, LF

  def convertFloat(val):
    return (0 if val is None else float(val))

  mData = [None,None,None,None,None]
  if Meteo['use'] == None: initMeteo(debug=debug)
  if (not Meteo['use']) or (not Meteo['enabled']): return mData

  # Measure BME280/680: temp oC, rel hum %, pres pHa, gas Ohm, aqi %
  LED.blink(3,0.1,0x002200,False); prev = 1
  try:
    prev = I2Cobj.PwrI2C(Meteo['pins'],i2c=Meteo['i2c'],on=True)
    if (Meteo['name'] == 'BME680') and (not Meteo['fd'].gas_base): # BME680
      display("AQI base: wait"); nl -= LF
    #Meteo['i2c'].init(nr, pins=Meteo['pins']) # SPI oled causes bus errors
    #sleep_ms(100)
    mData = []
    for item in range(0,5):
        mData.append(0)
        for cnt in range(0,5): # try 5 times to avoid null reads
            try:
                if item == TEMP: # string '20.12'
                    mData[TEMP] = convertFloat(Meteo['fd'].temperature)
                elif item == HUM: # string '25'
                    mData[HUM] = convertFloat(Meteo['fd'].humidity)
                elif Meteo['name'][:3] != 'BME': break
                elif item == PRES: # string '1021'
                    mData[PRES] = convertFloat(Meteo['fd'].pressure)
                elif Meteo['name'] == 'BME680':
                    if item == GAS: mData[GAS] = convertFloat(Meteo['fd'].gas)
                    elif item == AQI:
                        mData[AQI] = round(convertFloat(Meteo['fd'].AQI),1)
                        if not 'gas_base' in Meteo.keys():
                            Meteo['gas_base'] = Meteo['fd'].gas_base
                break
            except OSError as e: # I2C bus error, try to recover
                print("OSerror %s on data nr %d" % (e,item))
                Meteo['i2c'].init(I2C.MASTER, pins=Meteo['pins'])
                LED.blink(1,0.1,0xff6c00,False)
    # work around if device corrupts the I2C bus
    # Meteo['i2c'].init(I2C.MASTER, pins=Meteo['pins'])
    sleep_ms(500)
    rectangle(0,nl,128,LF,0)
  except Exception as e:
    display("%s ERROR: " % Meteo['name'])
    print(e)
    LED.blink(5,0.1,0xff00ff,True)
    return [None,None,None,None,None]

  LED.off()
  # display results
  nl += 6  # oled spacing
  if Meteo['name'] == 'BME680':
    title = "  C hum% pHa AQI"
    values = "% 2.1f %2d %4d %2d" % (round(mData[TEMP],1),round(mData[HUM]),round(mData[PRES]),round(mData[AQI]))
  elif Meteo['name'] == 'BME280':
    title = "    C hum%  pHa"
    values = "% 3.1f  % 3d % 4d" % (round(mData[TEMP],1),round(mData[HUM]),round(mData[PRES]))
  else:
    title = "    C hum%"
    values = "% 3.1f  % 3d" % (round(mData[TEMP],1),round(mData[HUM]))
  display(title)
  display("o",(12,-5),prt=False)
  display(values)
  if not prev: I2Cobj.PwrI2C(Meteo['pins'],i2c=Meteo['i2c'],on=prev)
  return mData # temp, hum, pres, gas, aqi

# denote a null value with all ones
# denote which sensor values present in data package
def DoPack(dData,mData,gps=None,debug=False):
  global Dust
  t = 0
  for d in dData, mData:
    for i in range(1,len(d)):
      if d[i] == None: d[i] = 0
  if mData[0] == None: mData[0] = 0
  if dData[PM1] == None: # PM2.5 PM10 case
    d = struct.pack('>HH',int(dData[PM25]*10),int(dData[PM10]*10))
    # print("PM 2.5, 10 cnt: ", dData[1:3])
  else:
    d = struct.pack('>HHH',int(dData[PM1]*10),int(dData[PM25]*10),int(dData[PM10]*10))
    t += 1
  if ('cnt' in Dust.keys()) and Dust['cnt']: # add counts
    # defeat: Plantower PM5c == Sensirion PM4c: to do: set flag in PM5c
    flg = 0x8000 if Dust['name'][:3] in ['SPS',] else 0x0
    try:
      if Dust['expl']:
        # 9 decrementing bytes, may change this
        d += struct.pack('>HHHHHH',
          int(dData[PM10c]*10+0.5),
          int(dData[PM05c]*10+0.5),
          int(dData[PM1c]*10+0.5),
          int(dData[PM25c]*10+0.5),
          int(dData[PM5c]*10+0.5)|flg,
          int(dData[PM03c]*10+0.5))
      else:
        # 9 bytes, ranges, average grain size  >0.30*100
        d += struct.pack('>HHHHHH',
          int((dData[PM10c]-dData[PM5c])*10+0.5)|0x8000,
          int(dData[PM05c]*10+0.5),
          int((dData[PM1c]-dData[PM05c])*10+0.5),
          int((dData[PM25c]-dData[PM1c])*10+0.5),
          int((dData[PM5c]-dData[PM25c])*10+0.5)|flg,
          int(dData[PM03c]*100+0.5))
    except:
      d += struct.pack('>HHHHHH',0,0,0,0,0,0)
      display("Error dust fan",clear=True)
      LED.blink(5,0.2,0xFF0000,False)
    t += 2
  m = struct.pack('>HHH',int(mData[TEMP]*10+300),int(mData[HUM]*10),int(mData[PRES]))
  if len(mData) > 3:
    m += struct.pack('>HH',int(round(mData[GAS]/100.0)),int(mData[AQI]*10))
    t += 4
  if (type(gps) is list) and (gps[LAT] > 0.01):
    l = struct.pack('>lll', int(round(gps[LAT]*100000)),int(round(gps[LON]*100000)),int(round(gps[ALT]*10)))
    t += 8
  else: l = ''
  # return d+m+l
  t = struct.pack('>B', t | 0x80) # flag the package
  return t+d+m+l # flag the package

# send kit info to LoRaWan
def SendInfo(port=Iprt):
  global Meteo, Dust, Network, LED
  global Gps, lastGPS, thisGPS
  meteo = ['','DHT11','DHT22','BME280','BME680','SHT31']
  dust = ['None','PPD42NS','SDS011','PMSx003','SPS30']
  if Network['fd'] == None: return False
  print("meteo: %s, dust: %s" %(Meteo['name'],Dust['name']))
  if (not Meteo['enabled']) and (not Dust['enabled']) and (not Gps['enabled']):
    return True
  sense = ((meteo.index(Meteo['name'])&0xf)<<4) | (dust.index(Dust['name'])&0x7)
  gps = 0
  LocUpdate()
  sense |= 0x8
  version = int(__version__[0])*10+int(__version__[2])
  data = struct.pack('>BBlll',version,sense, int(thisGPS[LAT]*100000),int(thisGPS[LON]*100000),int(thisGPS[ALT]*10))
  Network['fd'].send(data,port=port)
  LED.blink(1,0.2,0x0054FF,False) # blue
  return None

# identity PyCom SN
def getSN():
  from machine import unique_id
  import binascii
  SN = binascii.hexlify(unique_id()).decode('utf-8')
  return SN

# startup info
def Info(debug=False):
  global interval
  global STOP
  global Network
  global Dust
  global lastGPS
  global Meteo

  try:
    # connect I2C devices
    initDisplay(debug=debug)

    import os
    display('%s' % PyCom, (0,0),clear=True)
    display("MySense %s" % __version__[:8], (0,0), clear=True)
    display("s/n " + getSN())

    display("probes: %ds/%dm" % (interval['sample'], (interval['interval']+interval['sample'])/60))

    if initDust(debug=debug):
        if Dust['cnt']: display("PM pcs:" + Dust['name'])
        else: display("PM   : " + Dust['name'])
    else: display("No dust sensor")

    if initMeteo(debug=debug):
        display("meteo: " + Meteo['name'])
    else: display("No meteo sensor")

    sleep_ms(15000)
    if not initGPS(debug=debug):
        display("No GPS")
    display('G:%.4f/%.4f' % (lastGPS[LAT],lastGPS[LON]))

    if initNetwork(debug=debug):
        display('Network: %s' % Network['name'])
    else: display("No network")
    if Network['enabled']: SendInfo()

  except Exception as e:
    # pycom.rgbled(0xFF0000)
    display("ERROR %s" % e)
    return False
  return True

# main loop
def runMe(debug=False):
  global interval, Power
  global UARTobj, I2Cobj
  global Dust
  global Meteo

  if not 'info_next' in interval.keys(): interval['info_next'] = 0
  if not Info(debug=debug): # initialize devices and show initial info
    print("FATAL ERROR")
    return False

  while True: # LOOP forever
    toSleep = time()
    if interval['info'] and (toSleep > interval['info_next']): # send info update
       SendInfo()
       if interval['info'] < 60: interval['info'] = 0 # was forced
       toSleep = time()
       interval['info_next'] = toSleep + interval['info']
    # Power management ttl is done by DoXYZ()
    if Display['enabled'] and Power['display']: Display['fd'].poweron()

    dData = DoDust(debug=debug)
    if Dust['use']:
        Dust['fd'].Standby()   # switch off laser and fan
        PinPower(atype='dust',on=False,debug=debug)

    mData = DoMeteo(debug=debug)

    # Send packet
    if Network['enabled']:
        if (Network['name'] == 'TTN'):
          if ('cnt' in Dust.keys()) and Dust['cnt']: port=Dprt[1]
          else: port=Dprt[0]
          if  Network['fd'].send(DoPack(dData,mData,LocUpdate(),debug=debug),port=port):
            LED.off()
          else:
            display(" LoRa send ERROR")
            LED.blink(5,0.2,0x9c5c00,False)
        else: LED.blink(2,0.2,0xFF0000,False)

    if STOP:
      sleep_ms(60*1000)
      Display['fd'].poweroff()
      PinPower(atype=['dust','gps','meteo','display'],on=False,debug=debug)
      # and put ESP in deep sleep: machine.deepsleep()
      return False

    toSleep = interval['interval'] - (time() - toSleep)
    if Dust['enabled']:
      if toSleep > 30:
        toSleep -= 15
        Dust['fd'].Standby()   # switch off laser and fan
      elif toSleep < 15: toSleep = 15
    PinPower(atype=['gps','dust'],on=False,debug=debug) # auto on/off next time
    if Display['enabled'] and (Power['display'] != None):
       Display['fd'].poweroff()
    elif not Power['i2c']:
      if not ProgressBar(0,62,128,1,toSleep,0xebcf5b,10):
        display('stopped SENSING', (0,0), clear=True)
        LED.blink(5,0.3,0xff0000,True)
      continue
    PinPower(atype=['display','meteo'],on=False,debug=debug)
    if not Power['sleep']: LED.blink(10,int(toSleep/10),0x748ec1,False)
    else:
      # save config and LoRa
      sleep(toSleep) # deep sleep
      # restore config and LoRa
    PinPower(atype=['display','meteo'],on=True,debug=debug)

if __name__ == "__main__":
  runMe(debug=True)
  import sys
  sys.exit() # reset
