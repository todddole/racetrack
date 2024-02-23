from src.components.LocationDataGateway import LocationDataGateway
from threading import Thread
import time
import logging
from src.components.constants import *
import json

TIME_MAT_CATEGORIES = ANALYZER_CATEGORIES[:]
TIME_MAT_CATEGORIES.append("DNF")

TIME_THRESHOLD = 120
def massage(mylist):
    retdict = {}
    for item in mylist:
        retdict[item["_id"]] = item["data"]
    return retdict

class ClockTimesRefresher(Thread):
    def setup(self, ct):
        self.clocktimes = ct

    def run(self):
        for i in range(len(TIME_MAT_CATEGORIES)):
            call_name = self.clocktimes.rname + "-" + TIME_MAT_CATEGORIES[i]
            data = self.clocktimes.ldg.get_all_data(call_name)
            self.clocktimes.timedata[i] = massage(data)
            logging.debug(" init " + TIME_MAT_CATEGORIES[i] + " size " + str(len(self.clocktimes.timedata[i])))
            self.clocktimes.lastupdates[i] = time.time()
        self.clocktimes.locdata = self.clocktimes.ldg.get_all_data(self.clocktimes.rname + "-locationlasts")
        self.clocktimes.locupdate = time.time()

        self.clocktimes.racenumbers = self.clocktimes.ldg.get_data("racenumbers", self.clocktimes.rname)
        athletes = self.clocktimes.ldg.get_all_data("athletes")
        self.clocktimes.athletes=athletes
        if self.clocktimes.athletes[len(self.clocktimes.athletes)-1]["_id"] == "athlete_list":
            del self.clocktimes.athletes[len(self.clocktimes.athletes)-1]

        self.clocktimes.devices = {}
        for key in self.clocktimes.racenumbers:

            athid = int(self.clocktimes.racenumbers[key])

            for athletecount in range(len(athletes)):
                if (int((athletes[athletecount])["_id"]) == athid): break
            athlete = athletes[athletecount]["data"]

            athlete = json.loads(athlete)
            self.clocktimes.devices[key] = athlete["deviceid"]
        self.clocktimes.ready=True

class ClockTimes:
    def __init__(self, rname):
        self.ldg = LocationDataGateway()
        self.refresher = ClockTimesRefresher()
        self.refresher.setup(self)
        self.starttime = time.time()
        self.rname = rname

        self.timedata = []
        self.lastupdates = []
        for category in TIME_MAT_CATEGORIES:
            self.timedata.append({})
            self.lastupdates.append(0)

        self.ready=False
        self.refresher.start()




    def refresh_data(self, index):
        logging.debug("Refreshing Data")
        self.timedata[index] = massage(self.ldg.get_all_data(self.rname + "-" + TIME_MAT_CATEGORIES[index]))
        self.lastupdates[index] = time.time()

    def get_starters(self):
        self.refresh_data(0)
        return self.timedata[0]

    def get_racenumbers(self):
        return self.racenumbers

    def get_device(self, athid):
        if athid in self.devices.keys():
            return self.devices[athid]
        return None
    def get_locations(self):
        if (time.time() - self.locupdate > 60):
            self.locdata = self.ldg.get_all_data(self.rname + "-locationlasts")
            self.locupdate = time.time()
        return self.locdata

    def get_location_and_time(self, athid):
        if (athid is None) or (athid == ""): return None, None
        if (time.time() - self.locupdate > 60):
            self.locdata = self.ldg.get_all_data(self.rname + "-locationlasts")
            self.locupdate = time.time()
        devid = self.get_device(athid)

        bestlocation=None
        bestloctime=None
        for location in self.locdata:
            if (devid) != location["_id"]: continue
            thisdata = location["data"]
            bestloctime = float(thisdata["time"])
            bestlocation = (float(thisdata["la"]), float(thisdata["lo"]))
        return bestlocation, bestloctime



    def get_phasers(self, phase):
        if phase not in TIME_MAT_CATEGORIES: return None
        index = TIME_MAT_CATEGORIES.index(phase)
        self.refresh_data(index)
        return self.timedata[index]

    def get_value(self, key, category):
        if category not in TIME_MAT_CATEGORIES:
            return ""

        index = TIME_MAT_CATEGORIES.index(category)
        if (time.time() - self.lastupdates[index]) > TIME_THRESHOLD:
            self.refresh_data(index)
        if key not in self.timedata[index]:
            return ""
        return self.timedata[index][key]









