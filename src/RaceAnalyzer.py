#!/usr/bin/env python3

# Version 0.1
#   Identify the current race
#   Make sure it is still running
#   Create a male pro leaderboard
#
# Version 1.0
#   Creates leaderboards for all divisions
#   Loads the leaderboards into the database

from src.components.LocationDataGateway import LocationDataGateway
from src.components.ClockTimes import ClockTimes, massage
import json
import time
import datetime
import logging
import sys
from geopy import distance
from src.components.constants import *





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
        self.starttime = float(self.ldg.get_data("starttime", self.rname))
        self.starttime = int(self.starttime)

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


        phasers = self.clocktimes.get_phasers(phase)
        divphasers = []
        divathletes = []
        times = []



        for ph in phasers:
            athid = self.racenumbers[ph]
            athlete=self.athletes[athid]
            athtime = phasers[ph]
            if (athlete["division"] == division):
                divphasers.append(athid)
                divathletes.append(athlete)
                times.append(athtime)

        for i in range(len(divphasers)-1):
            for j in range(i+1, len(divphasers)):
                if times[j]<times[i]:
                    times[i], times[j] = times[j], times[i]
                    divphasers[i], divphasers[j] = divphasers[j], divphasers[i]
                    divathletes[i], divathletes[j] = divathletes[j], divathletes[i]
        shownum = min(20, len(times))
        logging.info("Leaderboard for "+division+" at "+phase)

        zerotime = float(times[0])

        data = {"location":phase}

        dataarray = []
        zerotime = int(zerotime)
        leadertime = str(datetime.timedelta(seconds=zerotime - self.starttime)) + " Race Time"
        dataarray.append({"number":divphasers[0], "name":divathletes[0]["name"], "time": leadertime})
        logging.info("" + divphasers[0] + " " + divathletes[0]["name"] + " - " + leadertime)
        data["1"] = dataarray[0]

        for i in range(1, shownum):
            ourtime = float(times[i])
            ourtime = int(ourtime)
            if (i==1): logging.info("" + divphasers[i] + " " + divathletes[i]["name"] + " - " + times[i] + " +" +str(datetime.timedelta(seconds=ourtime - zerotime)))
            else: logging.debug("" + divphasers[i] + " " + divathletes[i]["name"] + " - " + times[i] + " +" +str(datetime.timedelta(seconds=ourtime - zerotime)))
            dataarray.append({"number": divphasers[i], "name": divathletes[i]["name"],
                              "time": "+" + str(datetime.timedelta(seconds=ourtime - zerotime))})
            data[str(i+1)] = dataarray[i]
        x=self.ldg.upsert_data(division, data, self.rname +"-Leaderboards")

    def make_leaderboards(self):
        for division in ANALYZE_DIVISIONS:
            self.make_leaderboard(division)



if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    race = Race()
    race.make_leaderboards()


