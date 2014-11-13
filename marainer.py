#!/usr/bin/env python

__author__ = 'ube'

import os
from daemon import runner
import serial
from math import radians, cos, sin, asin, sqrt
import sqlite3
import time
import configparser

class Marainer():
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/tty'
        self.stderr_path = '/dev/tty'
        self.pidfile_path = '/tmp/marainer.pid'
        self.pidfile_timeout = 5
        ini = configparser.ConfigParser()
        home = os.path.expanduser("~")
        inifiles = ["/etc/marainer/marainer.ini", home+"/.config/marainer.ini",
                    home+"/.marainer/marainer.ini", "marainer.ini"]

        for ifile in inifiles:
            if os.path.isfile(ifile):
                inifile = ifile
        ini.read(inifile)
        self.dbfile = ini['main']['db']
        self.lockonstart = ini['main']['lockonstart']


    def run(self):
        db = sqlite3.connect(self.dbfile)
        c = db.cursor()
        config = {}
        updateTime = int(time.time())
        c.execute("select * from config")
        dbconf = c.fetchall()
        for conf in dbconf:
            config[conf[0]] = conf[1]
        allowedDiff = float(config['allowedDiff'])
        s = serial.Serial(config['serialPort'], int(config['serialSpeed']), timeout=1)

        while True:  # Wait for data
            if time.time() - updateTime > int(config['updateConfig']) and int(config['updateConfig']):
                updateTime = time.time()
                c.execute("select * from config")
                dbconf = c.fetchall()
                for conf in dbconf:
                    config[conf[0]] = conf[1]
                allowedDiff = float(config['allowedDiff'])
            if s.inWaiting():
                data = s.readline()
                if data.startswith("$GPRMC"):
                    t = time.time()
                    a = data.strip().split(",")
                    if len(a) != 13:
                        continue
                    latPrefix = ""
                    lonPrefix = ""
                    valid = False
                    if a[2] == "A":
                        valid = True
                    if a[4] == "S":
                        latPrefix = "-"
                    if a[6] == "W":
                        lonPrefix = "-"
                    if valid:
                        lat = round(float(a[3][:2]) + (float(a[3][2:]) * 60 / 3600), 6)
                        lon = round(float(a[5][:3]) + (float(a[5][3:]) * 60 / 3600), 6)
                        if int(config['lock']) or self.lockonstart:
                            c.execute("update config set value = '%f' where key = 'lockLat'" % lat)
                            c.execute("update config set value = '%f' where key = 'lockLon'" % lon)
                            c.execute("update config set value = '0' where key = 'lock'" )
                            config['lock'] = "0"
                            self.lockonstart = False
                            db.commit()
                        c.execute("select * from location")
                        diff = self.haversine(lon, lat, float(config['lockLon']), float(config['lockLat']))
                        if diff > allowedDiff and int(config['armed']):
                            url = "http://maps.google.com/maps?z=12&t=m&q=loc:%s%f+%s%f" % (latPrefix, lat,
                                                                                            lonPrefix, lon)
                            c.execute("insert into alarm (time, lon, lat, url, ack) values (%d, %f, %f, '%s', 0)"§
                                      % (t, lon, lat, url))
                        c.execute("update location set lon = %f, lat = %f, time = %d" % (lon, lat, time.time()))
                        db.commit()
                    time.sleep(float(config['interval']))

    def haversine(self,lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        m = 6367000 * c
        return m


app = Marainer()
daemon_runner = runner.DaemonRunner(app)
daemon_runner.do_action()