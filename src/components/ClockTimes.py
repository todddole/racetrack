from src.components.LocationDataGateway import LocationDataGateway
from threading import Thread
import time
import logging
from src.components.constants import *

TIME_MAT_CATEGORIES = ANALYZER_CATEGORIES

TIME_THRESHOLD = 120
def massage(mylist):
    retdict = {}
    for item in mylist:
        retdict[item["_id"]] = item["data"]
    return retdict

class ClockTimesRefresher(Thread):
    def setup(self, ct):
        self.clocktime = ct

    def run(self):
        pass


class ClockTimes:
    def __init__(self, rname):
        self.ldg = LocationDataGateway()
        #self.refresher = ClockTimesRefresher()
        #self.refresher.setup(self)
        #self.refresher.start()
        self.starttime = time.time()
        self.rname = rname

        self.timedata = []
        self.lastupdates = []
        for category in TIME_MAT_CATEGORIES:
            self.timedata.append({})
            self.lastupdates.append(0)

        for i in range(len(TIME_MAT_CATEGORIES)):
            call_name = self.rname + "-" + TIME_MAT_CATEGORIES[i]
            data = self.ldg.get_all_data(call_name)
            self.timedata[i]=massage(data)
            logging.debug(" init "+TIME_MAT_CATEGORIES[i] + " size "+str(len(self.timedata[i])))
            self.lastupdates[i] = time.time()

    def refresh_data(self, index):
        logging.debug("Refreshing Data")
        self.timedata[index] = massage(self.ldg.get_all_data(self.rname + "-" + TIME_MAT_CATEGORIES[index]))
        self.lastupdates[index] = time.time()

    def get_starters(self):
        self.refresh_data(0)
        return self.timedata[0]

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









