from src.components.LocationDataGateway import LocationDataGateway
from src.RaceAnalyzer import *

import unittest
from unittest.mock import patch
import os
from dotenv import load_dotenv
import pymongo

# Integration Test
#   Tests that Race Analyzer is properly creating leaderboards
#   Uses a mock to change the database to a testing db
#   calls Race Analyzer to update the testing db with various calculated leaderboards based on testing db race data
#   confirms that the leaderboards are correct


class TestRaceAnalyzer(unittest.TestCase):

    def mock_setup_db(self):
        """
        Configuration method to return db instance
        """

        load_dotenv()
        dbString = f'mongodb+srv://racecollector:{os.environ.get("password")}' \
                   '@rtcluster0.pctg1sv.mongodb.net/?retryWrites=true&w=majority'

        client = pymongo.MongoClient(dbString)  # establish connection
        mongo_db = client.db

        return mongo_db

    def setUp(self):
        self.ourdb = self.mock_setup_db()




    def tearDown(self):
        pass

    def test_raceAnalyzer_1(self):
        with patch('src.components.LocationDataGateway.LocationDataGateway.setup_db', return_value=self.ourdb):
            self.race=Race()
            assert (self.race.get_race_phase("MPRO", 5)=="RaceFinish")
            self.race.make_leaderboard("MPRO","EnterT1")
            lbdata = self.race.ldg.get_data("MPRO", self.race.rname + "-Leaderboards")
            assert lbdata["1"]["number"]=="263"
            self.race.make_leaderboard("MPRO", "BikeTM3")
            lbdata = self.race.ldg.get_data("MPRO", self.race.rname + "-Leaderboards")
            assert lbdata["1"]["number"]=="556"
            self.race.make_leaderboards()

            lbdata = self.race.ldg.get_data("M80+", self.race.rname + "-Leaderboards")
            assert lbdata["3"]["number"]=="840"

            lbdata = self.race.ldg.get_data("F35-39", self.race.rname + "-Leaderboards")
            assert lbdata["10"]["number"]=="2607"


if __name__ == '__main__':
    unittest.main()
