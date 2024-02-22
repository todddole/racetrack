#!/usr/bin/env python3
# By Todd Dole
# generates random athletes and updates mongodb athletes

# version 0.5: initial prototype
# version 1.0: updated 2/9/2024 to add mongodb connectivity and device id
# version 1.1: added error handling
# version 1.2: added division, pros.  Changed device id and athlete id to conserve memory


from src.components.LocationDataGateway import LocationDataGateway
from src.components.Athlete import Athlete

from random import randint
import requests
import json
import time
import numpy as np


from flask_restful.inputs import url

def get_triathlete_birthday(category):
    agefactor = 0
    if (category==0):
        slot = randint(1,12)
    else:
        slot = randint(1,8)
    if (slot==1):
        year = randint(1995,2007)
    elif (slot<5):
        year = randint(1985,1995)
        agefactor = 10
    elif (slot<8):
        year = randint(1975,1985)
        agefactor = 5
    elif (slot<10):
        year = randint(1965,1975)
    elif (slot<11):
        year = randint(1955, 1965)
        agefactor = -20
    else:
        year = randint(1935, 1955)
        agefactor = -40

    month=randint(1,12)
    day=randint(1, 29)
    return agefactor, str(month) + "/" + str(day) + "/" + str(year)

def convert_to_base62(base10_number):
    # Code adapted from https://www.askpython.com/python/examples/convert-base10-integer-base64
    base62_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"

    base62_representation = ""

    while base10_number > 0:
        remainder = base10_number % 62
        base62_representation = base62_chars[remainder] + base62_representation
        base10_number //= 62
    return base62_representation


def generateAthlete(athleteid, deviceid, category):
    gendernum = randint(1, 101)
    url = "https://api.namefake.com/english-united-states/"
    headers = {
        'accept':'application/json'
        }

    if gendernum <= 35:
        params = {
            'gender': 'female'
        }
        url+="female/"
    else:
        params = {
            'gender': 'male'
        }
        url+="male/"
    response = requests.get(url, headers=headers)
    #print(response)

    if response.status_code == 200:
        data = json.loads(response.text)
    else:
        return -1


    id = str(athleteid)
    athname = data['name']
    athgender = params['gender']
    agefactor, athbirthdate = get_triathlete_birthday(category)
    if (category==0):
        strength = max(int(np.random.normal(60,10)) + agefactor, 0)
    else:
        strength = randint(91,100)

    profactor = 10*category
    athswimstr = max(min(strength + randint(-20+profactor,11), 100), -25)
    athbikestr = max(min(strength + randint(-10+(profactor//2),11), 100), -25)
    athrunstr = max(min(strength + randint(-15,11), 100), -25)

    while (athswimstr + athbikestr + athrunstr > 296):
        rednum = randint(1,3)
        if rednum == 1:
            athswimstr -= randint(1,2)
        elif rednum == 2:
            athbikestr -= randint(1,2)
        else:
            athrunstr -= randint(1,2)

    #athlete['swimstr'] = str(swimstr)
    #athlete['bikestr'] = str(bikestr)
    #athlete['runstr'] = str(runstr)
    #athlete['deviceid'] = id
    ourdeviceid = convert_to_base62(deviceid)
    if (category==1):
        if (athgender=='male'):
            division='MPRO'
        else:
            division='FPRO'
    else:
        if (athgender=='male'):
            division='AGM'
        else:
            division='AGF'


    athlete=Athlete(athname, athgender, athbirthdate, athswimstr, athbikestr, athrunstr, division, ourdeviceid)
    return id, athlete

if __name__ == '__main__':

    athletes = {}
    idlist = []
    ldg = LocationDataGateway()

    athleteid=0
    deviceid=0
    category = 0

    for i in range(10000):
        breakit = False
        try:
            if athleteid<701:
                category = 1
            else:
                category = 0
            id, athlete = generateAthlete(athleteid, deviceid, category)
            athleteid+=1
            deviceid+=1
        except Exception as e:
            breakit = True

        if (breakit):
            i-=1
            continue



        print(id + " : ", end='')
        athdump = json.dumps(athlete.__dict__)
        print(athdump)
        athletes[id]=athlete
        idlist.append(id)
        ldg.add_data(id, athdump, "athletes")
        #if (i%100 == 0): print(i)

    ldg.add_data("athlete_list", idlist, "athletes")

    #with open('data/athletes.json', 'w') as f:
    #    json.dump(athletes, f)





