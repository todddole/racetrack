from src.components.LocationDataGateway import LocationDataGateway
from src.components.ClockTimes import ClockTimes
import unittest
from unittest.mock import patch
import os
from dotenv import load_dotenv
import pymongo

class TestClockTimes(unittest.TestCase):

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


    def test_refresh_data1(self):
        with patch('src.components.LocationDataGateway.LocationDataGateway.setup_db', return_value=self.ourdb):
            clocktimes = ClockTimes("race2024-02-21-1")
            clocktimes.refresh_data(0)
            assert clocktimes.timedata[0]['1'] == '1708518605.5327725'


    def test_get_value1(self):
        with patch('src.components.LocationDataGateway.LocationDataGateway.setup_db', return_value=self.ourdb):
            clocktimes = ClockTimes("race2024-02-21-1")
            clocktimes.refresh_data(0)
            a = clocktimes.get_value('1','RaceStart')
            assert a == '1708518605.5327725'

    def test_get_phasers1(self):
        with patch('src.components.LocationDataGateway.LocationDataGateway.setup_db', return_value=self.ourdb):
            clocktimes = ClockTimes("race2024-02-21-1")
            clocktimes.refresh_data(0)
            a = clocktimes.get_phasers("BikeTM1")
            assert a['250'] == '1708524581.2712736'



if __name__ == '__main__':
    unittest.main()