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


from src.components.LocationDataGateway import LocationDataGateway
from src.components.Athlete import Athlete
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



race = None
#----- Constants

#Speedfactor - Reduces sleep times by this amount.  60 = cycles 1 hour of race time per 1 minute real time
SPEEDFACTOR = 60
LOGLEVEL = logging.INFO
SHOWPLT = False
DEFAULT_API_URL = "http://localhost:5000/data/"
DEFAULT_API_KEY = "youareanironman"
device_count={}

class ApiReporter(Thread):
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
                time.sleep(1)
                continue

            key = item["key"]
            data = item["data"]
            try:
                url=self.api_url+key+"/"

                response = requests.post(url, data=json.dumps(data),
                                         headers={"Content-Type":"application/json"})
                if response.status_code != 201:
                    logging.error("Api error: Post Status Code " + str(response.status_code))
                    logging.error("  URL: " + url)
                    logging.error("  json: " + str(data))
            except Exception as e:
                logging.error("Api exception!!")

class DataReporter(Thread):
    def setup(self, myrace, api_url, api_key):
        self.srace = myrace
        self.q = Queue()
        self.pq = Queue()
        self.finished = False
        self.api_url = api_url
        self.api_key = api_key

    def report(self, item, priority=False):
        if (priority):
            self.pq.put(item)
        else:
            self.q.put(item)
    def run(self):
        threadlist = []
        for i in range(20):
            threadlist.append(ApiReporter())
            threadlist[i].setup(self.api_url, self.api_key)
            threadlist[i].start()

        whichthread = 0
        while (not self.finished) or (not self.pq.empty()) or (not self.q.empty()):
            if (not self.pq.empty()):
                item = self.pq.get()
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
            threadlist[whichthread].add(everything, )
            whichthread += 1
            if (whichthread > 19): whichthread = 0

        # Shutdown the worker threads
        for i in range(20):
            threadlist[i].finish()

    def finish(self):
        self.finished = True


class RaceStarter(Thread):

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

    lat1, lon1 = point1[0], point1[1]
    lat2, lon2 = point2[0], point2[1]

    DL = lon2 - lon1
    X = math.cos(lat2) * math.sin(DL)
    Y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(DL)
    brng = np.rad2deg(math.atan2(X, Y))



    if brng < 0: brng+= 360
    return brng

def move_along(point1, point2, met_dist):
    bearing = get_bearing(point1, point2)
    newloc = distance.distance(meters=met_dist).destination(point1, bearing)
    return newloc

def customAthleteDecoder(athleteDict):
    return namedtuple('X', athleteDict.keys())(*athleteDict.values())

def get_div(athlete):
    if (athlete.division == 'MPRO') or (athlete.division == 'FPRO'):
        return athlete.division
    birthyear = athlete.birthdate.split('/')[2]
    thisyear = datetime.date.today().year
    raceage = thisyear - birthyear
    if (athlete.gender == 'male'):
        ourdiv = 'M'
    else:
        ourdiv = 'F'
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
        outstr += get_div(self)
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

        biketimepct=1 - (self.bikestr / 100) + random.uniform(-.07, 0.03) * race.windfactor
        biketime = ((bikecut - bikerec) * biketimepct) + bikerec
        self.bikespd = 180000 / biketime


        runcut = (60*60*8)
        runtimepct = 1 - (self.runstr / 100) + random.uniform(-.07, 0.03) * race.heatfactor
        runtime = ((runcut - runrec) * runtimepct) + runrec
        self.runspd = 42000 / runtime

        self.location = race.swimcrs[0]

        self.racenum = 0

        self.status = 0
        self.starttime = None
        self.leg = 0

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
        race.report_data(str(self.racenum), str(time.time()), extraname="RaceStart")

    def set_racenum(self, racenum):
        self.racenum = racenum

    def start_run(self):
        self.status=5
        self.leg=0
        self.location = race.runcrs[0]
        logging.debug("Run Start: " + self.name + " has entered the bike course!")
        race.t2ers -= 1
        race.runners += 1
        race.report_data(str(self.racenum), str(time.time()), extraname="RunStart")

    def start_bike(self):
        self.status=3
        self.leg = 0
        self.location = race.bikecrs[0]
        logging.debug("Bike Start: " + self.name + " has entered the bike course!")
        race.t1ers -=1
        race.bikers += 1
        race.report_data(str(self.racenum), str(time.time()), extraname="BikeStart")

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
        race.report_data(str(self.racenum), str(time.time()), extraname="RaceFinish")


    def transition_One(self, addtime):
        self.status = 2
        self.leg = 0
        self.t1sec = addtime
        self.t1left = random.randint(90,600) - addtime
        logging.debug("Swim Finish: " + self.name + " is out of the water! "+str(self.swimsec // 60) + ":"+str(self.swimsec % 60) + " -- swim str = " + str(self.swimstr))
        race.swimmers -= 1
        race.t1ers +=1
        race.report_data(str(self.racenum), str(time.time()), extraname="EnterT1")

    def transition_Two(self, addtime):
        self.status = 4
        self.leg = 0
        self.t2sec = addtime
        self.t2left = random.randint(90, 600) - addtime
        logging.debug("Bike Finish: " + self.name + " is off the bike! " + str(self.bikesec // 60) + ":" + str(
            self.bikesec % 60) + " -- bike str = " + str(self.bikestr))
        race.bikers -= 1
        race.t2ers += 1
        race.report_data(str(self.racenum), str(time.time()), extraname="EnterT2")

    def DNF(self, reason):
        self.status=99
        logging.info(reason)
        race.report_data(str(self.racenum), str(time.time()), extraname="DNF")
        race.dnfers += 1

    def report_location(self):
        key = urllib.parse.quote_plus(self.deviceid) + str(device_count[self.deviceid])
        device_count[self.deviceid] = device_count[self.deviceid]+1
        data = {"dev": self.deviceid, "time":str(time.time()), "la":str(self.location[0]), "lo":str(self.location[1]), "nl":"[]"}
        race.report_data(key, data, priority=False, extraname="locations")

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
                        race.report_data(str(self.racenum), str(time.time()), extraname="RunTM" + str(myindex))

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
                        race.report_data(str(self.racenum), str(time.time()), extraname="BikeTM" + str(myindex))

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
        self.swimmers = 0
        self.bikers = 0
        self.runners=0
        self.finishers = 0
        self.dnfers = 0
        self.t1ers = 0
        self.t2ers = 0
        self.rtime = 0

        self.swimcrs = [
            (19.639572, -155.995188),
            (19.637690, -155.994440),
            (19.635070, -155.993390),
            (19.628160, -155.990120),
            (19.624510, -155.988290),
            (19.624410, -155.989660),
            (19.639260, -155.996217),
            (19.639377, -155.996689)

        ]

        self.bikecrs = [
            (19.640017, -155.997058),
            (19.64116, -155.99533),
            (19.64118, -155.99537),
            (19.64125, -155.99553),
            (19.64135, -155.99568),
            (19.64144, -155.99581),
            (19.64149, -155.99589),
            (19.64167, -155.9961),
            (19.64185, -155.99632),
            (19.64193, -155.99641),
            (19.64193, -155.9964099),
            (19.64193, -155.99641),
            (19.64186, -155.99645),
            (19.64176, -155.99644),
            (19.6415599, -155.99659),
            (19.64134, -155.99676),
            (19.64124, -155.99685),
            (19.6412, -155.99688),
            (19.6408999, -155.99712),
            (19.64079, -155.9971799),
            (19.64068, -155.9971799),
            (19.64058, -155.99715),
            (19.64051, -155.99712),
            (19.64035, -155.99699),
            (19.64025, -155.9969),
            (19.64025, -155.9968999),
            (19.64025, -155.9969),
            (19.6401499, -155.99684),
            (19.64011, -155.99677),
            (19.64009, -155.99668),
            (19.64009, -155.99655),
            (19.64012, -155.99634),
            (19.6401499, -155.9961099),
            (19.64014, -155.99587),
            (19.64012, -155.9957),
            (19.6400599, -155.99543),
            (19.63983, -155.9948),
            (19.63979, -155.99466),
            (19.63976, -155.99456),
            (19.63972, -155.99449),
            (19.63967, -155.99443),
            (19.63956, -155.99433),
            (19.63939, -155.99417),
            (19.63923, -155.99406),
            (19.63908, -155.99394),
            (19.63899, -155.9938699),
            (19.63886, -155.99381),
            (19.63829, -155.9935099),
            (19.6381, -155.9934),
            (19.63796, -155.99329),
            (19.63784, -155.99317),
            (19.63779, -155.99313),
            (19.63773, -155.99307),
            (19.63766, -155.99299),
            (19.63745, -155.99277),
            (19.6369599, -155.99229),
            (19.63662, -155.9918999),
            (19.63646, -155.99171),
            (19.63624, -155.9914499),
            (19.6362, -155.99141),
            (19.636, -155.9912),
            (19.6357399, -155.99091),
            (19.63552, -155.99069),
            (19.6354599, -155.99063),
            (19.6354, -155.99059),
            (19.63526, -155.9905),
            (19.63504, -155.9903799),
            (19.63476, -155.99024),
            (19.63454, -155.99014),
            (19.63448, -155.9901),
            (19.63442, -155.99007),
            (19.63428, -155.99001),
            (19.63415, -155.98996),
            (19.63401, -155.98991),
            (19.6339, -155.98987),
            (19.63299, -155.98953),
            (19.63242, -155.98932),
            (19.63232, -155.98928),
            (19.63181, -155.9891),
            (19.6317999, -155.98905),
            (19.6317999, -155.98903),
            (19.63179, -155.989),
            (19.63178, -155.98897),
            (19.63176, -155.98895),
            (19.63175, -155.98894),
            (19.63171, -155.98891),
            (19.63164, -155.98886),
            (19.63155, -155.98879),
            (19.63137, -155.9886799),
            (19.63123, -155.98858),
            (19.63108, -155.98848),
            (19.63096, -155.98839),
            (19.6308599, -155.9883199),
            (19.6307699, -155.98825),
            (19.63072, -155.98821),
            (19.63066, -155.98815),
            (19.6305799, -155.98807),
            (19.63044, -155.98791),
            (19.63035, -155.98781),
            (19.6302, -155.98768),
            (19.63007, -155.98755),
            (19.62987, -155.98737),
            (19.62987, -155.98737),
            (19.62987, -155.98737),
            (19.62972, -155.98723),
            (19.62967, -155.98719),
            (19.6296399, -155.98713),
            (19.62961, -155.98708),
            (19.62959, -155.98703),
            (19.62954, -155.98688),
            (19.6295, -155.98679),
            (19.62945, -155.98665),
            (19.6293599, -155.98647),
            (19.62926, -155.98629),
            (19.62915, -155.98614),
            (19.62906, -155.98603),
            (19.62899, -155.98592),
            (19.62894, -155.98587),
            (19.6288899, -155.98582),
            (19.62879, -155.98575),
            (19.62863, -155.98567),
            (19.62852, -155.98562),
            (19.62839, -155.98558),
            (19.6283, -155.9855399),
            (19.62824, -155.98551),
            (19.6282, -155.98549),
            (19.62815, -155.9854499),
            (19.62807, -155.98537),
            (19.62801, -155.98532),
            (19.62793, -155.98524),
            (19.62788, -155.98518),
            (19.62779, -155.98507),
            (19.6277, -155.98493),
            (19.62768, -155.98488),
            (19.62764, -155.98481),
            (19.6276, -155.98473),
            (19.62756, -155.98462),
            (19.62752, -155.9845),
            (19.6274799, -155.98439),
            (19.62743, -155.98421),
            (19.62738, -155.9841099),
            (19.62734, -155.98405),
            (19.62728, -155.98398),
            (19.62723, -155.98394),
            (19.62713, -155.98388),
            (19.62708, -155.9838399),
            (19.62695, -155.98372),
            (19.62689, -155.98365),
            (19.62685, -155.98361),
            (19.6268, -155.98353),
            (19.62677, -155.98349),
            (19.62675, -155.98345),
            (19.62672, -155.98338),
            (19.62667, -155.98325),
            (19.62666, -155.98307),
            (19.62663, -155.98299),
            (19.62662, -155.98294),
            (19.6266, -155.98289),
            (19.6266, -155.98284),
            (19.62659, -155.98278),
            (19.62658, -155.98272),
            (19.62658, -155.98267),
            (19.62658, -155.98262),
            (19.62658, -155.98262),
            (19.62658, -155.98262),
            (19.6258, -155.98144),
            (19.62454, -155.9795),
            (19.62443, -155.97935),
            (19.6241999, -155.979),
            (19.62404, -155.97877),
            (19.62381, -155.9785),
            (19.62366, -155.97834),
            (19.62358, -155.97826),
            (19.62344, -155.97813),
            (19.62334, -155.97805),
            (19.62327, -155.97799),
            (19.62294, -155.97774),
            (19.62271, -155.97755),
            (19.62258, -155.97745),
            (19.62229, -155.97727),
            (19.62209, -155.97716),
            (19.6219499, -155.9771),
            (19.6218, -155.97704),
            (19.62141, -155.97694),
            (19.62061, -155.9767699),
            (19.62036, -155.9767),
            (19.62004, -155.97658),
            (19.61999, -155.97656),
            (19.61986, -155.97649),
            (19.61966, -155.97637),
            (19.61949, -155.97625),
            (19.61931, -155.97611),
            (19.61918, -155.97598),
            (19.61901, -155.97581),
            (19.61889, -155.97566),
            (19.61876, -155.97548),
            (19.6186599, -155.97531),
            (19.61853, -155.97507),
            (19.61839, -155.97478),
            (19.61828, -155.97452),
            (19.61818, -155.97429),
            (19.61807, -155.97405),
            (19.6177199, -155.97324),
            (19.61761, -155.97299),
            (19.61713, -155.97197),
            (19.61704, -155.97177),
            (19.61692, -155.97153),
            (19.61676, -155.97126),
            (19.61653, -155.97088),
            (19.61638, -155.97066),
            (19.61621, -155.9704),
            (19.61583, -155.96989),
            (19.61555, -155.96955),
            (19.6152799, -155.96923),
            (19.61512, -155.96903),
            (19.61488, -155.96874),
            (19.61481, -155.96867),
            (19.61461, -155.96838),
            (19.61455, -155.96831),
            (19.61455, -155.9683099),
            (19.61455, -155.96831),
            (19.61459, -155.96821),
            (19.61467, -155.9680799),
            (19.61479, -155.96792),
            (19.61485, -155.96783),
            (19.61485, -155.96783),
            (19.61485, -155.96783),
            (19.61495, -155.96788),
            (19.61535, -155.96807),
            (19.61632, -155.96856),
            (19.6168, -155.96881),
            (19.6168799, -155.96888),
            (19.6174399, -155.9692),
            (19.61859, -155.96984),
            (19.62041, -155.97082),
            (19.62192, -155.97162),
            (19.62289, -155.97212),
            (19.62817, -155.97468),
            (19.62836, -155.97477),
            (19.62855, -155.97487),
            (19.62985, -155.97558),
            (19.62991, -155.97557),
            (19.63017, -155.9757),
            (19.63115, -155.97619),
            (19.63121, -155.97622),
            (19.632, -155.9765899),
            (19.63332, -155.97742),
            (19.63338, -155.9775),
            (19.63522, -155.97846),
            (19.63652, -155.97914),
            (19.63673, -155.97925),
            (19.63701, -155.97942),
            (19.63763, -155.97979),
            (19.63773, -155.97985),
            (19.63839, -155.98032),
            (19.63941, -155.98118),
            (19.64021, -155.98202),
            (19.64088, -155.98278),
            (19.64151, -155.98367),
            (19.64211, -155.9847),
            (19.6425899, -155.98561),
            (19.64295, -155.98637),
            (19.64309, -155.98665),
            (19.6432, -155.98692),
            (19.64402, -155.9888),
            (19.64415, -155.98909),
            (19.6442799, -155.9893899),
            (19.64612, -155.99328),
            (19.64635, -155.99375),
            (19.64639, -155.99385),
            (19.64655, -155.99425),
            (19.64722, -155.99578),
            (19.64749, -155.99636),
            (19.6482, -155.99793),
            (19.64883, -155.9993),
            (19.64901, -155.99967),
            (19.6491599, -155.99995),
            (19.64959, -156.00071),
            (19.65003, -156.00138),
            (19.65077, -156.00243),
            (19.65098, -156.00269),
            (19.6515999, -156.00335),
            (19.65225, -156.00396),
            (19.65314, -156.00472),
            (19.65388, -156.00525),
            (19.65478, -156.0058),
            (19.65547, -156.00616),
            (19.65687, -156.00686),
            (19.65775, -156.00728),
            (19.65935, -156.0080199),
            (19.66032, -156.00849),
            (19.66125, -156.00893),
            (19.6621, -156.0094),
            (19.66265, -156.00974),
            (19.66876, -156.01377),
            (19.67102, -156.01524),
            (19.67137, -156.01546),
            (19.6717, -156.01568),
            (19.67307, -156.01657),
            (19.67336, -156.01676),
            (19.67367, -156.0169699),
            (19.67481, -156.01774),
            (19.67573, -156.01833),
            (19.67637, -156.01869),
            (19.67709, -156.01906),
            (19.67767, -156.01932),
            (19.67846, -156.01965),
            (19.67865, -156.01973),
            (19.67884, -156.01978),
            (19.67958, -156.01996),
            (19.68034, -156.02014),
            (19.6806899, -156.02022),
            (19.68102, -156.0203),
            (19.68415, -156.02099),
            (19.6863, -156.02149),
            (19.68668, -156.02158),
            (19.68767, -156.02187),
            (19.68829, -156.02207),
            (19.68943, -156.02253),
            (19.69, -156.02281),
            (19.6903599, -156.02299),
            (19.69066, -156.02318),
            (19.69961, -156.02867),
            (19.69987, -156.02883),
            (19.70016, -156.02901),
            (19.70439, -156.0317),
            (19.70501, -156.03208),
            (19.70552, -156.0323699),
            (19.7060299, -156.0326399),
            (19.70649, -156.03285),
            (19.70689, -156.03302),
            (19.70728, -156.0331799),
            (19.7078099, -156.0333599),
            (19.70839, -156.0335399),
            (19.70897, -156.03368),
            (19.7096899, -156.03382),
            (19.71032, -156.03391),
            (19.71088, -156.03396),
            (19.7115699, -156.03399),
            (19.71228, -156.03398),
            (19.71329, -156.0339),
            (19.71397, -156.03381),
            (19.71514, -156.0336),
            (19.71518, -156.0336),
            (19.71578, -156.03348),
            (19.71639, -156.03338),
            (19.72096, -156.03253),
            (19.72356, -156.03202),
            (19.72523, -156.03167),
            (19.72544, -156.03164),
            (19.7257, -156.03159),
            (19.72578, -156.03158),
            (19.7322, -156.03065),
            (19.73278, -156.03055),
            (19.73292, -156.03052),
            (19.73318, -156.0304899),
            (19.7402799, -156.02927),
            (19.74114, -156.02912),
            (19.74381, -156.02865),
            (19.74899, -156.02776),
            (19.74953, -156.02767),
            (19.75068, -156.02747),
            (19.75193, -156.02725),
            (19.75396, -156.0269),
            (19.75525, -156.02667),
            (19.75653, -156.0264),
            (19.75837, -156.02596),
            (19.75949, -156.02567),
            (19.76094, -156.02522),
            (19.76184, -156.02495),
            (19.7633699, -156.02442),
            (19.76483, -156.02385),
            (19.7668399, -156.02304),
            (19.76946, -156.0218),
            (19.7713, -156.02084),
            (19.77211, -156.02037),
            (19.77283, -156.01995),
            (19.77319, -156.01974),
            (19.77375, -156.0194),
            (19.7744399, -156.01896),
            (19.77478, -156.01873),
            (19.77534, -156.01837),
            (19.7761, -156.01786),
            (19.77689, -156.0173),
            (19.77761, -156.01678),
            (19.77828, -156.0163),
            (19.77908, -156.01573),
            (19.78068, -156.01459),
            (19.78582, -156.0109),
            (19.7880499, -156.00926),
            (19.7897399, -156.0079299),
            (19.78988, -156.00781),
            (19.79014, -156.00758),
            (19.79076, -156.00707),
            (19.79113, -156.00677),
            (19.79159, -156.00637),
            (19.79183, -156.00619),
            (19.79342, -156.00483),
            (19.7935, -156.00477),
            (19.79408, -156.00429),
            (19.79625, -156.00233),
            (19.79653, -156.00209),
            (19.79728, -156.0014),
            (19.79737, -156.00133),
            (19.79745, -156.00128),
            (19.79775, -156.001),
            (19.79938, -155.99941),
            (19.80088, -155.99792),
            (19.80169, -155.99712),
            (19.80302, -155.99571),
            (19.80371, -155.99494),
            (19.80405, -155.99455),
            (19.80408, -155.99445),
            (19.8054099, -155.99296),
            (19.8058, -155.9925299),
            (19.80593, -155.99237),
            (19.80594, -155.99236),
            (19.80606, -155.99221),
            (19.80673, -155.99139),
            (19.80689, -155.99119),
            (19.80694, -155.99114),
            (19.80709, -155.99095),
            (19.80811, -155.98963),
            (19.80831, -155.98938),
            (19.80852, -155.98908),
            (19.80883, -155.98867),
            (19.8089799, -155.98846),
            (19.80918, -155.98816),
            (19.80933, -155.98794),
            (19.80953, -155.98763),
            (19.80994, -155.98695),
            (19.81038, -155.98616),
            (19.81041, -155.98611),
            (19.81061, -155.9857199),
            (19.81072, -155.9855),
            (19.81088, -155.98518),
            (19.8110399, -155.98486),
            (19.81119, -155.98451),
            (19.81141, -155.98401),
            (19.81148, -155.98398),
            (19.81159, -155.98371),
            (19.81186, -155.98302),
            (19.81215, -155.98229),
            (19.8122599, -155.98199),
            (19.81247, -155.98137),
            (19.81265, -155.98078),
            (19.81277, -155.98038),
            (19.81288, -155.97996),
            (19.81293, -155.9798),
            (19.8130099, -155.97949),
            (19.81311, -155.97909),
            (19.81335, -155.9780199),
            (19.81371, -155.97553),
            (19.81389, -155.9738099),
            (19.8141, -155.97246),
            (19.81439, -155.97119),
            (19.81468, -155.97006),
            (19.81506, -155.96887),
            (19.81559, -155.96748),
            (19.81642, -155.9657),
            (19.81757, -155.96366),
            (19.8188, -155.96154),
            (19.82022, -155.95906),
            (19.82167, -155.95655),
            (19.82274, -155.9547399),
            (19.82519, -155.95045),
            (19.82867, -155.94441),
            (19.8292499, -155.94339),
            (19.8338, -155.93547),
            (19.83494, -155.93345),
            (19.83521, -155.93299),
            (19.83646, -155.93077),
            (19.83789, -155.92831),
            (19.83875, -155.92681),
            (19.84011, -155.92452),
            (19.84077, -155.92346),
            (19.8408, -155.92338),
            (19.84116, -155.92287),
            (19.84199, -155.9216999),
            (19.84288, -155.92058),
            (19.84416, -155.91912),
            (19.84537, -155.9179399),
            (19.84594, -155.91736),
            (19.847, -155.91649),
            (19.84828, -155.9155),
            (19.84988, -155.9143599),
            (19.85193, -155.91317),
            (19.85311, -155.91257),
            (19.8588099, -155.91001),
            (19.86085, -155.90908),
            (19.86414, -155.90761),
            (19.86571, -155.9069),
            (19.86729, -155.90618),
            (19.86828, -155.90575),
            (19.87095, -155.90456),
            (19.87288, -155.90371),
            (19.87478, -155.90284),
            (19.87716, -155.90178),
            (19.87973, -155.90062),
            (19.88231, -155.89947),
            (19.8846, -155.89845),
            (19.88582, -155.8979),
            (19.8867699, -155.89746),
            (19.88888, -155.89651),
            (19.89095, -155.89553),
            (19.89238, -155.8947499),
            (19.89283, -155.8945),
            (19.89337, -155.89418),
            (19.89492, -155.89316),
            (19.89582, -155.89252),
            (19.89694, -155.8916999),
            (19.89817, -155.89066),
            (19.89854, -155.8903599),
            (19.89891, -155.88999),
            (19.90075, -155.88822),
            (19.90162, -155.88731),
            (19.90173, -155.88717),
            (19.90365, -155.88492),
            (19.90985, -155.8766),
            (19.91096, -155.87517),
            (19.91212, -155.87358),
            (19.91235, -155.87324),
            (19.91273, -155.87276),
            (19.91991, -155.86313),
            (19.92162, -155.86086),
            (19.92191, -155.86047),
            (19.92224, -155.86003),
            (19.92607, -155.85494),
            (19.93005, -155.84959),
            (19.93132, -155.84785),
            (19.93375, -155.84477),
            (19.93462, -155.84374),
            (19.93492, -155.84339),
            (19.935, -155.8433),
            (19.93545, -155.84277),
            (19.93667, -155.8414699),
            (19.93892, -155.83916),
            (19.94082, -155.8373499),
            (19.94352, -155.8351099),
            (19.94541, -155.83375),
            (19.9461799, -155.8332),
            (19.94832, -155.83175),
            (19.94881, -155.83143),
            (19.94898, -155.83131),
            (19.95022, -155.83047),
            (19.95606, -155.8265),
            (19.95715, -155.82578),
            (19.95778, -155.82536),
            (19.95861, -155.82483),
            (19.95952, -155.8243),
            (19.96027, -155.82389),
            (19.9613, -155.82337),
            (19.96209, -155.823),
            (19.96306, -155.82259),
            (19.96471, -155.822),
            (19.96615, -155.82155),
            (19.9675699, -155.82119),
            (19.9694499, -155.82084),
            (19.97012, -155.82075),
            (19.97072, -155.82067),
            (19.9714, -155.8206),
            (19.97228, -155.82054),
            (19.97344, -155.82049),
            (19.97379, -155.82048),
            (19.97438, -155.82045),
            (19.97513, -155.8204),
            (19.97542, -155.82041),
            (19.97625, -155.82039),
            (19.97679, -155.82036),
            (19.97768, -155.82027),
            (19.97859, -155.82013),
            (19.9818399, -155.81948),
            (19.98583, -155.81866),
            (19.99106, -155.81751),
            (19.9914999, -155.81742),
            (19.99215, -155.81728),
            (19.99314, -155.81707),
            (19.9936, -155.81697),
            (19.99661, -155.81634),
            (19.997, -155.81626),
            (19.9970399, -155.81625),
            (19.99738, -155.81617),
            (20.00087, -155.81545),
            (20.00255, -155.81509),
            (20.0029, -155.81502),
            (20.00308, -155.81497),
            (20.00317, -155.81495),
            (20.0036999, -155.81483),
            (20.00467, -155.8146099),
            (20.00527, -155.81448),
            (20.00619, -155.81429),
            (20.01279, -155.81293),
            (20.01341, -155.81285),
            (20.01386, -155.81284),
            (20.01481, -155.81285),
            (20.01843, -155.81301),
            (20.01931, -155.81306),
            (20.01979, -155.81309),
            (20.0200299, -155.8131),
            (20.02027, -155.8131),
            (20.02098, -155.8131),
            (20.02122, -155.81309),
            (20.02149, -155.81308),
            (20.02176, -155.81307),
            (20.02203, -155.81304),
            (20.02241, -155.81299),
            (20.02278, -155.81293),
            (20.02278, -155.81293),
            (20.02278, -155.81293),
            (20.0228499, -155.81311),
            (20.02292, -155.81323),
            (20.02299, -155.81335),
            (20.0231, -155.81348),
            (20.0232199, -155.81359),
            (20.02335, -155.8137099),
            (20.02354, -155.81388),
            (20.02383, -155.81414),
            (20.02476, -155.81497),
            (20.02565, -155.8157699),
            (20.0259, -155.81603),
            (20.02614, -155.8163099),
            (20.02659, -155.81687),
            (20.027, -155.81743),
            (20.02975, -155.82082),
            (20.0302599, -155.82139),
            (20.03047, -155.82162),
            (20.03187, -155.82273),
            (20.03279, -155.82344),
            (20.03524, -155.82531),
            (20.03606, -155.82597),
            (20.03713, -155.82686),
            (20.0374, -155.82715),
            (20.03751, -155.82729),
            (20.03763, -155.82752),
            (20.03774, -155.82779),
            (20.03785, -155.82811),
            (20.03809, -155.82888),
            (20.03811, -155.82894),
            (20.0381399, -155.82898),
            (20.03817, -155.82902),
            (20.03819, -155.82905),
            (20.0382399, -155.82909),
            (20.03866, -155.82932),
            (20.03888, -155.82945),
            (20.03912, -155.8296499),
            (20.03932, -155.82987),
            (20.03965, -155.83026),
            (20.0400199, -155.83071),
            (20.0406799, -155.83149),
            (20.04108, -155.8319),
            (20.04153, -155.83232),
            (20.04213, -155.83279),
            (20.04214, -155.8328),
            (20.04287, -155.8334099),
            (20.04287, -155.83342),
            (20.0436, -155.83402),
            (20.0443399, -155.83461),
            (20.0450899, -155.83522),
            (20.04567, -155.83569),
            (20.04575, -155.83576),
            (20.04588, -155.83587),
            (20.04608, -155.836),
            (20.0488, -155.83777),
            (20.04897, -155.83787),
            (20.04917, -155.83799),
            (20.05243, -155.84003),
            (20.05261, -155.84014),
            (20.05308, -155.84043),
            (20.05362, -155.84077),
            (20.0539999, -155.84099),
            (20.05462, -155.8413799),
            (20.05989, -155.8447),
            (20.06009, -155.84483),
            (20.0614199, -155.84567),
            (20.06192, -155.84607),
            (20.06436, -155.84807),
            (20.0652, -155.8487199),
            (20.06571, -155.84916),
            (20.0659, -155.84933),
            (20.06609, -155.8495),
            (20.0665799, -155.8499),
            (20.06703, -155.85028),
            (20.06766, -155.8508),
            (20.07058, -155.85321),
            (20.07136, -155.85384),
            (20.07214, -155.85447),
            (20.07345, -155.85555),
            (20.07423, -155.8562),
            (20.0764299, -155.85809),
            (20.07663, -155.85827),
            (20.07682, -155.85842),
            (20.07688, -155.85847),
            (20.08006, -155.86109),
            (20.08114, -155.86187),
            (20.08475, -155.86412),
            (20.0866599, -155.86533),
            (20.08833, -155.86638),
            (20.09008, -155.8674399),
            (20.09203, -155.86892),
            (20.09246, -155.86918),
            (20.09286, -155.86939),
            (20.09356, -155.86973),
            (20.09795, -155.87126),
            (20.09986, -155.87217),
            (20.10366, -155.87398),
            (20.10384, -155.8740599),
            (20.10471, -155.87444),
            (20.1054, -155.8747),
            (20.10735, -155.87527),
            (20.10979, -155.87598),
            (20.1112, -155.8764),
            (20.11213, -155.87674),
            (20.11286, -155.87707),
            (20.11567, -155.8782699),
            (20.11778, -155.87916),
            (20.12218, -155.8810499),
            (20.12961, -155.88419),
            (20.1305799, -155.88452),
            (20.13318, -155.88529),
            (20.13704, -155.8864199),
            (20.1410899, -155.88757),
            (20.14268, -155.88805),
            (20.14534, -155.88886),
            (20.15492, -155.8916),
            (20.15665, -155.8921),
            (20.15703, -155.89221),
            (20.16313, -155.8940299),
            (20.1655, -155.89471),
            (20.16659, -155.895),
            (20.16725, -155.89512),
            (20.1678, -155.8952),
            (20.16842, -155.89525),
            (20.17097, -155.89537),
            (20.17488, -155.89554),
            (20.17798, -155.89568),
            (20.17837, -155.89569),
            (20.18018, -155.89576),
            (20.18131, -155.89586),
            (20.1838799, -155.89635),
            (20.18608, -155.89673),
            (20.18703, -155.89683),
            (20.1878, -155.89684),
            (20.18847, -155.89682),
            (20.18932, -155.89671),
            (20.18993, -155.8966299),
            (20.19081, -155.89641),
            (20.1916699, -155.89614),
            (20.19506, -155.89474),
            (20.1960799, -155.89432),
            (20.19784, -155.89359),
            (20.19949, -155.89291),
            (20.19962, -155.89285),
            (20.2013399, -155.89216),
            (20.20325, -155.89132),
            (20.20458, -155.89076),
            (20.20505, -155.89056),
            (20.21021, -155.88841),
            (20.2114699, -155.88791),
            (20.21355, -155.88695),
            (20.2161, -155.88548),
            (20.21685, -155.88498),
            (20.21895, -155.88344),
            (20.2196399, -155.88291),
            (20.22186, -155.88124),
            (20.22488, -155.87907),
            (20.2268, -155.87765),
            (20.22736, -155.87728),
            (20.2284, -155.87653),
            (20.22892, -155.87615),
            (20.23013, -155.87529),
            (20.23173, -155.87395),
            (20.23326, -155.8726),
            (20.23339, -155.87248),
            (20.2335, -155.87239),
            (20.2336199, -155.87228),
            (20.23453, -155.87131),
            (20.2352, -155.87049),
            (20.23569, -155.86982),
            (20.23614, -155.8691399),
            (20.2366199, -155.8683),
            (20.2369999, -155.8675299),
            (20.23713, -155.86729),
            (20.23758, -155.86615),
            (20.2379, -155.86499),
            (20.23793, -155.86487),
            (20.23839, -155.86309),
            (20.23857, -155.86181),
            (20.23862, -155.86132),
            (20.23867, -155.86086),
            (20.2387799, -155.8601),
            (20.23886, -155.85935),
            (20.23891, -155.85881),
            (20.23911, -155.8570499),
            (20.23915, -155.8565099),
            (20.23919, -155.85592),
            (20.23919, -155.85573),
            (20.2392, -155.85492),
            (20.23917, -155.85432),
            (20.23917, -155.85336),
            (20.23911, -155.85201),
            (20.23905, -155.84945),
            (20.23902, -155.84846),
            (20.23898, -155.84708),
            (20.2389699, -155.84654),
            (20.23882, -155.8416),
            (20.23875, -155.83945),
            (20.23874, -155.839),
            (20.23874, -155.83883),
            (20.23871, -155.83823),
            (20.2387, -155.83784),
            (20.2387, -155.83777),
            (20.2387, -155.8377699),
            (20.2387, -155.83777),
            (20.2395, -155.83777),
            (20.23959, -155.83772),
            (20.2396299, -155.8376199),
            (20.23961, -155.83721),
            (20.23961, -155.83721),
            (20.23961, -155.83721),
            (20.2396299, -155.8376199),
            (20.23959, -155.83772),
            (20.2395, -155.83777),
            (20.2387, -155.83777),
            (20.2387, -155.8377699),
            (20.2387, -155.83777),
            (20.2387, -155.83784),
            (20.23871, -155.83823),
            (20.23874, -155.83883),
            (20.23874, -155.839),
            (20.23875, -155.83945),
            (20.23882, -155.8416),
            (20.2389699, -155.84654),
            (20.23898, -155.84708),
            (20.23902, -155.84846),
            (20.23905, -155.84945),
            (20.23911, -155.85201),
            (20.23917, -155.85336),
            (20.23917, -155.85432),
            (20.2392, -155.85492),
            (20.23919, -155.85573),
            (20.23919, -155.85592),
            (20.23915, -155.8565099),
            (20.23911, -155.8570499),
            (20.23891, -155.85881),
            (20.23886, -155.85935),
            (20.2387799, -155.8601),
            (20.23867, -155.86086),
            (20.23862, -155.86132),
            (20.23857, -155.86181),
            (20.23839, -155.86309),
            (20.23793, -155.86487),
            (20.2379, -155.86499),
            (20.23758, -155.86615),
            (20.23713, -155.86729),
            (20.2369999, -155.8675299),
            (20.2366199, -155.8683),
            (20.23614, -155.8691399),
            (20.23569, -155.86982),
            (20.2352, -155.87049),
            (20.23453, -155.87131),
            (20.2336199, -155.87228),
            (20.2335, -155.87239),
            (20.23339, -155.87248),
            (20.23326, -155.8726),
            (20.23173, -155.87395),
            (20.23013, -155.87529),
            (20.22892, -155.87615),
            (20.2284, -155.87653),
            (20.22736, -155.87728),
            (20.2268, -155.87765),
            (20.22488, -155.87907),
            (20.22186, -155.88124),
            (20.2196399, -155.88291),
            (20.21895, -155.88344),
            (20.21685, -155.88498),
            (20.2161, -155.88548),
            (20.21355, -155.88695),
            (20.2114699, -155.88791),
            (20.21021, -155.88841),
            (20.20505, -155.89056),
            (20.20458, -155.89076),
            (20.20325, -155.89132),
            (20.2013399, -155.89216),
            (20.19962, -155.89285),
            (20.19949, -155.89291),
            (20.19784, -155.89359),
            (20.1960799, -155.89432),
            (20.19506, -155.89474),
            (20.1916699, -155.89614),
            (20.19081, -155.89641),
            (20.18993, -155.8966299),
            (20.18932, -155.89671),
            (20.18847, -155.89682),
            (20.1878, -155.89684),
            (20.18703, -155.89683),
            (20.18608, -155.89673),
            (20.1838799, -155.89635),
            (20.18131, -155.89586),
            (20.18018, -155.89576),
            (20.17837, -155.89569),
            (20.17798, -155.89568),
            (20.17488, -155.89554),
            (20.17097, -155.89537),
            (20.16842, -155.89525),
            (20.1678, -155.8952),
            (20.16725, -155.89512),
            (20.16659, -155.895),
            (20.1655, -155.89471),
            (20.16313, -155.8940299),
            (20.15703, -155.89221),
            (20.15665, -155.8921),
            (20.15492, -155.8916),
            (20.14534, -155.88886),
            (20.14268, -155.88805),
            (20.1410899, -155.88757),
            (20.13704, -155.8864199),
            (20.13318, -155.88529),
            (20.1305799, -155.88452),
            (20.12961, -155.88419),
            (20.12218, -155.8810499),
            (20.11778, -155.87916),
            (20.11567, -155.8782699),
            (20.11286, -155.87707),
            (20.11213, -155.87674),
            (20.1112, -155.8764),
            (20.10979, -155.87598),
            (20.10735, -155.87527),
            (20.1054, -155.8747),
            (20.10471, -155.87444),
            (20.10384, -155.8740599),
            (20.10366, -155.87398),
            (20.09986, -155.87217),
            (20.09795, -155.87126),
            (20.09356, -155.86973),
            (20.09286, -155.86939),
            (20.09246, -155.86918),
            (20.09203, -155.86892),
            (20.09008, -155.8674399),
            (20.08833, -155.86638),
            (20.0866599, -155.86533),
            (20.08475, -155.86412),
            (20.08114, -155.86187),
            (20.08006, -155.86109),
            (20.07688, -155.85847),
            (20.07682, -155.85842),
            (20.07663, -155.85827),
            (20.0764299, -155.85809),
            (20.07423, -155.8562),
            (20.07345, -155.85555),
            (20.07214, -155.85447),
            (20.07136, -155.85384),
            (20.07058, -155.85321),
            (20.06766, -155.8508),
            (20.06703, -155.85028),
            (20.0665799, -155.8499),
            (20.06609, -155.8495),
            (20.0659, -155.84933),
            (20.06571, -155.84916),
            (20.0652, -155.8487199),
            (20.06436, -155.84807),
            (20.06192, -155.84607),
            (20.0614199, -155.84567),
            (20.06009, -155.84483),
            (20.05989, -155.8447),
            (20.05462, -155.8413799),
            (20.0539999, -155.84099),
            (20.05362, -155.84077),
            (20.05308, -155.84043),
            (20.05261, -155.84014),
            (20.05243, -155.84003),
            (20.04917, -155.83799),
            (20.04897, -155.83787),
            (20.0488, -155.83777),
            (20.04608, -155.836),
            (20.04588, -155.83587),
            (20.04575, -155.83576),
            (20.04567, -155.83569),
            (20.0450899, -155.83522),
            (20.0443399, -155.83461),
            (20.0436, -155.83402),
            (20.04287, -155.83342),
            (20.04287, -155.8334099),
            (20.04214, -155.8328),
            (20.04213, -155.83279),
            (20.04153, -155.83232),
            (20.04108, -155.8319),
            (20.0406799, -155.83149),
            (20.0400199, -155.83071),
            (20.03965, -155.83026),
            (20.03932, -155.82987),
            (20.03912, -155.8296499),
            (20.03888, -155.82945),
            (20.03866, -155.82932),
            (20.0382399, -155.82909),
            (20.03819, -155.82905),
            (20.03817, -155.82902),
            (20.0381399, -155.82898),
            (20.03811, -155.82894),
            (20.03809, -155.82888),
            (20.03785, -155.82811),
            (20.03774, -155.82779),
            (20.03763, -155.82752),
            (20.03751, -155.82729),
            (20.0374, -155.82715),
            (20.03713, -155.82686),
            (20.03606, -155.82597),
            (20.03524, -155.82531),
            (20.03279, -155.82344),
            (20.03187, -155.82273),
            (20.03047, -155.82162),
            (20.0302599, -155.82139),
            (20.02975, -155.82082),
            (20.027, -155.81743),
            (20.02659, -155.81687),
            (20.02614, -155.8163099),
            (20.0259, -155.81603),
            (20.02565, -155.8157699),
            (20.02476, -155.81497),
            (20.02383, -155.81414),
            (20.02354, -155.81388),
            (20.02335, -155.8137099),
            (20.0232199, -155.81359),
            (20.0231, -155.81348),
            (20.02299, -155.81335),
            (20.02292, -155.81323),
            (20.0228499, -155.81311),
            (20.02278, -155.81293),
            (20.02278, -155.81293),
            (20.02278, -155.81293),
            (20.02241, -155.81299),
            (20.02203, -155.81304),
            (20.02176, -155.81307),
            (20.02149, -155.81308),
            (20.02122, -155.81309),
            (20.02098, -155.8131),
            (20.02027, -155.8131),
            (20.0200299, -155.8131),
            (20.01979, -155.81309),
            (20.01931, -155.81306),
            (20.01843, -155.81301),
            (20.01481, -155.81285),
            (20.01386, -155.81284),
            (20.01341, -155.81285),
            (20.01279, -155.81293),
            (20.00619, -155.81429),
            (20.00527, -155.81448),
            (20.00467, -155.8146099),
            (20.0036999, -155.81483),
            (20.00317, -155.81495),
            (20.00308, -155.81497),
            (20.0029, -155.81502),
            (20.00255, -155.81509),
            (20.00087, -155.81545),
            (19.99738, -155.81617),
            (19.9970399, -155.81625),
            (19.997, -155.81626),
            (19.99661, -155.81634),
            (19.9936, -155.81697),
            (19.99314, -155.81707),
            (19.99215, -155.81728),
            (19.9914999, -155.81742),
            (19.99106, -155.81751),
            (19.98583, -155.81866),
            (19.9818399, -155.81948),
            (19.97859, -155.82013),
            (19.97768, -155.82027),
            (19.97679, -155.82036),
            (19.97625, -155.82039),
            (19.97542, -155.82041),
            (19.97513, -155.8204),
            (19.97438, -155.82045),
            (19.97379, -155.82048),
            (19.97344, -155.82049),
            (19.97228, -155.82054),
            (19.9714, -155.8206),
            (19.97072, -155.82067),
            (19.97012, -155.82075),
            (19.9694499, -155.82084),
            (19.9675699, -155.82119),
            (19.96615, -155.82155),
            (19.96471, -155.822),
            (19.96306, -155.82259),
            (19.96209, -155.823),
            (19.9613, -155.82337),
            (19.96027, -155.82389),
            (19.95952, -155.8243),
            (19.95861, -155.82483),
            (19.95778, -155.82536),
            (19.95715, -155.82578),
            (19.95606, -155.8265),
            (19.95022, -155.83047),
            (19.94898, -155.83131),
            (19.94881, -155.83143),
            (19.94832, -155.83175),
            (19.9461799, -155.8332),
            (19.94541, -155.83375),
            (19.94352, -155.8351099),
            (19.94082, -155.8373499),
            (19.93892, -155.83916),
            (19.93667, -155.8414699),
            (19.93545, -155.84277),
            (19.935, -155.8433),
            (19.93492, -155.84339),
            (19.93462, -155.84374),
            (19.93375, -155.84477),
            (19.93132, -155.84785),
            (19.93005, -155.84959),
            (19.92607, -155.85494),
            (19.92224, -155.86003),
            (19.92191, -155.86047),
            (19.92162, -155.86086),
            (19.91991, -155.86313),
            (19.91273, -155.87276),
            (19.91235, -155.87324),
            (19.91212, -155.87358),
            (19.91096, -155.87517),
            (19.90985, -155.8766),
            (19.90365, -155.88492),
            (19.90173, -155.88717),
            (19.90162, -155.88731),
            (19.90075, -155.88822),
            (19.89891, -155.88999),
            (19.89854, -155.8903599),
            (19.89817, -155.89066),
            (19.89694, -155.8916999),
            (19.89582, -155.89252),
            (19.89492, -155.89316),
            (19.89337, -155.89418),
            (19.89283, -155.8945),
            (19.89238, -155.8947499),
            (19.89095, -155.89553),
            (19.88888, -155.89651),
            (19.8867699, -155.89746),
            (19.88582, -155.8979),
            (19.8846, -155.89845),
            (19.88231, -155.89947),
            (19.87973, -155.90062),
            (19.87716, -155.90178),
            (19.87478, -155.90284),
            (19.87288, -155.90371),
            (19.87095, -155.90456),
            (19.86828, -155.90575),
            (19.86729, -155.90618),
            (19.86571, -155.9069),
            (19.86414, -155.90761),
            (19.86085, -155.90908),
            (19.8588099, -155.91001),
            (19.85311, -155.91257),
            (19.85193, -155.91317),
            (19.84988, -155.9143599),
            (19.84828, -155.9155),
            (19.847, -155.91649),
            (19.84594, -155.91736),
            (19.84537, -155.9179399),
            (19.84416, -155.91912),
            (19.84288, -155.92058),
            (19.84199, -155.9216999),
            (19.84116, -155.92287),
            (19.8408, -155.92338),
            (19.84077, -155.92346),
            (19.84011, -155.92452),
            (19.83875, -155.92681),
            (19.83789, -155.92831),
            (19.83646, -155.93077),
            (19.83521, -155.93299),
            (19.83494, -155.93345),
            (19.8338, -155.93547),
            (19.8292499, -155.94339),
            (19.82867, -155.94441),
            (19.82519, -155.95045),
            (19.82274, -155.9547399),
            (19.82167, -155.95655),
            (19.82022, -155.95906),
            (19.8188, -155.96154),
            (19.81757, -155.96366),
            (19.81642, -155.9657),
            (19.81559, -155.96748),
            (19.81506, -155.96887),
            (19.81468, -155.97006),
            (19.81439, -155.97119),
            (19.8141, -155.97246),
            (19.81389, -155.9738099),
            (19.81371, -155.97553),
            (19.81335, -155.9780199),
            (19.81311, -155.97909),
            (19.8130099, -155.97949),
            (19.81293, -155.9798),
            (19.81288, -155.97996),
            (19.81277, -155.98038),
            (19.81265, -155.98078),
            (19.81247, -155.98137),
            (19.8122599, -155.98199),
            (19.81215, -155.98229),
            (19.81186, -155.98302),
            (19.81159, -155.98371),
            (19.81148, -155.98398),
            (19.81148, -155.98408),
            (19.81115, -155.98484),
            (19.81103, -155.9851),
            (19.81089, -155.98537),
            (19.8107599, -155.98564),
            (19.8107, -155.98575),
            (19.81066, -155.98583),
            (19.81049, -155.98615),
            (19.81046, -155.98621),
            (19.81037, -155.98638),
            (19.81021, -155.98666),
            (19.80991, -155.98718),
            (19.80962, -155.98767),
            (19.80932, -155.98816),
            (19.80891, -155.98876),
            (19.80854, -155.98928),
            (19.80716, -155.99102),
            (19.8070099, -155.9912),
            (19.80697, -155.99126),
            (19.8068199, -155.99144),
            (19.80613, -155.99228),
            (19.80601, -155.99242),
            (19.80601, -155.99243),
            (19.806, -155.9924399),
            (19.80586, -155.99259),
            (19.80548, -155.99303),
            (19.80415, -155.99452),
            (19.80405, -155.99455),
            (19.80371, -155.99494),
            (19.80302, -155.99571),
            (19.80169, -155.99712),
            (19.80088, -155.99792),
            (19.79938, -155.99941),
            (19.79775, -156.001),
            (19.79745, -156.00128),
            (19.79739, -156.00137),
            (19.79735, -156.00141),
            (19.797, -156.00176),
            (19.79682, -156.00191),
            (19.79663, -156.00209),
            (19.7963099, -156.0023799),
            (19.79609, -156.00258),
            (19.79576, -156.0029),
            (19.79523, -156.00341),
            (19.79486, -156.00373),
            (19.79447, -156.00406),
            (19.79414, -156.00436),
            (19.79376, -156.00468),
            (19.79356, -156.00486),
            (19.7934899, -156.00492),
            (19.79336, -156.00503),
            (19.79189, -156.00628),
            (19.7917099, -156.00641),
            (19.79018, -156.00763),
            (19.78988, -156.00781),
            (19.7897399, -156.0079299),
            (19.7880499, -156.00926),
            (19.78582, -156.0109),
            (19.78068, -156.01459),
            (19.77908, -156.01573),
            (19.77828, -156.0163),
            (19.77761, -156.01678),
            (19.77689, -156.0173),
            (19.7761, -156.01786),
            (19.77534, -156.01837),
            (19.77478, -156.01873),
            (19.7744399, -156.01896),
            (19.77375, -156.0194),
            (19.77319, -156.01974),
            (19.77283, -156.01995),
            (19.77211, -156.02037),
            (19.7713, -156.02084),
            (19.76946, -156.0218),
            (19.7668399, -156.02304),
            (19.76483, -156.02385),
            (19.7633699, -156.02442),
            (19.76184, -156.02495),
            (19.76094, -156.02522),
            (19.75949, -156.02567),
            (19.75837, -156.02596),
            (19.75653, -156.0264),
            (19.75525, -156.02667),
            (19.75396, -156.0269),
            (19.75193, -156.02725),
            (19.75068, -156.02747),
            (19.74953, -156.02767),
            (19.74899, -156.02776),
            (19.74381, -156.02865),
            (19.74114, -156.02912),
            (19.7402799, -156.02927),
            (19.73318, -156.0304899),
            (19.73292, -156.03052),
            (19.73278, -156.03055),
            (19.7322, -156.03065),
            (19.72578, -156.03158),
            (19.7257, -156.03159),
            (19.72544, -156.03164),
            (19.72523, -156.03167),
            (19.72356, -156.03202),
            (19.72096, -156.03253),
            (19.71639, -156.03338),
            (19.71578, -156.03348),
            (19.71518, -156.0336),
            (19.71514, -156.0336),
            (19.71397, -156.03381),
            (19.71329, -156.0339),
            (19.71228, -156.03398),
            (19.7115699, -156.03399),
            (19.71088, -156.03396),
            (19.71032, -156.03391),
            (19.7096899, -156.03382),
            (19.70897, -156.03368),
            (19.70839, -156.0335399),
            (19.7078099, -156.0333599),
            (19.70728, -156.0331799),
            (19.70689, -156.03302),
            (19.70649, -156.03285),
            (19.7060299, -156.0326399),
            (19.70552, -156.0323699),
            (19.70501, -156.03208),
            (19.70439, -156.0317),
            (19.70016, -156.02901),
            (19.69987, -156.02883),
            (19.69961, -156.02867),
            (19.69066, -156.02318),
            (19.6903599, -156.02299),
            (19.69, -156.02281),
            (19.68943, -156.02253),
            (19.68829, -156.02207),
            (19.68767, -156.02187),
            (19.68668, -156.02158),
            (19.6863, -156.02149),
            (19.68415, -156.02099),
            (19.68102, -156.0203),
            (19.6806899, -156.02022),
            (19.68034, -156.02014),
            (19.67958, -156.01996),
            (19.67884, -156.01978),
            (19.67865, -156.01973),
            (19.67846, -156.01965),
            (19.67767, -156.01932),
            (19.67709, -156.01906),
            (19.67637, -156.01869),
            (19.67573, -156.01833),
            (19.67481, -156.01774),
            (19.67367, -156.0169699),
            (19.67336, -156.01676),
            (19.67307, -156.01657),
            (19.6717, -156.01568),
            (19.67137, -156.01546),
            (19.67102, -156.01524),
            (19.66876, -156.01377),
            (19.66265, -156.00974),
            (19.6621, -156.0094),
            (19.66125, -156.00893),
            (19.66032, -156.00849),
            (19.65935, -156.0080199),
            (19.65775, -156.00728),
            (19.65687, -156.00686),
            (19.65547, -156.00616),
            (19.65478, -156.0058),
            (19.65388, -156.00525),
            (19.65314, -156.00472),
            (19.65225, -156.00396),
            (19.6515999, -156.00335),
            (19.65098, -156.00269),
            (19.65077, -156.00243),
            (19.65003, -156.00138),
            (19.64959, -156.00071),
            (19.6491599, -155.99995),
            (19.64901, -155.99967),
            (19.64883, -155.9993),
            (19.6482, -155.99793),
            (19.64749, -155.99636),
            (19.64722, -155.99578),
            (19.64655, -155.99425),
            (19.64655, -155.9942499),
            (19.64655, -155.99425),
            (19.64632, -155.99413),
            (19.64591, -155.9941),
            (19.6456, -155.99428),
            (19.64518, -155.9944999),
            (19.64469, -155.99477),
            (19.64455, -155.99485),
            (19.64321, -155.99559),
            (19.64264, -155.99595),
            (19.6424, -155.9961),
            (19.64193, -155.99641),
            (19.64186, -155.99645),
            (19.64176, -155.99644),
            (19.6415599, -155.99659),
            (19.64134, -155.99676),
            (19.64124, -155.99685),
            (19.6412, -155.99688),
            (19.6408999, -155.99712),
            (19.64079, -155.9971799),
            (19.64068, -155.9971799),
            (19.64058, -155.99715),
            (19.64051, -155.99712),
            (19.64035, -155.99699),
            (19.64025, -155.9969),
            (19.64025, -155.9968999),
            (19.64025, -155.9969),
            (19.6401499, -155.99684),
            (19.64011, -155.99677),
            (19.64009, -155.99668),
            (19.64009, -155.99655),
            (19.64012, -155.99634),
            (19.6401499, -155.9961099),
            (19.64014, -155.99587),
            (19.64012, -155.9957),
            (19.6400599, -155.99543),
            (19.63983, -155.9948),
            (19.63979, -155.99466),
            (19.63976, -155.99456),
            (19.63972, -155.99449),
            (19.63967, -155.99443),
            (19.63956, -155.99433),
            (19.63939, -155.99417),
            (19.63923, -155.99406),
            (19.63908, -155.99394),
            (19.63899, -155.9938699),
            (19.63886, -155.99381),
            (19.63829, -155.9935099),
            (19.6381, -155.9934),
            (19.63796, -155.99329),
            (19.63784, -155.99317),
            (19.63779, -155.99313),
            (19.63773, -155.99307),
            (19.63766, -155.99299),
            (19.63745, -155.99277),
            (19.6369599, -155.99229),
            (19.63662, -155.9918999),
            (19.63646, -155.99171),
            (19.63624, -155.9914499),
            (19.6362, -155.99141),
            (19.636, -155.9912),
            (19.6357399, -155.99091),
            (19.63552, -155.99069),
            (19.6354599, -155.99063),
            (19.6354, -155.99059),
            (19.63526, -155.9905),
            (19.63504, -155.9903799),
            (19.63476, -155.99024),
            (19.63454, -155.99014),
            (19.63448, -155.9901),
            (19.63442, -155.99007),
            (19.63428, -155.99001),
            (19.63415, -155.98996),
            (19.63401, -155.98991),
            (19.6339, -155.98987),
            (19.63299, -155.98953),
            (19.63242, -155.98932),
            (19.63232, -155.98928),
            (19.63181, -155.9891),
            (19.6317999, -155.98905),
            (19.6317999, -155.98903),
            (19.63179, -155.989),
            (19.63178, -155.98897),
            (19.63176, -155.98895),
            (19.63175, -155.98894),
            (19.63171, -155.98891),
            (19.63164, -155.98886),
            (19.63155, -155.98879),
            (19.63137, -155.9886799),
            (19.63123, -155.98858),
            (19.63108, -155.98848),
            (19.63096, -155.98839),
            (19.6308599, -155.9883199),
            (19.6307699, -155.98825),
            (19.63072, -155.98821),
            (19.63066, -155.98815),
            (19.6305799, -155.98807),
            (19.63044, -155.98791),
            (19.63035, -155.98781),
            (19.6302, -155.98768),
            (19.63007, -155.98755),
            (19.62987, -155.98737),
            (19.62972, -155.98723),
            (19.62967, -155.98719),
            (19.6296399, -155.98713),
            (19.62961, -155.98708),
            (19.62959, -155.98703),
            (19.62954, -155.98688),
            (19.6295, -155.98679),
            (19.62945, -155.98665),
            (19.6293599, -155.98647),
            (19.62926, -155.98629),
            (19.62915, -155.98614),
            (19.62906, -155.98603),
            (19.62899, -155.98592),
            (19.62894, -155.98587),
            (19.6288899, -155.98582),
            (19.62879, -155.98575),
            (19.62863, -155.98567),
            (19.62852, -155.98562),
            (19.62839, -155.98558),
            (19.6283, -155.9855399),
            (19.62824, -155.98551),
            (19.6282, -155.98549),
            (19.62815, -155.9854499),
            (19.62811, -155.98541),
            (19.640017, -155.997058)
        ]

        self.biketm=[300, 600, 900, 1200]

        self.runcrs = [
            (19.6399178, -155.9970403),
            (19.6400108, -155.996994),
            (19.6401749, -155.9968095),
            (19.640283, -155.996762),
            (19.6406759, -155.9969697),
            (19.6407972, -155.9969745),
            (19.640861, -155.9969557),
            (19.641744, -155.9962712),
            (19.6417664, -155.9961752),
            (19.641678, -155.996036),
            (19.6413242, -155.9955029),
            (19.6411904, -155.9952813),
            (19.6410373, -155.9949441),
            (19.6409289, -155.9945219),
            (19.6405971, -155.9927724),
            (19.6404995, -155.9924295),
            (19.6404017, -155.9921996),
            (19.6402787, -155.9919892),
            (19.6400903, -155.9917251),
            (19.6399268, -155.9915486),
            (19.639771, -155.9914082),
            (19.6392995, -155.9910851),
            (19.6385565, -155.9906997),
            (19.6384906, -155.9906938),
            (19.6384478, -155.9907147),
            (19.6384198, -155.9907461),
            (19.6374836, -155.9925878),
            (19.637434, -155.9925992),
            (19.6372799, -155.9924431),
            (19.6356084, -155.990707),
            (19.6354449, -155.9905425),
            (19.6352947, -155.9904257),
            (19.6351245, -155.9903181),
            (19.6345995, -155.990043),
            (19.6344441, -155.9899708),
            (19.6307761, -155.9885798),
            (19.6298781, -155.9882907),
            (19.6287363, -155.9880117),
            (19.6268958, -155.9876669),
            (19.6266859, -155.9876172),
            (19.6264361, -155.9875373),
            (19.6261435, -155.9874206),
            (19.6259312, -155.987318),
            (19.625727, -155.9872053),
            (19.6254411, -155.9870188),
            (19.6251631, -155.9867977),
            (19.6243253, -155.9860069),
            (19.6241771, -155.9858799),
            (19.6240414, -155.9857747),
            (19.6237678, -155.9856359),
            (19.6235265, -155.9855696),
            (19.6227524, -155.9853867),
            (19.6213, -155.9850123),
            (19.6201782, -155.9846484),
            (19.6196152, -155.9844375),
            (19.6189215, -155.9841433),
            (19.6179645, -155.9837076),
            (19.6171071, -155.9833247),
            (19.6161763, -155.9828979),
            (19.6153023, -155.9824668),
            (19.6148757, -155.9822358),
            (19.614207, -155.9818301),
            (19.6136275, -155.9814417),
            (19.6108656, -155.9794264),
            (19.6104894, -155.9791851),
            (19.6094263, -155.9784086),
            (19.6091055, -155.9781206),
            (19.6081276, -155.977204),
            (19.6079048, -155.9770266),
            (19.6068224, -155.9764919),
            (19.606591, -155.9763388),
            (19.6063377, -155.9761055),
            (19.60573, -155.9755136),
            (19.6044649, -155.9747212),
            (19.604159, -155.9745753),
            (19.6038981, -155.9745059),
            (19.6035513, -155.9744203),
            (19.6032989, -155.9743989),
            (19.6029252, -155.9744214),
            (19.6019229, -155.9745747),
            (19.6015595, -155.9746156),
            (19.6013637, -155.9746238),
            (19.6010239, -155.9746073),
            (19.6006327, -155.9745559),
            (19.6001262, -155.9744724),
            (19.6006157, -155.9745536),
            (19.6010069, -155.9746074),
            (19.6013456, -155.9746226),
            (19.601538, -155.9746173),
            (19.6019029, -155.974576),
            (19.6029074, -155.9744242),
            (19.6032767, -155.9743985),
            (19.6035273, -155.9744185),
            (19.6038762, -155.9744994),
            (19.604147, -155.9745703),
            (19.6044536, -155.9747132),
            (19.6057154, -155.9755038),
            (19.6063251, -155.9760926),
            (19.6065759, -155.9763264),
            (19.6068123, -155.9764846),
            (19.6078958, -155.9770207),
            (19.608119, -155.9771962),
            (19.6090911, -155.9781072),
            (19.609416, -155.9783995),
            (19.6104782, -155.9791762),
            (19.6108557, -155.9794194),
            (19.6136176, -155.9814336),
            (19.6141939, -155.9818225),
            (19.6148643, -155.9822293),
            (19.6152927, -155.9824613),
            (19.6161663, -155.9828922),
            (19.6170947, -155.9833187),
            (19.6179551, -155.9837032),
            (19.6189097, -155.9841389),
            (19.6196036, -155.9844325),
            (19.6201656, -155.9846436),
            (19.6212883, -155.9850082),
            (19.6227359, -155.9853804),
            (19.6235137, -155.9855657),
            (19.6237566, -155.9856321),
            (19.6240295, -155.9857667),
            (19.6241679, -155.9858695),
            (19.6243136, -155.9859964),
            (19.6251516, -155.9867868),
            (19.6254293, -155.9870091),
            (19.6257123, -155.9871961),
            (19.6259184, -155.9873123),
            (19.6261297, -155.9874168),
            (19.6264216, -155.9875309),
            (19.6266674, -155.9876103),
            (19.6268797, -155.9876625),
            (19.6287223, -155.9880087),
            (19.6298698, -155.9882871),
            (19.6307706, -155.988577),
            (19.6344322, -155.9899659),
            (19.6345913, -155.9900362),
            (19.6351197, -155.9903157),
            (19.6352954, -155.9904222),
            (19.6354447, -155.9905425),
            (19.6356096, -155.9907069),
            (19.6372785, -155.9924421),
            (19.6373829, -155.9924702),
            (19.6374578, -155.9924735),
            (19.6375136, -155.9924404),
            (19.6375709, -155.992364),
            (19.6383382, -155.9908417),
            (19.6384338, -155.9906336),
            (19.6393005, -155.9910806),
            (19.6397775, -155.9914143),
            (19.6399379, -155.9915608),
            (19.6401039, -155.9917371),
            (19.6402875, -155.9920012),
            (19.640411, -155.9922169),
            (19.6405082, -155.9924496),
            (19.6406012, -155.9927895),
            (19.6409327, -155.9945362),
            (19.6410442, -155.9949617),
            (19.6412012, -155.9952968),
            (19.6413366, -155.9955224),
            (19.6418133, -155.9961022),
            (19.6420409, -155.9961035),
            (19.6421886, -155.9960268),
            (19.6443452, -155.9947887),
            (19.646245, -155.9937901),
            (19.6465336, -155.9937699),
            (19.6469771, -155.9947263),
            (19.650054, -156.0006988),
            (19.650372, -156.0012449),
            (19.6507424, -156.0018223),
            (19.6512259, -156.0024921),
            (19.6519867, -156.0033324),
            (19.6529867, -156.0042693),
            (19.6536121, -156.0047816),
            (19.6547732, -156.0055944),
            (19.6580876, -156.0072055),
            (19.6605224, -156.0083501),
            (19.6611216, -156.0086246),
            (19.6619144, -156.0090791),
            (19.6622506, -156.0092799),
            (19.6626343, -156.0095216),
            (19.6629854, -156.0097514),
            (19.6638161, -156.0102608),
            (19.6648581, -156.0109504),
            (19.6673157, -156.0125883),
            (19.6712326, -156.0151646),
            (19.6732375, -156.0164993),
            (19.6758386, -156.0181627),
            (19.6768083, -156.0186891),
            (19.6774528, -156.0189702),
            (19.6782884, -156.019308),
            (19.6788372, -156.0194886),
            (19.6805939, -156.0199807),
            (19.6828644, -156.0204709),
            (19.6847186, -156.0209323),
            (19.6865391, -156.0213489),
            (19.6874222, -156.0215861),
            (19.6881183, -156.0218099),
            (19.6893262, -156.022291),
            (19.6902086, -156.0227191),
            (19.6908718, -156.0230824),
            (19.6917131, -156.0235624),
            (19.6998435, -156.02863),
            (19.7007871, -156.0291756),
            (19.70397, -156.031202),
            (19.7049168, -156.0317934),
            (19.7060345, -156.0324183),
            (19.7068289, -156.0327866),
            (19.7074253, -156.0330068),
            (19.7081224, -156.0332366),
            (19.7088007, -156.0334173),
            (19.7095036, -156.0335675),
            (19.7105347, -156.0337152),
            (19.7111381, -156.0337606),
            (19.7117556, -156.0337709),
            (19.7124718, -156.0337405),
            (19.7140308, -156.0335532),
            (19.715986, -156.0332398),
            (19.7172722, -156.0330284),
            (19.7186358, -156.032816),
            (19.7204949, -156.0325069),
            (19.721656, -156.0323087),
            (19.7253618, -156.0316288),
            (19.7255452, -156.0321314),
            (19.7256917, -156.0328565),
            (19.7255888, -156.0336716),
            (19.7247456, -156.0339618),
            (19.7172324, -156.035434),
            (19.7164015, -156.0356064),
            (19.7162174, -156.035621),
            (19.7159644, -156.0355992),
            (19.7158999, -156.035621),
            (19.7158628, -156.0356625),
            (19.7158382, -156.035703),
            (19.715545, -156.0382773),
            (19.7153563, -156.0398137),
            (19.714431, -156.0475659),
            (19.7144456, -156.0477021),
            (19.7144998, -156.0478388),
            (19.7145805, -156.0479547),
            (19.7148857, -156.0481711),
            (19.7211692, -156.0527174),
            (19.7256796, -156.0560026),
            (19.7256685, -156.0560243),
            (19.7211299, -156.0527869),
            (19.7147581, -156.0481402),
            (19.7145995, -156.0480114),
            (19.7145006, -156.0478968),
            (19.7144367, -156.0477706),
            (19.7144057, -156.047645),
            (19.7144061, -156.0475045),
            (19.7158121, -156.0355932),
            (19.7159639, -156.0355351),
            (19.716269, -156.0355543),
            (19.7166241, -156.0355036),
            (19.717215, -156.0353697),
            (19.7244448, -156.0339084),
            (19.7247705, -156.0338367),
            (19.7254662, -156.0335647),
            (19.7255416, -156.0328586),
            (19.7254179, -156.0321536),
            (19.7253054, -156.0317669),
            (19.7252677, -156.0317214),
            (19.7235484, -156.0320045),
            (19.7224254, -156.0322121),
            (19.7191081, -156.032781),
            (19.7168034, -156.0331386),
            (19.7158493, -156.0333008),
            (19.7139405, -156.033634),
            (19.7122468, -156.0338184),
            (19.7108627, -156.0337938),
            (19.7094001, -156.0336045),
            (19.7080187, -156.0332686),
            (19.7066501, -156.0327763),
            (19.704902, -156.0318496),
            (19.703222, -156.0307809),
            (19.6998827, -156.0287191),
            (19.6970663, -156.0269555),
            (19.691482, -156.023529),
            (19.6890871, -156.0222476),
            (19.6876976, -156.0217351),
            (19.6862341, -156.0213333),
            (19.6828048, -156.0205156),
            (19.6807758, -156.0200423),
            (19.6788192, -156.0195322),
            (19.677135, -156.0189004),
            (19.6759216, -156.0182641),
            (19.6743497, -156.0172622),
            (19.668402, -156.013347),
            (19.6637732, -156.0103133),
            (19.6614485, -156.0088518),
            (19.6604036, -156.0083507),
            (19.6550319, -156.0057967),
            (19.6539815, -156.0051199),
            (19.6525913, -156.0040051),
            (19.6511484, -156.0024864),
            (19.6500402, -156.0007736),
            (19.6466847, -155.9942881),
            (19.6464821, -155.9938579),
            (19.6459393, -155.9939942),
            (19.6432496, -155.9954632),
            (19.6420506, -155.9961445),
            (19.6417922, -155.9961227),
            (19.6413261, -155.995503),
            (19.6411813, -155.9952675),
            (19.6410317, -155.9949242),
            (19.6409266, -155.9945051),
            (19.6405912, -155.9927503),
            (19.6404983, -155.9924162),
            (19.6403961, -155.9921837),
            (19.6402723, -155.991979),
            (19.6400823, -155.9917137),
            (19.6399251, -155.9915466),
            (19.639771, -155.991407),
            (19.6392986, -155.9910817),
            (19.6385567, -155.9906983),
            (19.6384937, -155.9906928),
            (19.6384459, -155.9907145),
            (19.6384181, -155.9907479),
            (19.637542, -155.9925406),
            (19.6375468, -155.9926079),
            (19.6375692, -155.9926886),
            (19.6380053, -155.9931088),
            (19.638172, -155.9932435),
            (19.6389512, -155.993744),
            (19.6391514, -155.993898)
        ]

        self.runtm = [80, 160, 240]

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


#TODD

        self.report_data(self.raceid, {"data": self.raceid}, colname="racelist")


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
        self.starttime = time.time()
        self.isdone = False
        logging.info("Starting race at " + str(self.starttime), "  windfactor=" + str(self.windfactor) +
                     "  heatfactor=" + str(self.heatfactor))
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
    logging.basicConfig(level=LOGLEVEL)
    logging.info('Starting HawaiiSim')

    race = Race()
    cycletime = int(os.environ.get("CYCLE_TIME"))

    race.startinterval = int(os.getenv("START_INTERVAL", 6))

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
        race.update_status(cycletime)
        rtime += cycletime
        race.update_rtime(rtime)

        cycles+=1
        if (cycles % 10 == 0):
            logging.info("" +str(datetime.timedelta(seconds=rtime)) + " --- " +
                         "  Swimmers: " + str(race.swimmers) + "  |  T1: "+str(race.t1ers) +
                         "  |  Bike: " + str(race.bikers) + "  |  T2: " + str(race.t2ers) +
                         "  |  Run: " + str(race.runners) + "  |  Finished: " + str(race.finishers) +
                         "  |  DNF: " + str(race.dnfers))
        if (cycles == 60):
            if (SHOWPLT):
                show_map()
            cycles=0

        if (SPEEDFACTOR!=9999):
            time.sleep(cycletime / SPEEDFACTOR)

    logging.info("Writing race results to data/raceresults.csv")

    f = open("data/raceresults.csv", "w")

    logging.info("Finished List contains " + str(len(race.finishedlist)) + " athletes.")
    for athlete in race.finishedlist:
        f.write(str(athlete))
        f.write("\n")

    f.close()


