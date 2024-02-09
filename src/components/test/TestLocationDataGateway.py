from src.components.LocationDataGateway import LocationDataGateway

import unittest

class TestLocationDataGateway(unittest.TestCase):
    def test_add__del_data1(self):
        lDG = LocationDataGateway()

        expected_id="test1234"
        data = "TestData1234"

        lDG.del_data(expected_id, "test")

        retval = lDG.add_data(expected_id, data, "test")

        assert retval == expected_id

        retval = lDG.del_data(expected_id, "test")
        assert retval == 1

    def test_add_data1(self):
        lDG = LocationDataGateway()
        expected_id="test1234"
        data = "TestData1234"

        lDG.del_data(expected_id, "test")
        retval = lDG.add_data(expected_id, data, "test")
        assert retval == expected_id

    def test_get_data1(self):
        self.test_add_data1()
        lDG = LocationDataGateway()
        expected_id="test1234"
        data = "TestData1234"
        value = lDG.get_data(expected_id, "test")
        assert value == data

    def test_del_data1(self):
        self.test_add_data1()
        lDG = LocationDataGateway()
        expected_id="test1234"
        retval = lDG.del_data(expected_id, "test")
        assert retval == 1


if __name__ == '__main__':
    unittest.main()