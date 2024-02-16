#!/usr/bin/env python3

# V 0.1 gets race list and displays most recent race and start list

# V 1.0 Minimum Viable Product:
#   Displays race name and clock time of current race
#   Presents a search form that allows user to search on:
#       Race Number
#       Athlete Name
#    or Age Group
#   Search Results include Race Number, Name, Division


from flask import Flask, request, url_for, render_template
from src.components.LocationDataGateway import LocationDataGateway
import json
import time
import datetime

app = Flask(__name__)

def get_header():
    ldg = LocationDataGateway()
    racelist = ldg.get_all_data("racelist")
    if (len(racelist) == 0):
        raceinfo = '''<h1>No Races Found!  Come Back Later!</h1>'''
    else:

        bignum = 0
        rname = ""
        for r in racelist:
            rnum = int(r["_id"])
            if (rnum > bignum):
                bignum = rnum
                rname = r["data"]
        rname = rname["data"]

        raceinfo = "<h1>Today's Race: " + rname + "</h1>\n"
        rname = "race" + rname
        starttime = float(ldg.get_data("starttime", rname))
        starttime = int(starttime)
        curtime = int(time.time())
        clocktime = str(datetime.timedelta(seconds=curtime - starttime))
        raceinfo += "<h2>Race Clock Time: " + clocktime + "</h2>\n"
        return ldg, raceinfo, rname

def get_division(division, birthdate, gender):
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
@app.route("/")
def main():
    ldg, raceinfo, rname = get_header()


    returnstr = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <title>Racetrack</title>
    </head>
    <body>
    
    <h1>Racetrack Race Tracking Software</h1>
    <p>About: This software currently allows real time location tracking of simulated athletes in a simulated triathlon on a certain big island in Hawaii.</p>
    
      
    '''
    returnstr += raceinfo

    returnstr += '''
    <form action="/status" method="post">
    <label for="name">Athlete Name or Race Number:</label><br>
    <input type="text" id="name" name="name"><br>
    <label for="agegroup">Or select a division:</label><br>
    <select name="agegroup" id="agegroup">
      <option value="MPRO">Male Professional</option>
      <option value="FPRO">Female Professional</option>
      <option value="M18-24">Male 18-24</option>
      <option value="F18-24">Female 18-24</option>
      <option value="M25-29">Male 25-29</option>
      <option value="F25-29">Female 25-29</option>
      <option value="M30-34">Male 30-34</option>
      <option value="F30-34">Female 30-34</option>
      <option value="M35-39">Male 35-39</option>
      <option value="F35-39">Female 35-39</option>
      <option value="M40-44">Male 40-44</option>
      <option value="F40-44">Female 40-44</option>
      <option value="M45-49">Male 45-49</option>
      <option value="F45-49">Female 45-49</option>
      <option value="M50-54">Male 50-54</option>
      <option value="F50-54">Female 50-54</option>
      <option value="M55-59">Male 55-59</option>
      <option value="F55-59">Female 55-59</option>
      <option value="M60-64">Male 60-64</option>
      <option value="F60-64">Female 60-64</option>
      <option value="M65-69">Male 65-69</option>
      <option value="F65-69">Female 65-69</option>
      <option value="M70-74">Male 70-74</option>
      <option value="F70-74">Female 70-74</option>
      <option value="M75-79">Male 75-79</option>
      <option value="F75-79">Female 75-79</option>
      <option value="M80+">Male 80+</option>
      <option value="F80+">Female 80+</option>
    </select>
      
           
    <br><input type="submit" value="submit">
    </form>
    '''

    return returnstr

@app.route("/status", methods=['POST'])
def status():
    ldg, raceinfo, rname = get_header()

    name = request.form.get('name')
    division = request.form.get('agegroup')

    number = 0
    if len(name) > 0:
        try:
            number = int(name)
        except ValueError:
            number = 0

        if (number > 0):
            type = 'racenum'
        else:
            type = 'racename'
    else:
        type = 'division'

    returnstr = raceinfo


    racenumbers = ldg.get_all_data(rname)
    racenumbers = racenumbers[0]["data"]

    athletes = ldg.get_all_data("athletes")

    returnstr+="<Table><tr><th>Race Number</th><th>Name</th><th>division</th></tr>\n"


    for key in racenumbers:
        if (type=='racenum') and (str(key)!=str(number)): continue
        athid = int(racenumbers[key])

        for athletecount in range(len(athletes)):
            if (int((athletes[athletecount])["_id"]) == athid): break
        athlete = athletes[athletecount]["data"]


        athlete = json.loads(athlete)

        if (type=='racename') and name not in athlete["name"]: continue
        mydivision = get_division(athlete["division"] , athlete["birthdate"], athlete["gender"])
        if (type=='division') and (mydivision != division): continue
        returnstr += "<tr><td>" + str(key) + "</td><td>"
        returnstr+=""+athlete["name"] + "</td><td>"+mydivision+"</td></tr>\n"

    returnstr += "</table>\n"

    return returnstr

if __name__ == "__main__":
    app.run(debug=True, port=5001)
