
from src.components.LocationDataGateway import LocationDataGateway


CA = "2024-02-16-2"
CR = "race"+CA
RN = 2





if __name__ == '__main__':
    ldg = LocationDataGateway()
    print(CR)
    ldg.drop_collection(CR)
    a = ldg.drop_collection(CR + "-BikeTM1")
    a = ldg.drop_collection(CR + "-BikeTM2")
    a = ldg.drop_collection(CR + "-BikeTM3")
    a = ldg.drop_collection(CR + "-BikeTM4")
    a = ldg.drop_collection(CR + "-DNF")
    a = ldg.drop_collection(CR + "-RunTM1")
    a = ldg.drop_collection(CR + "-RunTM2")
    a = ldg.drop_collection(CR + "-RunTM3")
    a = ldg.drop_collection(CR + "-BikeStart")
    a = ldg.drop_collection(CR + "-EnterT1")
    a = ldg.drop_collection(CR + "-EnterT2")
    a = ldg.drop_collection(CR + "-RaceFinish")
    a = ldg.drop_collection(CR + "-RaceStart")
    a = ldg.drop_collection(CR + "-RunStart")
    a = ldg.drop_collection(CR + "-locations")

    a = ldg.del_data(str(RN), "racelist")

