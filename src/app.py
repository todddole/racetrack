#!/usr/bin/env python3

# V 0.1 gets race list and displays most recent race and start list

# V 1.0 Minimum Viable Product:
#   Displays race name and clock time of current race
#   Presents a search form that allows user to search on:
#       Race Number
#       Athlete Name
#    or Age Group
#   Search Results include Race Number, Name, Division
#
# V1.1 Search Results Improvement
#   Added Start Time, Swim Time, T1, Bike, Run, Finish Time
#   Added Status
#
# V1.2 ClockTimes Refactor
#   Added ClockTimes data gateway for Timing Mat Times
#
# V1.3 Add Detail endpoint
#   Added detail endpoint (just displays athlete id for now)
#   Added an "ALL" dropdown option
#   Constants file
#   Added Leaderboard to front page V1.0
#
# V1.4 RabbitMQ Integration
#   Sends a rabbitmq message for RaceAnalyzer whenever someone gets /
#   RaceAnalyzer checks if it's been more than 2 minutes since leaderboards were refreshed,
#   and refreshes them if so
#   (note that for now, this probably won't reflect on the current get)
#
# V1.5 Maps Implementation
#   Added Google Map to Details Page
#   Added Google Map to / with all the athletes in the currently selected leaderboard division
#


from flask import Flask, request, url_for, render_template
from src.components.LocationDataGateway import LocationDataGateway
from src.components.ClockTimes import ClockTimes
import json
import time
import datetime
import logging
from src.components.constants import *
import pika
import os
from dotenv import load_dotenv


app = Flask(__name__)
clocktimes = None

def send_rabbit_mq(message):

    rmqurl = os.getenv("RABBITMQ_URL", "")
    rmqque = os.getenv("RABBITMQ_QUEUE", "")

    try:
        params=pika.URLParameters(rmqurl)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.queue_declare(queue=rmqque)
        channel.basic_publish(exchange='',
                              routing_key=rmqque,
                              body=message)
        connection.close()
    except Exception as e:
        pass

def get_header():
    # does a few common page functions:
    # gets and returns ldg
    # returns the top of an html page with race name and current race clock
    # returns current race name (rname) for future data calls
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

def massage(mylist):
    # utility function that fixes data from LocationDataGateway
    retdict = {}
    for item in mylist:
        retdict[item["_id"]] = item["data"]
    return retdict
@app.route("/")
def main():
    send_rabbit_mq("leaderboard")
    leaderboard = request.args.get('leaderboard', default="MPRO")
    global clocktimes
    ldg, raceinfo, rname = get_header()
    if clocktimes is None: clocktimes = ClockTimes(rname)
    if (rname!=clocktimes.rname) : clocktimes = ClockTimes(rname)

    returnstr = render_template('map.html')
    returnstr += '''
    
    
    <h1>Racetrack Race Tracking Software</h1>
    <p>About: This software currently allows real time location tracking of simulated athletes in a simulated triathlon on a certain big island in Hawaii.</p>
    <p>Any resemblence to real people or races is purely coincidental.</p>
    <p>A description of the project maybe found at <a href="https://github.com/todddole/racetrack">https://github.com/todddole/racetrack</a></p>
      
    '''
    returnstr += raceinfo

    returnstr += '''
    <h3>Search by athlete name, race number, or race division:</h3>
    <form action="/status" method="post">
    <label for="name">Athlete Name or Race Number:</label><br>
    <input type="text" id="name" name="name"><br>
    <label for="agegroup">Or select a division:</label><br>
    <select name="agegroup" id="agegroup">
      <option value="ALL">All Racers</option>
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
    <br>
    <br>
    <h1>Race Leaderboard: 
    '''

    leaderboardorig = leaderboard
    if leaderboard=="M80": leaderboard="M80+"
    elif leaderboard=="F80": leaderboard="F80+"
    if (leaderboard not in ANALYZE_DIVISIONS):
        returnstr += "Error, division not found</h1>"
        return returnstr

    returnstr += leaderboard
    lbdata = ldg.get_data(leaderboard, rname+"-Leaderboards")
    if (lbdata is None):
        returnstr += " -- No Data Yet</h1>"
    else:
        lblocation = lbdata["location"]

        pacetype = PACE_NONE
        if lblocation in TIMING_MATS.keys():
            pacetype = TIMING_MATS[lblocation][2]
            lblocation = TIMING_MATS[lblocation][0]

        returnstr += " at " + lblocation + "</h1>\n"

    returnstr += '''
    <form id="lbform" action="/" method="get"><br>
    <label for="leaderboard">Show Leaderboard For:</label>
    <select name="leaderboard" id="leaderboard">
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
      <option value="M80">Male 80+</option>
      <option value="F80">Female 80+</option>
    </select>
    <input type=submit value="submit">
    </form><br>
        
    '''

    returnstr = returnstr.replace("value=\""+leaderboardorig+"\">", "value=\""+leaderboardorig+"\" selected>")

    if (lbdata is not None):
        returnstr += "<table><TR><TH>Race Number</TH><TH>Name</TH><TH>Time Behind Leader</TH>"
        if (pacetype!=PACE_NONE): returnstr += "<TH>Speed:</TH>"
        returnstr += "</TR>\n"
        for i in range(1,21):
            key = str(i)
            if key in lbdata.keys():
                returnstr += "<tr><td>" + str(lbdata[key]["number"]) + "</td><td>" + \
                    str(lbdata[key]["name"]) + "</td><td>" + str(lbdata[key]["time"]) + "</td>"
                if (pacetype != PACE_NONE): returnstr += "<td>" + str(lbdata[key]["pace"]) +"</td>"
                returnstr+="</tr>\n"


        returnstr += "</table>"

    # Add the Map

    racenumbers = clocktimes.racenumbers

    athletes = clocktimes.athletes

    maplocs = []
    dnfers = clocktimes.get_phasers("DNF")

    for key in racenumbers:
        if key in dnfers.keys(): continue
        athid = int(racenumbers[key])

        for athletecount in range(len(athletes)):
            if (int((athletes[athletecount])["_id"]) == athid): break
        athlete = athletes[athletecount]["data"]

        athlete = json.loads(athlete)

        mydivision = get_division(athlete["division"] , athlete["birthdate"], athlete["gender"])
        if (mydivision != leaderboard): continue

        ####
        location, loctime = clocktimes.get_location_and_time(key)
        if (location is not None):
            maplocs.append((location, athlete["name"]))

    locs = [maplocs[i][0] for i in range (len(maplocs))]

    input_lat = sum([locs[i][0] for i in range(len(locs))] ) / len (locs)
    input_long = sum([locs[i][1] for i in range(len(locs))]) / len (locs)

    returnstr += "<h3>Location Map for "+leaderboard+"</h3><br>"
    returnstr += "<div id=\"map\"></div>"
    returnstr += "<script>initMap( " + str(input_lat) + ", " + str(input_long) + " );\n"

    for maploc in maplocs:
        input_lat = maploc[0][0]
        input_long = maploc[0][1]
        input_name = maploc[1]
        returnstr += "addMarker("+ str(input_lat) + ", " + str(input_long) + ", \""+str(input_name)+"\");\n"
    returnstr += "</script>"

    return returnstr
@app.route('/detail', methods=['GET'])
def detail():
    global clocktimes
    send_rabbit_mq("leaderboard")
    athid = request.args.get('id')

    ldg, raceinfo, rname = get_header()
    location, loctime = clocktimes.get_location_and_time(athid)


    returnstr = render_template('map.html')
    for athletecount in range(len(clocktimes.athletes)):
        if (int((clocktimes.athletes[athletecount])["_id"]) == athid): break
    athlete = clocktimes.athletes[athletecount]["data"]
    athlete = json.loads(athlete)

    returnstr += "<H1>Details for " + athlete["name"] + "</H1>:"
    returnstr += "Last Known Location:<br>\n"
    secondsago = int(time.time() - float(loctime))
    returnstr += str(location) + ", reported " + str(secondsago) + " seconds ago<br>\n"

    input_lat = location[0]
    input_long = location[1]


    returnstr += "<h3>Current Location:</h3><br>"
    returnstr += "<div id=\"map\"></div>"

    returnstr += "<script>initMap( " + str(input_lat) + ", " + str(input_long) + " );\n"
    returnstr += "addMarker(" + str(input_lat) + ", " + str(input_long) + ", 'Location');\n</script>"
    return returnstr


@app.route("/status", methods=['POST'])
def status():
    global clocktimes

    send_rabbit_mq("leaderboard")
    ldg, raceinfo, rname = get_header()
    if clocktimes is None: clocktimes = ClockTimes(rname)
    if (rname!=clocktimes.rname) : clocktimes = ClockTimes(rname)

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


    racenumbers = clocktimes.racenumbers

    athletes = clocktimes.athletes

    returnstr += '''<Table border=1 padding=10px><tr><th>Race Number</th><th>Name</th><th>division</th><th>Status</th>
            <th>Start Time</th><th>Swim</th><th>T1</th><th>Bike</th><th>T2</th><th>Run</th><th>Finish</th>
            </tr>
        '''

    for key in racenumbers:
        if (type=='racenum') and (str(key)!=str(number)): continue
        athid = int(racenumbers[key])

        for athletecount in range(len(athletes)):
            if (int((athletes[athletecount])["_id"]) == athid): break
        athlete = athletes[athletecount]["data"]
        athlete = json.loads(athlete)

        if (type == 'racename') and name not in athlete["name"]: continue
        mydivision = get_division(athlete["division"] , athlete["birthdate"], athlete["gender"])
        if (type == 'division') and (division!="ALL") and (mydivision != division): continue
        returnstr += "<tr><td><a href='/detail?id=" + str(key) + "'>" + str(key) + "</a></td><td>"
        returnstr += ""+athlete["name"] + "</td><td>"+mydivision+"</td>\n"

        status = ""
        if clocktimes.get_value(key, "DNF")!= "": status = "Did Not Finish"
        elif clocktimes.get_value(key, "RaceFinish") != "": status = "Finished"
        elif clocktimes.get_value(key, "RaceStart") != "": status = "Racing"
        returnstr+="<td>" + status + "</td>\n"

        # Race Start
        time_str=""
        rs = clocktimes.get_value(key, "RaceStart")
        if (rs!=""): time_str = datetime.datetime.fromtimestamp(float(rs)).strftime("%H:%M:%S")
        returnstr += "<td>" + time_str
        returnstr += "</td>\n"

        #Swim Time
        time_str = ""
        t1 = clocktimes.get_value(key, "EnterT1")
        if (t1!="") and (rs!=""): time_str = str(datetime.timedelta(seconds=int(float(t1) - float(rs))))
        returnstr += "<td> " + time_str
        returnstr += "</td>\n"

        #T1 Time
        time_str = ""
        bs = clocktimes.get_value(key, "BikeStart")
        if (bs!="") and (t1!=""): time_str = str(datetime.timedelta(seconds=int(float(bs) - float(t1))))
        returnstr += "<td> " + time_str
        returnstr += "</td>\n"

        #Bike Time
        time_str = ""
        t2 = clocktimes.get_value(key, "EnterT2")
        if (t2!="")and (bs!=""): time_str = str(datetime.timedelta(seconds=int(float(t2) - float(bs))))
        returnstr += "<td> " + time_str
        returnstr += "</td>\n"

        #T2 Time
        time_str = ""
        rns = clocktimes.get_value(key, "RunStart")
        if (rns!="") and (t2!=""): time_str = str(datetime.timedelta(seconds=int(float(rns) - float(t2))))
        returnstr += "<td> " + time_str
        returnstr += "</td>\n"

        #Run Time
        time_str = ""
        fin = clocktimes.get_value(key, "RaceFinish")
        if (fin!="") and (rns!=""): time_str = str(datetime.timedelta(seconds=int(float(fin) - float(rns))))
        returnstr += "<td> " + time_str
        returnstr += "</td>\n"

        # Total
        time_str = ""
        if (fin!="") and (rs!=""): time_str = str(datetime.timedelta(seconds=int(float(fin) - float(rs))))
        returnstr += "<td> " + time_str
        returnstr += "</td>\n"

        returnstr += "</tr>\n"

    returnstr += "</table>\n"

    return returnstr

if __name__ == "__main__":
    load_dotenv()
    app.run(debug=False, port=5001)
    ldg, raceinfo, rname = get_header()
    if clocktimes is None: clocktimes = ClockTimes(rname)
    if (rname!=clocktimes.rname) : clocktimes = ClockTimes(rname)
    logging.info("Accepting Connections...")


