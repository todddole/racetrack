from src.components.LocationDataGateway import LocationDataGateway

import unittest

class TestLocationDataGateway(unittest.TestCase):
    def test_add__delete_data1(self):
        lDG = LocationDataGateway()

        expected_id="test1234"
        data = "TestData1234"

        lDG.del_data(expected_id)

        retval = lDG.add_data(expected_id, data)

        assert retval == expected_id

        retval = lDG.del_data(expected_id)
        assert retval == 1

if __name__ == '__main__':
    unittest.main()