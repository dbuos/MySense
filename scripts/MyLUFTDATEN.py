#!/usr/bin/env python3
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

# $Id: MyLUFTDATEN.py,v 3.14 2020/04/25 13:24:20 teus Exp teus $

# TO DO: write to file or cache
# reminder: InFlux is able to sync tables with other MySQL servers

""" Publish measurements to Madavi.de and Luftdaten.info
    they will appear as graphs in http://www.madavi.de/sensor/graph.php
    Make sure to enable acceptance for publishing in the map of Luftdaten
    by emailing the prefix-serial and location details.
    if 'madavi' and/or 'luftdaten' is enabled in ident send them a HTTP POST
    Relies on Conf setting by main program
"""
modulename='$RCSfile: MyLUFTDATEN.py,v $'[10:-4]
__version__ = "0." + "$Revision: 3.14 $"[11:-2]

try:
    import sys
    import datetime
    import json
    import requests
    import signal
    from time import time
    import re
except ImportError as e:
    sys.exit("FATAL: One of the import modules not found: %s" % e)

# configurable options
__options__ = ['output','luftdaten','madavi','id_prefix',
        'serials', 'projects','active','DEBUG']

Conf = {
    'output': False,
    # defined by, obtained from LuftDaten: Rajko Zschiegner dd 24-12-2017
    'id_prefix': "TTNMySense-", # prefix ID prepended to serial number of module
    'luftdaten': 'https://api.luftdaten.info/v1/push-sensor-data/', # api end point
    'madavi': 'https://api-rrd.madavi.de/data.php', # madavi.de end point
    # expression to identify serials to be subjected to be posted
    'serials': '(f07df1c50[02-9]|93d73279d[cd])', # pmsensor[1 .. 11] from pmsensors
    'projects': 'VW2017',# expression to identify projects to be posted
    'active': True,      # output to luftdaten maps is also activated
    'registrated': None, # has done initial setup
    'log': None,         # MyLogger log print routine
    'DEBUG': False       # debugging info
}

# ========================================================
# write data directly to a database
# =======================================================
# once per session registrate and receive session cookie
# =======================================================
# TO DO: this needs to have more security in it e.g. add apikey signature
def registrate(net):
    global Conf
    if not Conf['log']:
        import MyLogger
        Conf['log'] = MyLogger.log
    if Conf['registrated'] != None:
            return Conf['registrated']
    import logging
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    # req_log = logging.getLogger('requests.packages.urllib3')
    # req_log.setLevel(logging.WARNING)
    # req_log.propagate = True
    if net['module'] is bool:
        if (not net['module']) or (not net['connected']): return False
    Conf['match'] = re.compile(Conf['projects']+'_'+Conf['serials'], re.I)
    Conf['registrated'] = True
    return Conf['registrated']

# Luftdaten nomenclature and ID codes:
sense_table = {
    "meteo": {
        # X-Pin codes as id used by Luftdaten for meteo sensors
        # from airrohr-firmware/ext_def.h
        "types": {
            # 680 pin nr is a guess
            'DHT22': 7, 'BME680': 11, 'BME280': 11, 'BME180': 11,
            'BMP280': 3, 'BMP180': 3,
            'DS18B20': 13, 'HTU21D': 7,
        },
        "temperature": ['temperature','temp','dtemp',],
        "humidity": ['humidity','hum','rv','rh',],
        "pressure": ['pres','pressure','luchtdruk',],
    },
    "dust": {
        # X-Pin codes as id used by Luftdaten for dust sensors
        # TO DO: complete the ID codes used by Luftdaten
        "types": {
            'SDS011': 1, 'PMS3003': 1, 'PMS7003': 1, 'PMS5003': 1,
            'PMSx003': 1, 'PMSX003': 1,
            # SPS30 pin nr is a guess
            'SPS30': 1, 'HPM': 25, 'PPD42NS': 5, 'SHINEY': 5,
        },
        "P1": ['pm10','pm10_atm',],  # should be P10
        "P2": ['pm2.5','pm25'],      # should be P25
        # missing pm1
    },
}

# send only a selection of possible measurements from the sensors
# Post meteo and dust data separately
def sendLuftdaten(ident,values):
    global __version__, Conf
    # the Luftdaten API json template
    # suggest to limit posts and allow one post with multiple measurements
    if 'luftdatenID' in ident.keys():
        headers = {
            'X-Sensor': Conf['id_prefix'] + str(ident['luftdatenID']),
        }
    else:
        headers = {
            'X-Sensor': Conf['id_prefix'] + str(ident['serial']),
        }
    postdata = {
        'software_version': 'MySense' + __version__,
    }
    postTo = []
    for url in ['luftdaten','madavi']:
        if (url == 'luftdaten') and (not ident['luftdaten']):
          print("Not (%s) to Luftdaten for kit: %s" % (str(ident['luftdaten']),headers['X-Sensor']))
          continue
        if ident[url] or ident['luftdaten'] == None:
          if url in ident.keys():
            postTo.append(Conf[url])
    if not len(postTo): return True
    for sensed in ['dust','meteo']:
        headers['X-Pin'] = None
        for sensorType in sense_table[sensed]['types']:
            if sensorType.lower() in [ x.lower() for x in ident['types']]:
                headers['X-Pin'] = str(sense_table[sensed]['types'][sensorType])
                break
        if not headers['X-Pin']: continue
        postdata['sensordatavalues'] = []
        for field in sense_table[sensed].keys():
            for valueField in values:
                if valueField in sense_table[sensed][field]:
                    postdata['sensordatavalues'].append({ 'value_type': field, 'value': str(round(values[valueField],2)) })
        if not len(postdata['sensordatavalues']): continue
        if not post2Luftdaten(headers,postdata,postTo,sensed):
            return False
    return True
        
# seems https may hang once a while
def alrmHandler(signal,frame):
    global Conf
    Conf['log'](modulename,'DEBUG','HTTP POST hangup, post aborted. Alarm nr %d' % signal)
    # signal.signal(signal.SIGALRM,None)

def watchOn(url):
    if url[:6] != 'https:': return None
    rts = [None,0,0]
    rts[0] = signal.signal(signal.SIGALRM,alrmHandler)
    rts[1] = int(time())
    rts[2] = signal.alarm(3*30)
    return rts

def watchOff(prev):
    if prev == None: return 1
    alrm = signal.alarm(0)
    if prev[0] and (prev[0] != alrmHandler):
        signal.signal(signal.SIGALRM,prev[0])
        if prev[2] > 0: # another alarm and handler was active
            prev[1] = prev[2] - (int(time()) - prev[1])
            if prev[1] <= 0:
                prev[1] = 1
            signal.alarm(prev[1])
    return alrm
    
# do an HTTP POST to [ Madavi.de, Luftdaten, ...]
def post2Luftdaten(headers,postdata,postTo,sensed):
    global Conf
    # debug time: do not really post this
    Conf['log'](modulename,'DEBUG',"Post headers: %s" % str(headers))
    Conf['log'](modulename,'DEBUG',"Post data   : %s" % str(postdata))
    rts = True
    if not 'HTTP_errors' in post2Luftdaten.__dict__:
        post2Luftdaten.HTTP_errors = {}
    if (headers['X-Sensor'] in post2Luftdaten.HTTP_errors.keys()) and ((post2Luftdaten.HTTP_errors[headers['X-Sensor']]%15) >= 3):
        Conf['log'](modulename,'ERROR','Posts for %s too many errors. Skipping.' % headers['X-Sensor'])
        post2Luftdaten.HTTP_errors[headers['X-Sensor']] += 1
        return True
    for url in postTo:
        prev = watchOn(url)
        try:
            r = requests.post(url, json=postdata, headers=headers)
            # Conf['log'](modulename,'INFO','Post to: %s' % url)
            Conf['log'](modulename,'DEBUG','Post returned status: %d' % r.status_code)
            if Conf['DEBUG']:
              if not r.ok:
                sys.stderr.write("Luftdaten POST to %s:\n" % url)
                sys.stderr.write("     headers: %s\n" % str(headers))
                sys.stderr.write("     data   : %s\n" % str(postdata))
                sys.stderr.write("     returns: %d\n" % r.status_code)
              else:
                host = ('Luftdate.info' if url.find('luftdaten') > 0 else 'madavi.de')
                sys.stderr.write("POST %s OK(%d) to %s ID(%s).\n" % (sensed,r.status_code,host,headers['X-Sensor']))
            if not r.ok:
                rts = False
                if r.status_code == 403:
                  Conf['log'](modulename,'ERROR','Post %s to %s with status code: forbidden (%d)' % (sensed,headers['X-Sensor'],r.status_code))
                elif r.status_code == 400:
                  Conf['log'](modulename,'ERROR','Not registered post %s for ID %s, status code: %d' % (sensed,headers['X-Sensor'],r.status_code))
                  raise ValueError("EVENT Not registered %s POST for ID %s" % (url,headers['X-Sensor']))
                else:
                  Conf['log'](modulename,'ATTENT','Post %s to %s with status code: %d' % (sensed,headers['X-Sensor'],r.status_code))
                if not headers['X-Sensor'] in post2Luftdaten.HTTP_errors.keys():
                  post2Luftdaten.HTTP_errors[headers['X-Sensor']]  = 0
                post2Luftdaten.HTTP_errors[headers['X-Sensor']] += 1
            elif headers['X-Sensor'] in post2Luftdaten.HTTP_errors.keys():
                del post2Luftdaten.HTTP_errors[headers['X-Sensor']]
        except requests.ConnectionError as e:
            Conf['log'](modulename,'ERROR','Connection error: ' + str(e))
            rts = False
        except Exception as e:
            if str(e).find('EVENT') >= 0: raise ValueError(str(e)) # send notice event
                # return True # not reached
            Conf['log'](modulename,'ERROR','Error: ' + str(e))
            rts = False
        if not watchOff(prev):
            Conf['log'](modulename,'ATTENT','HTTP 90 sec timeout error: URL %s with ID %s' % (url,headers['X-Sensor']))
            rts = True
    return rts

notMatchedSerials = []
def publish(**args):
    global Conf, notMatchedSerials
    if (not 'output' in Conf.keys()) or (not Conf['output']):
        return
    for key in ['data','internet','ident']:
        if not key in args.keys():
            Conf['log'](modulename,'FATAL',"Publish call missing argument %s." % key)
    if not registrate(args['internet']):
        Conf['log'](modulename,'WARNING',"Unable to registrate the sensor.")
        return False 
    for key in ['project','serial']:
        if (not key in args['ident'].keys()) or (not args['ident'][key]):
            return True
    # ident['luftdaten'] == None -> if not madavi in ident: ident['madavi'] = True
    if (not 'luftdaten' in args['ident'].keys()) and (not 'madavi' in args['ident'].keys()):
        return True
    matched = Conf['match'].match(args['ident']['project']+'_'+args['ident']['serial'])
    # publish only records of the matched project/serial combi,
    # default Madavi is enabled for those matches
    if not matched:
        if not args['ident']['project']+'_'+args['ident']['serial'] in notMatchedSerials:
            notMatchedSerials.append(args['ident']['project']+'_'+args['ident']['serial'])
            Conf['log'](modulename,'INFO',"Skipping records of project %s with serial %s to post to Luftdaten" % (args['ident']['project'],args['ident']['serial']))
        return True
    elif not 'madavi' in args['ident'].keys():  # dflt: Post to madavi.de
        args['ident']['madavi'] = True
    mayPost = False
    # if 'madavi' and/or 'luftdaten' is enabled in ident send them a HTTP POST
    for postTo in ['madavi','luftdaten',]:
        if not postTo in args['ident'].keys(): args['ident'][postTo] = False
        elif args['ident'][postTo]: mayPost = True
    if args['ident']['luftdaten']: args['ident']['madavi'] = True
    if mayPost: return sendLuftdaten(args['ident'],args['data'])
    return True

# test main loop
if __name__ == '__main__':
    from time import sleep
    Conf['output'] = True
    Conf['active'] = False      # no Post to Luftdaten in this test
    net = { 'module': True, 'connected': True }
    # Conf['DEBUG'] = True        # e.g. print Posts
    Output_test_data = [
        {   'ident': {'geolocation': '0,0,0',
              'luftdaten': False,
              'description': 'MQTT AppID=pmsensors MQTT DeviceID=pmsensor11',
              'fields': ['time', 'pm25', 'pm10', 'temp', 'rv'],
              'project': 'VW2017', 'units': ['s', 'ug/m3', 'ug/m3', 'C', '%'],
              'serial': '93d73279dc',
              'types': ['time', u'SDS011', u'SDS011', 'DHT22', 'DHT22']},
           'data': {
                'pm10': 3.6, 'rv': 39.8, 'pm25': 1.4, 'temp': 25,
                'time': int(time())-24*60*60}},
        {   'ident': {
              'description': 'MQTT AppID=pmsensors MQTT DeviceID=pmsensor1',
              'luftdaten': False,
              'fields': ['time', 'pm25', 'pm10', 'temp', 'rv'],
              'project': 'VW2017', 'units': ['s', 'ug/m3', 'ug/m3', 'C', '%'],
              'serial': 'f07df1c500',
              'types': ['time', u'PMS7003', u'PMS7003', 'BME280', 'BME280']},
           'data': {
                'pm10': 3.6, 'rv': 39.8, 'pm25': 1.6, 'temp': 24, 'pressure': 1024.2,
                'time': int(time())-23*60*60}},
        {   'ident': {
              'geolocation': '51.420635,6.1356117,22.9',
              'version': '0.2.28', 'serial': 'test_sense', # no serial match
              'fields': ['time', 'pm_25', 'pm_10', 'dtemp', 'drh', 'temp', 'rh', 'hpa'],
              'extern_ip': ['83.161.151.250'], 'label': 'alphaTest', 'project': 'BdP',
              'units': ['s', 'pcs/qf', u'pcs/qf', 'C', '%', 'C', '%', 'hPa'],
              'intern_ip': ['192.168.178.49', '2001:980:ac6a:1:83c2:7b8d:90b7:8750',
                    '2001:980:ac6a:1:17bf:6b65:17d2:dd7a'],
              'types': ['time','Dylos DC1100', 'Dylos DC1100',
                'DHT22', 'DHT22', 'BME280', 'BME280', 'BME280'],
              },
            'data': {
              'drh': 29.3, 'pm_25': 318.0, 'temp': 28.75,
              'time': 1494777772, 'hpa': 712.0, 'dtemp': 27.8,
              'rh': 25.0, 'pm_10': 62.0 },
        },
        ]
    for post in Output_test_data:
        try:
            if publish(
                ident=post['ident'],
                data=post['data'],
                internet=net
            ):
                print "Published\n"
            else:
                print "ERROR\n"
        except Exception as e:
            print("output channel error was raised as %s" % e)
            eak
