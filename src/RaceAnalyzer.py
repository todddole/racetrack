#!/usr/bin/env python3

# Version 0.1
#   Identify the current race
#   Make sure it is still running
#   Create a male pro leaderboard
#
# Version 1.0
#   Creates leaderboards for all divisions
#   Loads the leaderboards into the database
#
# Version 1.1
#   Added speed/pace column to leaderboard
#
# Version 1.2
#   Added RabbitMQ Integration:
#   Consumes RabbitMQ queue
#   On message, checks if >2 minutes have passed since last leaderboard refresh,
#     and if so, refreshes leaderboards

from src.components.LocationDataGateway import LocationDataGateway
from src.components.ClockTimes import ClockTimes, massage
import json
import time
import datetime
import logging
import sys
from geopy import distance
from src.components.constants import *
import os
import pika
from dotenv import load_dotenv

lastupdate = None
race=None
def get_pace(phase, lastphase, curtime, lasttime):
    if phase not in TIMING_MATS or lastphase not in TIMING_MATS:
        return ""
    pacetype = TIMING_MATS[phase][2]
    if (pacetype==PACE_NONE): return ""

    laptime = float(curtime) - float(lasttime)
    lapdist = TIMING_MATS[phase][1] - TIMING_MATS[lastphase][1]


    if (pacetype == PACE_SWIM_SPEED):
        secper100 = (laptime/lapdist)*100
        return str(datetime.timedelta(seconds=secper100)) + " / 100m"

    if (pacetype == PACE_BIKE_SPEED):
        kph = (lapdist/1000)/(laptime / 3600)
        mph = kph * 0.621371
        retstr = "{:.2f}".format(mph)
        return retstr + " MPH"

    if (pacetype == PACE_RUN_SPEED):
        min_per_k = (laptime/60) / (lapdist / 1000)
        min_per_mi = min_per_k / 0.621371
        sec_per_mi = min_per_mi*60

        return (str(datetime.timedelta(seconds=sec_per_mi))).split(':',1)[1].split(".")[0] + " / mi"


    return ""




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

class Race:
    def __init__(self):
        self.ldg = LocationDataGateway()
        racelist = self.ldg.get_all_data("racelist")
        if (len(racelist) == 0):
            logging.error("No racelist")
            sys.exit(-1)
        bignum = 0
        rname = ""
        for r in racelist:
            rnum = int(r["_id"])
            if (rnum > bignum):
                bignum = rnum
                rname = r["data"]
        self.rname = rname["data"]
        self.rname = "race"+self.rname
        print("rname is " + self.rname)
        self.clocktimes = ClockTimes(self.rname)

        self.swimcrs = SWIMCRS

        self.bikecrs = BIKECRS

        self.runcrs = RUNCRS
        self.racenumbers = self.ldg.get_data("racenumbers", self.rname)
        self.athletes = massage(self.ldg.get_all_data("athletes"))
        for athlete in self.athletes:
            self.athletes[athlete] = json.loads(self.athletes[athlete])
            self.athletes[athlete]["division"] = get_div(
                self.athletes[athlete]["division"],
                self.athletes[athlete]["birthdate"],
                self.athletes[athlete]["gender"]
            )

        self.starttime = 0
        while (self.starttime==0):
            try:
                ourstarttime = self.ldg.get_data("starttime", self.rname)
                self.starttime = float(ourstarttime)
                self.starttime = int(self.starttime)
            except Exception as e:
                time.sleep(10)

    def get_race_phase(self, division, min_racer):
        starters = self.clocktimes.get_phasers("RaceStart")
        for i in range(len(ANALYZER_CATEGORIES)-1, -1, -1):
            logging.debug("Testing " + ANALYZER_CATEGORIES[i])
            count = 0
            for starter in starters:
                athid = self.racenumbers[starter]
                if (self.athletes[athid]["division"] != division): continue
                if self.clocktimes.get_value(starter, ANALYZER_CATEGORIES[i]) != "": count+=1
                if count >= min_racer:
                    logging.debug("We are in race phase " + ANALYZER_CATEGORIES[i])
                    return ANALYZER_CATEGORIES[i]
        return ""


    def analyze_course_distance(self, course):
        # This is just a utility function for manual testing
        print("Leg 0 " + "  " +str(course[0][0]) + "," + str(course[0][1]))
        cumdist = 0
        for i in range(len(course)-1):
            outln = "Leg "+ str(i+1) + "  " + str(course[i][0]) + "," + str(course[i][1]) + "  "
            legdist = distance.distance(course[i], course[i+1]).m
            cumdist += legdist
            outln += str(legdist) + "  " + str(cumdist)
            print(outln)
    def make_leaderboard(self, division):
        phase = self.get_race_phase(division, 10)

        if (phase==""):
            data = {"location": "Not Started"}
            self.ldg.add_data(division, data, self.rname + "-Leaderboards")
            logging.info("Leaderboard for " + division + " Not Started")
            return

        if (phase=="RaceStart"):
            data = {"location": "Race Started"}
            self.ldg.add_data(division, data, self.rname + "-Leaderboards")
            logging.info("Leaderboard for " + division + " Race Started")
            return

        lastphase = ANALYZER_CATEGORIES[ANALYZER_CATEGORIES.index(phase) -1]
        phasers = self.clocktimes.get_phasers(phase)
        lastphasers = self.clocktimes.get_phasers(lastphase)
        divphasers = []
        divathletes = []
        times = []
        timeslast = []



        for ph in phasers:
            athid = self.racenumbers[ph]
            athlete=self.athletes[athid]
            athtime = phasers[ph]
            lasttime = lastphasers[ph]
            if (athlete["division"] == division):
                divphasers.append(athid)
                divathletes.append(athlete)
                times.append(athtime)
                timeslast.append(lasttime)

        for i in range(len(divphasers)-1):
            for j in range(i+1, len(divphasers)):
                if times[j]<times[i]:
                    times[i], times[j] = times[j], times[i]
                    timeslast[i], timeslast[j] = timeslast[j], timeslast[i]
                    divphasers[i], divphasers[j] = divphasers[j], divphasers[i]
                    divathletes[i], divathletes[j] = divathletes[j], divathletes[i]
        shownum = min(20, len(times))
        logging.info("Leaderboard for "+division+" at "+phase)

        zerotime = float(times[0])

        data = {"location":phase}

        dataarray = []
        zerotime = int(zerotime)
        leadertime = str(datetime.timedelta(seconds=zerotime - self.starttime)) + " Race Time"
        pace = get_pace(phase, lastphase, times[0], timeslast[0])
        dataarray.append({"number":divphasers[0], "name":divathletes[0]["name"], "time": leadertime, "pace":pace})


        logging.info("" + divphasers[0] + " " + divathletes[0]["name"] + " - " + leadertime + " - " + pace)
        data["1"] = dataarray[0]

        for i in range(1, shownum):
            ourtime = float(times[i])
            ourtime = int(ourtime)
            ourpace = get_pace(phase, lastphase, times[i], timeslast[i])
            if (i==1): logging.info("" + divphasers[i] + " " + divathletes[i]["name"] + " - " + times[i] + " +" +str(datetime.timedelta(seconds=ourtime - zerotime)) + " - " + ourpace)
            else: logging.debug("" + divphasers[i] + " " + divathletes[i]["name"] + " - " + times[i] + " +" +str(datetime.timedelta(seconds=ourtime - zerotime))+ " - " + ourpace)
            dataarray.append({"number": divphasers[i], "name": divathletes[i]["name"],
                              "time": "+" + str(datetime.timedelta(seconds=ourtime - zerotime)),
                              "pace":ourpace})
            data[str(i+1)] = dataarray[i]
        x=self.ldg.upsert_data(division, data, self.rname +"-Leaderboards")

    def confirm_race(self):
        racelist = self.ldg.get_all_data("racelist")
        if (len(racelist) == 0):
            logging.error("No racelist")
            sys.exit(-1)
        bignum = 0
        rname = ""
        for r in racelist:
            rnum = int(r["_id"])
            if (rnum > bignum):
                bignum = rnum
                rname = r["data"]
        newrname = rname["data"]
        newrname = "race" + newrname
        if (self.rname!=newrname): return False
        return True


    def make_leaderboards(self):
        for division in ANALYZE_DIVISIONS:
            self.make_leaderboard(division)

def callback(ch, method, properties, body):
    global lastupdate
    global race
    logging.info("Received" + str(body))
    curtime = time.time()
    if (lastupdate is not None) and (curtime - lastupdate < 120): return
    lastupdate = curtime
    if (race.confirm_race()==False): race=Race()
    race.make_leaderboards()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    load_dotenv()
    rmqurl = os.getenv("RABBITMQ_URL", "")
    rmqque = os.getenv("RABBITMQ_QUEUE", "")
    race = Race()


    try:
        params=pika.URLParameters(rmqurl)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue=rmqque)
        channel.basic_consume(rmqque,
                              callback,
                              auto_ack=True)

    except Exception as e:
        pass
    channel.start_consuming()
    connection.close()





