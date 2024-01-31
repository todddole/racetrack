#!/usr/bin/env python3

# By Todd Dole, for Data collections assignment
# Task is to retrieve some data from an API, then insert into a database
# I retrieve the first page of live flights originating from Colorado Springs
# from flightaware.com api

from components.LocationDataGateway import LocationDataGateway
import time
import requests
import json
import flask
import flask_restful



def get_a_plane():
    # Connect to
    url = "https://aeroapi.flightaware.com/aeroapi/flights/search/positions"
    headers = {
        'x-apikey':'AUJC4G4928vYB6j2jKbHjx5lpPc0Bgba'
        }
    params = {
        'origin': 'Colorado Springs'
    }

    print("Requesting flight data for flights departing Colorado Springs")
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = json.loads(response.text)
        return data



if __name__ == '__main__':
    #get some plane data and then load it into our database
    data = get_a_plane()
    print(data)

    ldg = LocationDataGateway()
    id = "PlaneTest " + str(time.time())
    x = ldg.add_data(id, data)
    if (x==id):
        print("Database update successful!  Added entry '" + x + "'")
    else:
        print("Database update failed...")

