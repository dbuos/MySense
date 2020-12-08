#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
#
# Copyright (C) 2020, Behoud de Parel, Teus Hagen, the Netherlands
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

# $Id: MyTTNclient.py,v 2.1 2020/12/08 15:06:08 teus Exp teus $

# Broker between TTN and some  data collectors: luftdaten.info map and MySQL DB
# if nodes info is loaded and DB module enabled export nodes info to DB
# the latter will enable to maintain in DB status of kits and kit location/activity/exports

# module mqtt: git clone https://github.com/eclipse/paho.mqtt.python.git
# cd paho.mqtt.python ; python setup.py install
# broker server: Debian: apt-get install mqtt

"""Simple test script for TTN MQTT broker access
    Module can be used as library as well CLI
    command line (CLI) arguments:
        verbose=true|false or -v or --verbose. Default False.
        user=TTNuser user account name for TTN.
        password=TTNpassword eg ttn-account-v2.abscdefghijl123456789ABCD.
        keepalive=N Keep A Live in seconds for connection, defaults to 180 secs.
            Dflt: None.
        node will be seen at TTN as topic ID. Multiple (no wild card) is possible.
        node='comma separated nodes' ... to subscribe to. Dflt node='+' (all wild card).
        show=pattern regular expression of device IDs to display the full data record.
"""

import paho.mqtt.client as mqttClient
import threading
import time, datetime
import re
import sys
import json

# routines to collect messages from TTN MQTT broker (yet only subscription)
# collect records in RecordQueue[] using QueueLock
# broker with TTN connection details: host, user credentials, list of topics
# broker = {
#        "address": "eu.thethings.network",  # Broker address default
#        "port":  1883,                      # Broker port default
#        "user":  "20201126grub",            # Connection username
#                                            # Connection password
#        "password": ttn-account-v2.GW36kBmsaNZaXYCs0jx4cbPiSfaK6r0q9Zj0jx4Bmsts"
#        "topic": "+" , # topic or list of topics to subscribe to
#    }
class TTN_broker:
    def __init__(self, broker, verbose=False, keepalive=180, logger=sys.stdout.write):
        self.TTNconnected = None  # None=ont yet, False from disconnected, True connected
        self.message_nr = 0    # number of messages received
        self.RecordQueue = []  # list of received data records
        self.QueueLock = threading.RLock() # Threadlock fopr queue handling
        self.TTNclient = None  # TTN connection handle
        self.verbose = verbose # verbosity
        self.broker = broker   # TTN access details
        self.KeepAlive = keepalive # connect keepalive in seconds, default 60
        self.logger = logger   # routine to print errors
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            if self.verbose: self.logger("INFO Connected to broker\n")
            self.TTNconnected = True                # Signal connection 
        else:
            self.logger("ERROR Connection failed\n")
            raise IOError("TTN MQTT connection failed")
    
    def _on_disconnect(self, client, userdata, rc):
        if self.verbose:
            self.logger("ERROR TTN disconnect rc=%d: %s.\n" % (rc,[ "successful", "incorrect protocol version", "invalid client identifier", "server unavailable", "bad username or password", "not authorised"][rc]))

        if not rc:
            self.logger("ERROR Disconnect from client site.\n")
        else:
            self.logger("ERROR Disconnect from MQTT broker: %s.\n" % [ "successful", "incorrect protocol version", "invalid client identifier", "server unavailable", "bad username or password", "not authorised"][rc])
        # self.TTNclient.loop_stop()
        time.sleep(0.1)
        self.TTNconnected = False
     
    def _on_message(self, client, userdata, message):
        self.message_nr += 1
        try:
            record = json.loads(message.payload)
            # self.logger("INFO %s: Message %d received: \n" % (datetime.datetime.now().strftime("%m-%d %Hh%Mm"),self.message_nr) + record['dev_id'] + ', port=%d' % record['port'] + ', raw payload="%s"' % record['payload_raw'])
            if len(record) > 25:
                self.logger("WARNING TTN MQTT records overload. Skipping.\n")
            else:
                with self.QueueLock: self.RecordQueue.append(record)
            return True
        except Exception as e:
            # raise ValueError("Payload record is not in json format. Skipped.")
            self.logger("ERROR it is not json payload, error: %s\n" % str(e))
            self.logger("INFO \t%s skipped message %d received: \n" % (datetime.datetime.now().strftime("%m-%d %Hh%Mm"),self.message_nr) + 'topic: %s' % message.topic + ', payload: %s' % message.payload)
            return False

    @property
    def TTNConnected(self):
        return self.TTNconnected
     
    def TTNinit(self):
        if self.TTNclient == None:
            # may need this on reinitialise()
            self.TTNclientID = "ThisTTNtestID" if not 'clientID' in self.broker.keys() else self.broker['clientID']
            if self.verbose:
                self.logger("INFO Initialize TTN MQTT client ID %s\n" % self.TTNclientID)
            # create new instance, clean session save client init info?
            self.TTNclient = mqttClient.Client(self.TTNclientID, clean_session=True)
            self.TTNclient.username_pw_set(self.broker["user"], password=self.broker["password"])    # set username and password
            self.TTNclient.on_connect = self._on_connect        # attach function to callback
            self.TTNclient.on_message = self._on_message        # attach function to callback
            self.TTNclient.on_disconnect = self._on_disconnect  # attach function to callback
            for cnt in range(3):
                try:
                    self.TTNclient.connect(self.broker["address"], port=self.broker["port"], keepalive=self.KeepAlive) # connect to broker
                    break
                except Exception as e:
                    self.logger("INFO \n%s ERROR Try to connect failed to %s with error: %s\n" % (datetime.datetime.now().strftime("%m-%d %Hh%Mm:"),self.broker["address"], str(e)))
                    if cnt >= 2:
                        self.logger("FATAL Giving up.\n")
                        exit(1)
        else:
            self.TTNclient.reinitialise()
            if self.verbose:
                self.logger("INFO Reinitialize TTN MQTT client\n")
        return True
    
    def TTNstart(self):
        if self.TTNconnected: return True
        self.TTNconnected = False
        if not self.TTNclient:
            self.TTNinit()
        else: self.TTNclient.reinitialise(client_id=self.TTNclientID)
        cnt = 0
        if self.verbose:
            self.logger("INFO Starting up TTN MQTT client.\n")
        self.TTNclient.loop_start()
        time.sleep(0.1)
        while self.TTNconnected != True:    # Wait for connection
            if cnt > 250:
                if self.verbose:
                    self.logger("FAILURE waited for connection too long.\n")
                self.TTNstop()
                return False
            if self.verbose:
                if not cnt:
                    self.logger("INFO Wait for connection\n")
                elif (cnt%10) == 0:
                    if self.logger == sys.stdout.write:
                        sys.stdout.write("\033[F") #back to previous line 
                        sys.stdout.write("\033[K") #clear line 
                    self.logger("INFO Wait for connection % 3.ds\n"% (cnt/10))
            cnt += 1
            time.sleep(0.1)
        self.TTNclient.subscribe(self.broker['topic'])
        if self.verbose:
            self.logger("INFO TTN MQTT client started\n")
        return True
    
    def TTNstop(self):
        if not self.TTNclient: return
        if self.verbose: self.logger("ERROR STOP TTN connection\n")
        try:
            self.TTNclient.loop_stop()
            self.TTNclient.disconnect()
        except: pass
        self.TTNconnected = False
        self.TTNclient = None  # renew MQTT object class
        time.sleep(60)

MQTTindx = None
# find brokers who need to be (re)started up
def MQTTstartup(MQTTbrokers,verbose=False,keepalive=180,logger=None):
    global MQTTindx
    brokers = MQTTbrokers
    if not type(brokers) is list: brokers = [brokers] # single broker
    for indx in range(len(brokers)-1,-1,-1):
      broker = brokers[indx]
      if not broker or not type(broker) is dict:
        del brokers[indx]
        continue
      if not 'fd' in broker or broker['fd'] == None: # initialize
        broker['fd'] = None      # class object handle
        broker['restarts'] = 0   # nr of restarts with timing of 60 seconds
        broker['startTime'] = 0  # last time started
        broker['polling'] = 1    # number of secs to delay check for data
        broker['waiting'] = 0    # last time record
      if not broker['fd']:
        broker['fd'] = TTN_broker(broker, verbose=verbose, keepalive=keepalive, logger=logger)
      if not broker['fd']:
        logger("ERROR Unable to initialize TTN MQTT class for %s\n" % str(broker))
        del MQTTbrokers[indx]
        continue
      if not broker['fd'] or not broker['fd'].TTNstart():
        logger("FATAL Unable to initialize TTN MQTT connection: %s.\n" % str(broker))
        del MQTTbrokers[indx]
      elif not broker['startTime']:
        broker['waiting'] = broker['startTime'] = time.time()
      MQTTindx = -1
    if not len(brokers): return False
    return True

# stop a broker or a list of brokers
def MQTTstop(MQTTbrokers):
    brokers = MQTTbrokers
    if not type(brokers) is list: brokers = [brokers]
    for broker in brokers:
      try:
        broker['fd'].TTNstop(); broker['fd'] = None
      except: pass

# get a record from an MQTT broker eg TTN
#     verbose: verbosity, keepalive: keep connect,
#     logger: fie to lo, sec2pol: wait on record
def GetData(MQTTbrokers, verbose=False,keepalive=180,logger=None, sec2pol=10):
    global MQTTindx
    timing = time.time()
    while True:
      # find brokers who are disconnected
      if not type(MQTTbrokers) is list: MQTTbrokers = [MQTTbrokers]
      for broker in MQTTbrokers:
        if not broker or len(broker) < 2: continue
        try:
          if not broker['fd'].TTNConnected:
            broker['fd'].MQTTStop()
            broker['fd'] = None
        except:
          if not type(broker) is dict:
            raise ValueError("Undefined broker %s" % str(broker))
          broker['fd'] = None
      if not len(MQTTbrokers) or not MQTTstartup(MQTTbrokers,verbose=verbose,keepalive=keepalive,logger=logger):
        raise IOError("FATAL no MQTT broker available")
      if MQTTindx == None: MQTTindx = -1
      now = time.time()

      # try to find a (next) queue with a data record
      for nr in range(len(MQTTbrokers)):
        MQTTindx = (MQTTindx+1)%len(MQTTbrokers)
        broker = MQTTbrokers[MQTTindx]
        try:
          if len(broker['fd'].RecordQueue):
            broker['waiting'] = now
            with broker['fd'].QueueLock: record = broker['fd'].RecordQueue.pop(0)
            return record
        except: pass

      # no record found, reset dying connections, delete dead connections
      ToBeRestarted = (0,None,-1) # (minimal wait time, broker)
      for nr in range(len(MQTTbrokers)):
        MQTTindx = (MQTTindx+1)%len(MQTTbrokers)
        broker = MQTTbrokers[MQTTindx]
        try:
            if len(broker['fd'].RecordQueue): continue
        except: pass

        # CONNECTED broker
        if broker['fd'].TTNConnected:
          # there was no record in the record queue
          if (now - broker['waiting'] > 20*60) and (now - broker['startTime'] > 45*60):
            logging("ERROR Waiting too long for data from broker %s. Stop connection." % str(broker))
            broker['fd'].TTNStop()
            del MQTTbrokers[MQTTindx]
            # break  # break to while True loop
          if not broker['waiting']: broker['waiting'] = now

        # DISCONNECTED broker
        elif broker['restarts'] <= 3: # try simple restart
            logging("ERROR: %s: Connection died. Try again.\n" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            broker['fd'].TTNstop()
            if now-broker['startTime'] > 15*60: # had run for minimal 5 minutes
              broker['restarts'] = 0
              broker['fd'] = None
              broker['waiting'] = now
              # break # break to while True loop
            else:
              broker['restarts'] += 1  # try again and delay on failure
              broker['waiting'] = now
        else:
            logging("ERROR: %s: Too many restries on broker %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S",str(broker))))
            broker['fd'].TTNstop()
            broker['fd'] = None
            broker = {}

        if not ToBeRestarted[1]:
          ToBeRestarted = (broker['waiting'],broker,MQTTindx)
        elif broker['waiting'] < ToBeRestarted[0]:
          ToBeRestarted = (broker['waiting'],broker,MQTTindx)
      
      if ToBeRestarted[1]:
        if verbose:
          if int(time.time()-timing) and logger == sys.stdout.write:
            sys.stdout.write("\033[F") #back to previous line 
            sys.stdout.write("\033[K") #clear line 
          logger("Waiting %3d secs +%3d secs.\n" % (time.time()-timing,max(ToBeRestarted[1]['waiting'] - now,sec2pol)))
        time.sleep(max(ToBeRestarted[1]['waiting'] - now,sec2pol))
        MQTTindx = ToBeRestarted[2]-1
      else:
        if verbose:
          if int(time.time()-timing) and logger == sys.stdout.write:
            sys.stdout.write("\033[F") #back to previous line 
            sys.stdout.write("\033[K") #clear line 
          logger("Awaiting %3d  secs +%3d secs.\n" % (time.time()-timing,sec2pol))
        time.sleep(sec2pol)
      # and try again in the while True loop

if __name__ == '__main__':
    # show full received TTN MQTT record foir this pattern
    show = None
    node = '+'          # TTN MQTT pattern for subscription device topic part
    user = "201802215971az"        # Connection username
    verbose = False
    logger = sys.stdout.write      # routine to print messages to console
    # Connection password
    password = "ttn-account-v2.GW3msa6kBNZs0jx4aXYCcbPaK6r0q9iSfZjIOB2Ixts"
    keepalive = 60      # to play with keepalive connection settings
    
    for arg in sys.argv[1:]:
        if arg  in ['-v','--verbode']:
            verbose = True; continue
        Match = re.match(r'(?P<key>verbose|show|node|user|password|keepalive)=(?P<value>.*)', arg, re.IGNORECASE)
        if Match:
            Match = Match.groupdict()
            if Match['key'].lower() == 'verbose':
                if Match['value'].lower() == 'false': verbose = False
                elif Match['value'].lower() == 'true': verbose = True
            elif Match['key'].lower() == 'show': show = re.compile(Match['value'], re.I)
            elif Match['key'].lower() == 'node':
                if node == '+': node = Match['value']
                else: node += ',' + Match['value']
            elif Match['key'].lower() == 'user': user = Match['value']
            elif Match['key'].lower() == 'password': password = Match['value']
            elif Match['key'].lower() == 'keepalive':
                if Match['value'].isdigit(): keepalive = int(Match['value'])
    
    # TTN MQTT broker access details
    topics = []
    for topic in node.split(','):
        topics.append(("+/devices/" + topic + "/up",0))
    TTNbroker = {
        "address": "eu.thethings.network",  # Broker address
        "port":  1883,                      # Broker port
        "user":  user,                      # Connection username
                                            # Connection password
        "password": password,
        "topic": (topics[0][0] if len(topics) == 1 else topics), # topic to subscribe to
    }
    MQTTbrokers = [ TTNbroker, ]

    while True:
      try:
        DataRecord = GetData(MQTTbrokers,verbose=verbose,keepalive=keepalive,logger=sys.stdout.write) 
        if DataRecord:
          print("%s: received data record: %s" % (datetime.datetime.now().strftime("%m-%d %Hh%Mm%Ss"),str(DataRecord['dev_id'])))
          if show and show.match(DataRecord['dev_id']):
            print("%s" % str(DataRecord))
        else:
          print("No data record received. Try again.")
      except Exception as e:
        print("End of get data record with exception: %s" % str(e))
        break
    MQTTstop(MQTTbrokers)
    exit(0)
