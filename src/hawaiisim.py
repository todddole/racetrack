#!/usr/bin/env python3

# Changelog
# V0.1 February 1
#
# V0.8 February 9, :
#   Pull athlete info from DB
#   Set up and start race
#   Plot graph of race
#   Implemented Swim, T1, Bike, T2
#
# V 0.9 February 10:
#   Implemented Run, Finish
#   Moved athlete start to separate thread
#   Output race results to CSV file
#
# V 0.95 February 10:
#   Implemented API reporting to racecollector
#   Added race numbers to athletes
#   Initial data reporting on race start, t1, bike start, t2, run start, finish
#   Bug fix - T1 and T2 time was not being recorded properly
#
# V 0.97
#   Corrected API Calls
#   Implemented DNF Reporting
#   Implemented Timing Mat reporting for bike and run
#
# V 1.0
#   Implemented Location Reporting
#
# V 1.1
#   Improved Location Reporting - includes device id and time stamp as fields, shorter _id
#   Added race categories and separate starts for MPRO, FPRO
#   Improved ApiReporter to include priority
#
# V1.2
#   Bug Fixes
#   Reconfigured location reporting to prevent buildup of api calls
#
# V1.21
#   Added race start time to the database
#
# V1.22
#   Added bike and run course adjustment to race times -- times were too fast
#   Updated location data collection:
#      Pros now update every time
#      AG athletes now update less frequently when queue times are longer
#      Added logging of queue sizes individually to easier check status
#      Added an environment variable to set the race start time to a particular time of day
#      Updated logging config to log to both file and console for now
#      Bug fix: Corrected windfactor and heatfactor calculations
#      Added constants file, moved most of the course definitions to constants
#      Bug fix: priority was getting dropped
#
# V1.23
#   Faster Transitions for pros


from components.LocationDataGateway import LocationDataGateway
from components.Athlete import Athlete
import os
import random
import json
from collections import namedtuple
import logging
from dotenv import load_dotenv
import time
from geopy import distance
import math
import numpy as np
import pandas as pd
from shapely.geometry import Point
from threading import Thread

import geopandas as gpd
import matplotlib.pyplot as plt
import datetime
from queue import Queue
import requests
import urllib.parse
from components.constants import *



race = None
#----- Local Constants

#Speedfactor - Reduces sleep times by this amount.  60 = cycles 1 hour of race time per 1 minute real time
SPEEDFACTOR = 1
LOGLEVEL = logging.INFO
SHOWPLT = False
DEFAULT_API_URL = "http://localhost:5000/data/"
DEFAULT_API_KEY = "youareanironman"
REPORT_WORKER = 15

#----- Global Variables
device_count={}
class ApiReporter(Thread):
    # Maintains a high priority and low priority queue
    # Accepts data on queues for transmission to rest api
    # transmits data from queue
    def setup(self, api_url, api_key):
        self.q = Queue()
        self.pq = Queue()
        self.finished = False
        self.api_url = api_url
        self.api_key = api_key

    def add(self, item, priority=False):
        if (priority==True):
            self.pq.put(item)
        else:
            self.q.put(item)

    def finish(self):
        self.finished = True
    def run(self):
        while (not self.finished) or (not self.q.empty()) or (not self.pq.empty()):
            if (not self.pq.empty()):
                item = self.pq.get()
            elif (not self.q.empty()):
                item = self.q.get()
            else:
                time.sleep(0.1)
                continue

            key = item["key"]
            data = item["data"]
            try:
                url=self.api_url+key+"/"

                response = requests.post(url, data=json.dumps(data),
                                         headers={"Content-Type":"application/json"})
                if response.status_code != 201:
                    logging.debug("Api error: Post Status Code " + str(response.status_code))
                    logging.debug("  URL: " + url)
                    logging.debug("  json: " + str(data))

                    # put item back on queue so data doesn't get lost
                    self.pq.put(item)
            except Exception as e:
                logging.debug("Api exception!!")

class DataReporter(Thread):
    # Passes data to ApiReporters for transmission to API
    def setup(self, myrace, api_url, api_key):
        self.srace = myrace
        self.q = Queue()
        self.pq = Queue()
        self.finished = False
        self.api_url = api_url
        self.api_key = api_key
        self.threadlist = []

    def report(self, item, priority=False):
        if (priority):
            self.pq.put(item)
        else:
            self.q.put(item)

    def queuesize(self):
        qsize = 0
        for i in self.threadlist:
            qsize+=i.q.qsize() + i.pq.qsize()
        return qsize

    def logqsizes(self):
        qsizelist = "  Queue Sizes: "
        for i in self.threadlist:
            qsizelist+="("+str(i.q.qsize()) + "," + str(i.pq.qsize())+") "
        logging.info(qsizelist)
    def run(self):

        for i in range(REPORT_WORKER):
            self.threadlist.append(ApiReporter())
            self.threadlist[i].setup(self.api_url, self.api_key)
            self.threadlist[i].start()

        whichthread = 0
        while (not self.finished) or (not self.pq.empty()) or (not self.q.empty()):
            newpriority = False
            if (not self.pq.empty()):
                item = self.pq.get()
                newpriority = True
            elif (not self.q.empty()):
                item = self.q.get()
            else:
                time.sleep(1)
                continue

            # we should have an item, process it
            key = item["key"]
            data = { "data": item["data"],
                     "colname" : item["colname"],
                     "api-key" : self.api_key}
            everything = {"key":key, "data":data}
            self.threadlist[whichthread].add(everything, priority=newpriority)
            whichthread += 1
            if (whichthread >= REPORT_WORKER): whichthread = 0

        # Shutdown the worker threads
        for i in range(REPORT_WORKER):
            self.threadlist[i].finish()

    def finish(self):
        self.finished = True


class RaceStarter(Thread):
    # Signals athletes to start race
    # Pro Men start first in a mass start
    # Pro Women start second in a mass start 10 minutes later
    # Age group athletes start 10 minutes later in a rolling start, one athlete per startinterval seconds

    def setup(self, myrace):
        self.srace = myrace
    def run(self):
        # Start all the MPRO
        if (self.srace.promcount>0):
            logging.info("Starting the Pro Men Race!")
            for i in range(self.srace.promcount):
                count = 0
                while (self.srace.athletelist[count].division != 'MPRO'): count+=1
                athlete = self.srace.athletelist.pop(count)
                athlete.start()
                self.srace.racinglist.append(athlete)

                self.srace.started += 1

            time.sleep(10*60/SPEEDFACTOR)

        # Start all the FPRO
        if (self.srace.profcount>0):
            logging.info("Starting the Pro Women Race!")
            for i in range(self.srace.profcount):
                count = 0
                while (self.srace.athletelist[count].division != 'FPRO'): count += 1
                athlete = self.srace.athletelist.pop(count)
                athlete.start()
                self.srace.racinglist.append(athlete)

                self.srace.started += 1

            time.sleep(10 * 60 / SPEEDFACTOR)

        if (self.srace.athletecount>0):
            logging.info("Starting the Age Groupers!")

        while len(self.srace.athletelist) > 0:
            athlete = self.srace.athletelist.pop()
            athlete.start()
            self.srace.racinglist.append(athlete)


            self.srace.started += 1
            if (SPEEDFACTOR!=9999):
                time.sleep(self.srace.startinterval / SPEEDFACTOR)

def show_map():
    dlist = []
    for athlete in race.racinglist:
        df2 = {'name': athlete.name, 'latitude': athlete.location[0], 'longitude': athlete.location[1]}
        dlist.append(df2)

    df = pd.DataFrame(dlist)

    crs = {'init': 'epsg:4326'}
    geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
    geo_df = gpd.GeoDataFrame(df,
        crs = crs,
        geometry = geometry)

    geo_df.plot(column = 'name')
    plt.ylim(19.58, 20.25)
    plt.xlim(-156.1, -155.80)

    plt.show()

def get_bearing(point1, point2):
    # copied from google search
    # gives an approximate bearing between two locations
    # seems to be slightly inaccurate

    lat1, lon1 = point1[0], point1[1]
    lat2, lon2 = point2[0], point2[1]

    DL = lon2 - lon1
    X = math.cos(lat2) * math.sin(DL)
    Y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(DL)
    brng = np.rad2deg(math.atan2(X, Y))



    if brng < 0: brng+= 360
    return brng

def move_along(point1, point2, met_dist):
    # returns a point in between point1 and point 2, met_distance from point 1
    bearing = get_bearing(point1, point2)
    newloc = distance.distance(meters=met_dist).destination(point1, bearing)
    return newloc

def customAthleteDecoder(athleteDict):
    return namedtuple('X', athleteDict.keys())(*athleteDict.values())

def get_div(division, birthdate, gender):
    # returns the triathlon division for an athlete
    # eg MPRO, FPRO, M35-39, F18-24
    if (division == "MPRO") or (division == "FPRO"):
        return division
    birthyear = int(birthdate.split("/")[2])
    thisyear = int(datetime.date.today().year)
    raceage = thisyear - birthyear

    ourdiv = "F"
    if (gender == 'male'):
        ourdiv = 'M'
    if raceage < 25:
        ourdiv += '18-24'
    elif raceage < 30:
        ourdiv += '25-29'
    elif raceage < 35:
        ourdiv += '30-34'
    elif raceage < 40:
        ourdiv += '35-39'
    elif raceage < 45:
        ourdiv += '40-44'
    elif raceage < 50:
        ourdiv += '45-49'
    elif raceage < 55:
        ourdiv += '50-54'
    elif raceage < 60:
        ourdiv += '55-59'
    elif raceage < 65:
        ourdiv += '60-64'
    elif raceage < 70:
        ourdiv += '65-69'
    elif raceage < 75:
        ourdiv += '70-74'
    elif raceage < 80:
        ourdiv += '75-79'
    else:
        ourdiv += '80+'
    return ourdiv


class RaceAthlete(Athlete):
    def __str__(self):
        outstr = ""
        outstr += str(self.racenum)
        outstr += ","
        outstr += self.name
        outstr += ","
        outstr += get_div(self.division, self.birthdate, self.gender)
        # Status and finish time
        outstr += ","
        outstr += str(self.status)

        outstr += ","
        outstr += str(datetime.timedelta(seconds=self.swimsec + self.t1sec + self.bikesec + self.t2sec + self.runsec))

        outstr += ","
        outstr += str(datetime.timedelta(seconds=self.swimsec))
        outstr += ","
        outstr += str(datetime.timedelta(seconds=self.t1sec))
        outstr += ","
        outstr += str(datetime.timedelta(seconds=self.bikesec))
        outstr += ","
        outstr += str(datetime.timedelta(seconds=self.t2sec))
        outstr += ","
        outstr += str(datetime.timedelta(seconds=self.runsec))
        outstr += ","
        outstr += str(self.location[0])
        outstr += ","
        outstr += str(self.location[1])

        return outstr


    def __init__(self, *args):
        Athlete.__init__(self, *args)
        global race
        if (self.gender=='male'):
            swimrec = race.swimrecmale
            bikerec = race.bikerecmale
            runrec = race.runrecmale
        else:
            swimrec = race.swimrecfemale
            bikerec = race.bikerecfemale
            runrec = race.runrecfemale
        swimcut = race.swimcut


        swimtimepct = 1 - (self.swimstr / 100) + random.uniform(-.07, 0.03)
        swimtime = ((swimcut - swimrec) * swimtimepct) + swimrec
        self.swimspd = 3800 / swimtime

        bikecut = race.bikecut

        bikecourseadjust = 1.03 # factor due to bike course being slightly off
        biketimepct=1 - (self.bikestr / 100) + random.uniform(-.07, 0.03) * (1/race.windfactor) * bikecourseadjust
        biketime = ((bikecut - bikerec) * biketimepct) + bikerec
        self.bikespd = 180000 / biketime


        runcut = (60*60*8)
        runcourseadjust = 1.02 #factor due to run course distance being slightly off
        runtimepct = 1 - (self.runstr / 100) + random.uniform(-.07, 0.03) * (1/race.heatfactor) * runcourseadjust
        runtime = ((runcut - runrec) * runtimepct) + runrec
        self.runspd = 42000 / runtime

        self.location = race.swimcrs[0]

        self.racenum = 0

        self.status = 0
        self.starttime = None
        self.leg = 0
        self.locdatarecord = {}

    def start(self):
        self.status = 1
        self.starttime = time.time()
        self.swimsec = 0
        self.bikesec = 0
        self.runsec = 0
        self.t1sec = 0
        self.t2sec = 0
        race.swimmers += 1

        logging.debug("Race Start: " + self.name + " has entered the water! " + str(len(race.athletelist)) + " to go")
        race.report_data(str(self.racenum), str(time.time()), priority=True, extraname="-RaceStart")

    def set_racenum(self, racenum):
        self.racenum = racenum

    def start_run(self):
        self.status=5
        self.leg=0
        self.location = race.runcrs[0]
        logging.debug("Run Start: " + self.name + " has entered the bike course!")
        race.t2ers -= 1
        race.runners += 1
        race.report_data(str(self.racenum), str(time.time()), priority=True, extraname="-RunStart")

    def start_bike(self):
        self.status=3
        self.leg = 0
        self.location = race.bikecrs[0]
        logging.debug("Bike Start: " + self.name + " has entered the bike course!")
        race.t1ers -=1
        race.bikers += 1
        race.report_data(str(self.racenum), str(time.time()), priority=True, extraname="-BikeStart")

    def finish(self, addtime):
        self.status = 10
        self.leg = 0
        self.runsec += addtime
        logging.info (race.race_timestamp() + " -- " +
                      self.name + ", you are an IRONMAN!!!  "+
                      str(datetime.timedelta(seconds=(self.swimsec + self.bikesec + self.runsec +
                                                      self.t1sec + self.t2sec))))
        race.runners -= 1
        race.finishers += 1
        race.report_data(str(self.racenum), str(time.time()), priority=True, extraname="-RaceFinish")


    def transition_One(self, addtime):
        self.status = 2
        self.leg = 0
        self.t1sec = addtime
        t1max = 150 if self.division in ["MPRO", "FPRO"] else 600
        self.t1left = random.randint(90,t1max) - addtime
        logging.debug("Swim Finish: " + self.name + " is out of the water! "+str(self.swimsec // 60) + ":"+str(self.swimsec % 60) + " -- swim str = " + str(self.swimstr))
        race.swimmers -= 1
        race.t1ers +=1
        race.report_data(str(self.racenum), str(time.time()), priority=True, extraname="-EnterT1")

    def transition_Two(self, addtime):
        self.status = 4
        self.leg = 0
        self.t2sec = addtime
        t2max = 150 if self.division in ["MPRO", "FPRO"] else 600
        self.t2left = random.randint(90, t2max) - addtime
        logging.debug("Bike Finish: " + self.name + " is off the bike! " + str(self.bikesec // 60) + ":" + str(
            self.bikesec % 60) + " -- bike str = " + str(self.bikestr))
        race.bikers -= 1
        race.t2ers += 1
        race.report_data(str(self.racenum), str(time.time()), priority=True, extraname="-EnterT2")

    def DNF(self, reason):
        self.status=99
        logging.info(reason)
        race.report_data(str(self.racenum), str(time.time()), priority=True, extraname="-DNF")
        race.dnfers += 1

    def report_location(self):
        key = urllib.parse.quote_plus(self.deviceid) + str(device_count[self.deviceid])
        device_count[self.deviceid] = device_count[self.deviceid]+1
        data = {"dev": self.deviceid, "time":str(time.time()), "la":str(self.location[0]), "lo":str(self.location[1]), "nl":"[]"}
        if (self.division=='MPRO') or (self.division=='FPRO'):
            race.report_data(key, data, priority=True, extraname="-locations")
            return

        self.locdatarecord[key]=data
        sizefactor=2
        if (race.qsize) > 50 and (race.qsize)< 200: sizefactor=5
        elif (race.qsize) < 500: sizefactor=10
        else: sizefactor=20
        if (len(self.locdatarecord)>=sizefactor) and (random.randint(1,2)==2):
            race.report_data("multipart", self.locdatarecord, priority=False, extraname="-locations")
            self.locdatarecord={}


    def advance(self, cycletime):

        nearbylist = []
        if (self.status==5):
            if (random.randint(1,8000) == 8000):
                self.DNF(race.race_timestamp() + " -- " + self.name +
                             " has bonked and decided to throw in the towel!!")
                race.runners-=1
                return 99

            # running, update position
            speedrandom = random.uniform(.9, 1.1)
            met_distance = self.runspd * speedrandom * cycletime

            rundone = False
            addtime = cycletime
            origmetdistance = met_distance

            while (met_distance>0) and (not rundone):
                # check distance of next waypoint
                legdist = distance.distance(self.location, race.runcrs[self.leg+1]).m


                if (legdist < met_distance):
                    legtime = int(cycletime * (legdist / origmetdistance))
                    addtime -= legtime
                    self.runsec += legtime
                    met_distance -= legdist
                    self.location = race.runcrs[self.leg+1]
                    self.leg+=1
                    logging.debug(self.name + " finished run leg " + str(self.leg))

                    if (self.leg in race.runtm):
                        # Crossed a timing mat, report it
                        myindex = race.runtm.index(self.leg) + 1
                        race.report_data(str(self.racenum), str(time.time() -addtime), priority = True, extraname="-RunTM" + str(myindex))

                    if (self.leg==len(race.runcrs) -1):
                        rundone = True
                        self.finish(addtime)
                        return 99


                else:
                    self.runsec += addtime
                    newloc = move_along(self.location, race.runcrs[self.leg+1], met_distance)

                    #logging.info(self.name + " moved from " + str(self.location) + " to " + str(newloc))
                    self.location = newloc
                    met_distance = 0
                    if (self.swimsec + self.bikesec + self.runsec + self.t1sec + self.t2sec > race.racecut):
                        # missed the cutoff, pull them out
                        self.DNF(race.race_timestamp() + " -- " +
                                     self.name + " failed to finish before midnight." + " -- run str = " + str(self.runstr))
                        race.runners-=1
                        return 99

        elif (self.status==4):
            self.t2left -= cycletime
            self.t2sec += cycletime
            if (self.t2left <= 0):
                self.start_run()

        elif (self.status==3):
            if (random.randint(1,10000) == 10000):
                self.DNF(race.race_timestamp() + " -- " +
                             self.name + " was in a brutal accident and has dropped out!!")
                race.bikers-=1
                return 99

            # biking, update position
            speedrandom = random.uniform(.9, 1.1)
            met_distance = self.bikespd * speedrandom * cycletime

            bikedone = False
            addtime = cycletime
            origmetdistance = met_distance

            while (met_distance>0) and (not bikedone):
                # check distance of next waypoint
                legdist = distance.distance(self.location, race.bikecrs[self.leg+1]).m


                if (legdist < met_distance):
                    legtime = int(cycletime * (legdist / origmetdistance))
                    addtime -= legtime
                    self.bikesec += legtime
                    met_distance -= legdist
                    self.location = race.bikecrs[self.leg+1]
                    self.leg+=1
                    logging.debug(self.name + " finished leg " + str(self.leg))
                    if (self.leg in race.biketm):
                        # Crossed a timing mat, report it
                        myindex = race.biketm.index(self.leg) + 1
                        race.report_data(str(self.racenum), str(time.time() -addtime), priority=True, extraname="-BikeTM" + str(myindex))

                    if (self.leg==len(race.bikecrs) -1):
                        bikedone = True
                        self.transition_Two(addtime)


                else:
                    self.bikesec += addtime
                    newloc = move_along(self.location, race.bikecrs[self.leg+1], met_distance)

                    #logging.info(self.name + " moved from " + str(self.location) + " to " + str(newloc))
                    self.location = newloc
                    met_distance = 0
                    if (self.bikesec > race.bikecut):
                        # missed the cutoff, pull them out
                        self.DNF(race.race_timestamp() + " -- " +
                                     self.name + " failed to make the bike cutoff, joined the sag wagon!!" + " -- bike str = " + str(self.bikestr))
                        race.bikers-=1
                        return 99

        elif (self.status==2):
            self.t1left -= cycletime
            self.t1sec += cycletime
            if (self.t1left <= 0):
                self.start_bike()


        elif (self.status==1):
            if (random.randint(1,8000) == 8000):
                self.DNF(race.race_timestamp() + " -- " +
                             self.name + " was eaten by a shark!!")
                race.swimmers-=1
                return 99

            # swimming, update position
            speedrandom = random.uniform(.9, 1.1)
            met_distance = self.swimspd * speedrandom * cycletime

            swimdone = False
            addtime = cycletime
            origmetdistance = met_distance

            while (met_distance>0) and (not swimdone):
                # check distance of next waypoint


                legdist = distance.distance(self.location, race.swimcrs[self.leg+1]).m


                if (legdist < met_distance):
                    legtime = int(cycletime * (legdist / origmetdistance))
                    addtime -= legtime
                    self.swimsec += legtime
                    met_distance -= legdist
                    self.location = race.swimcrs[self.leg+1]
                    self.leg+=1
                    logging.debug(self.name + " finished leg " + str(self.leg))
                    if (self.leg==len(race.swimcrs) -1):
                        swimdone = True
                        self.transition_One(addtime)


                else:
                    self.swimsec += addtime
                    newloc = move_along(self.location, race.swimcrs[self.leg+1], met_distance)

                    #logging.info(self.name + " moved from " + str(self.location) + " to " + str(newloc))
                    self.location = newloc
                    met_distance = 0
                    if (self.swimsec > race.swimcut):
                        # missed the cutoff, pull them out
                        self.DNF(race.race_timestamp() + " -- " +
                                     self.name + " failed to make the swim cutoff, pulled out of the water!!" + " -- swim str = " + str(self.swimstr))
                        race.swimmers -= 1
                        return 99

        if (self.status>=10):
            return 99

        #report position
        self.report_location()

        return self.status






class Race:
    def __init__(self):
        self.qsize=0
        self.swimmers = 0
        self.bikers = 0
        self.runners=0
        self.finishers = 0
        self.dnfers = 0
        self.t1ers = 0
        self.t2ers = 0
        self.rtime = 0

        self.swimcrs = SWIMCRS

        self.bikecrs = BIKECRS

        self.biketm=[300, 600, 900, 1200]

        self.runcrs = RUNCRS

        self.runtm = RUN_TIME_MATS

        self.startinterval = 6

        self.swimrecmale = 2789
        self.swimrecfemale = 2894
        self.swimcut = (60*60*2) + (60*30)

        self.bikerecmale = (60*60*4) + (60*4) + 36
        self.bikerecfemale = (60*60*4) + (60*26) + 7
        self.bikecut = (60*60*8)

        self.runrecmale = (60*60*2) + (60*36) + 15
        self.runrecfemale = (60*60*2) + (60*48) + 23
        self.racecut = (60*60*17)

        self.windfactor = random.uniform(0.9, 1.02)
        self.heatfactor = random.uniform(0.9, 1.02)

        self.datareporter = DataReporter()

        data_url = os.getenv("API_URL", DEFAULT_API_URL)
        api_key = os.getenv("API_KEY", DEFAULT_API_KEY)

        self.datareporter.setup(self, data_url, api_key)
        self.datareporter.start()

        self.raceid = str(datetime.date.today())
        ldg = LocationDataGateway()
        count = 1
        racelist = ldg.get_all_data("racelist")


        racenums = []
        for r in racelist:
            radd=r["data"]
            racenums.append(radd["data"])

        while (self.raceid + "-" + str(count) in racenums):
            count+=1

        self.raceid = self.raceid + "-" + str(count)

        self.report_data(str(len(racelist)+1), {"data": self.raceid}, colname="racelist")


        try:
            self.athletecount = int(os.environ.get("ATH_COUNT"))
            self.promcount = int(os.environ.get("PROM_COUNT"))
            self.profcount = int(os.environ.get("PROF_COUNT"))
        except:
            self.athletecount = 5
            self.promcount = 0
            self.profcount = 0




        self.athletelist = []
        self.started = 0

    def report_data(self, key, data, colname="race", priority=True, extraname = ""):
        if (colname=="race"):
            colname += self.raceid
        colname += extraname

        item = {"key": key,
                "data": data,
                "colname": colname}
        self.datareporter.report(item, priority)

    def setqsize(self):
        self.qsize = self.datareporter.queuesize()

    def logqsize(self):
        self.datareporter.logqsizes()
    def add_athletes(self, athletes):
        self.athletelist = athletes
        racenumlist = {}
        count=1
        for athlete in athletes:
            athlete.set_racenum(count)
            racenumlist[str(count)] = str(athlete.id)
            count+=1
        self.report_data("racenumbers", racenumlist)


    def start_race(self):
        # Wait for the right time of day to start the race
        istime=False
        starttime = os.getenv("START_TIME", "")
        if (starttime==""): istime=True
        else: logging.info("Waiting until " + starttime + " for the race to start...")
        while (not istime):
            now = datetime.datetime.now()
            current_time = now.strftime("%H:%M")
            if (current_time==starttime): istime=True
            time.sleep(5)


        self.starttime = time.time()
        self.isdone = False
        logging.info("Starting race at " + str(self.starttime) + "  windfactor=" + str(self.windfactor) +
                     "  heatfactor=" + str(self.heatfactor))
        self.report_data("starttime", self.starttime)
        self.racinglist = []
        self.finishedlist = []

    def end_race(self):
        self.isdone = True
        self.endtime = time.time()
        logging.info("Ending race at " + str(self.endtime))
        self.datareporter.finish()


    def update_rtime(self, rtime):
        self.rtime = rtime

    def race_timestamp(self):
        return str(datetime.timedelta(seconds=self.rtime))

    def update_status(self, cycletime):
        #logging.info("Race Status Update")
        self.updatetime = time.time()

        # check if athletes have all started


        # advance each athlete
        for ath in self.racinglist:
            if (ath.advance(cycletime)==99):
                # athlete is finished, pop from racinglist
                self.racinglist.remove(ath)
                self.finishedlist.append(ath)

        if (len(self.racinglist)==0):
            self.end_race()






    def is_done(self):
        return self.isdone


def load_athletes(athletecount, promcount, profcount):
    athletes = []
    ldg = LocationDataGateway()
    #athlete_ids = ldg.get_data("athlete_list", "athletes")
    athletelist = ldg.get_all_data("athletes")
    select_aths = []
    prom_aths = []
    prof_aths = []
    for i in athletelist:
        j=json.loads(i["data"])
        if (j["division"] == 'MPRO'):
            prom_aths.append(i)
        elif (j["division"] == 'FPRO'):
            prof_aths.append(i)
        else:
            select_aths.append(i)

    for i in range(promcount):
        #pick a randodom athlete
        ath = prom_aths.pop(random.randint(0,len(prom_aths)-1))
        athid = ath["_id"]
        data = json.loads(ath["data"])
        data["id"] = str(athid)
        #print(data)
        device_count[data["deviceid"]] = 0

        athletes.append(RaceAthlete(data))

    for i in range(profcount):
        #pick a randodom athlete
        ath = prof_aths.pop(random.randint(0,len(prof_aths)-1))
        athid = ath["_id"]
        data = json.loads(ath["data"])
        data["id"] = str(athid)
        #print(data)
        device_count[data["deviceid"]] = 0

        athletes.append(RaceAthlete(data))


    for i in range(athletecount):
        #pick a randodom athlete
        ath = select_aths.pop(random.randint(0,len(select_aths)-1))
        athid = ath["_id"]
        data = json.loads(ath["data"])
        data["id"] = str(athid)
        #print(data)
        device_count[data["deviceid"]] = 0

        athletes.append(RaceAthlete(data))


    return athletes






if __name__ == '__main__':

    load_dotenv()
    logging.basicConfig(
        level=LOGLEVEL,
        handlers=[
            logging.FileHandler("hawaiisim.log"),
            logging.StreamHandler()
        ])
    logging.info('Starting HawaiiSim')

    race = Race()
    cycletime = int(os.environ.get("CYCLE_TIME"))

    race.startinterval = int(os.getenv("START_INTERVAL", 6))
    SPEEDFACTOR = int(os.getenv("SPEED_FACTOR", SPEEDFACTOR))

    logging.info('Loading athletes')
    race.add_athletes(load_athletes(race.athletecount, race.promcount, race.profcount))
    logging.info('Loaded ' + str(len(race.athletelist)) + ' athletes')


    #for ath in race.athletelist:
     #   print(ath.name + ' - Swim Speed:' + str(ath.swimspd) + " m/s")

    race.start_race()

    starter = RaceStarter()
    starter.setup(race)
    starter.start()

    cycles = 0
    rtime = 0

    while (race.started == 0): time.sleep(0.1)

    while not race.is_done():
        update_start = time.time()
        race.update_status(cycletime)
        race.setqsize()



        rtime += cycletime
        race.update_rtime(rtime)

        cycles+=1
        if (cycles % 10 == 0):

            logging.info("" +str(datetime.timedelta(seconds=rtime)) + " --- " +
                         "  Swimmers: " + str(race.swimmers) + "  |  T1: "+str(race.t1ers) +
                         "  |  Bike: " + str(race.bikers) + "  |  T2: " + str(race.t2ers) +
                         "  |  Run: " + str(race.runners) + "  |  Finished: " + str(race.finishers) +
                         "  |  DNF: " + str(race.dnfers) + " Queue Size:" + str(race.qsize))
            race.logqsize()


        if (cycles == 60):
            if (SHOWPLT):
                show_map()
            cycles=0

        if (SPEEDFACTOR!=9999):
            keepwaiting = True
            while (keepwaiting==True):
                update_time = time.time() - update_start
                if (update_time < (cycletime / SPEEDFACTOR)):
                    time.sleep(0.1)
                else:
                    keepwaiting = False



    logging.info("Writing race results to data/raceresults.csv")

    f = open("src/data/raceresults.csv", "w")

    logging.info("Finished List contains " + str(len(race.finishedlist)) + " athletes.")
    for athlete in race.finishedlist:
        f.write(str(athlete))
        f.write("\n")

    f.close()


