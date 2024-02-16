#!/usr/bin/env python3

# V 0.1 gets race list and displays most recent race and start list

from flask import Flask, request, url_for, render_template
from src.components.LocationDataGateway import LocationDataGateway
import json

app = Flask(__name__)

@app.route("/")
def main():
    ldg = LocationDataGateway()
    racelist = ldg.get_all_data("racelist")
    if (len(racelist)==0):
        return '''<h1>No Races Found!  Come Back Later!</h1>'''

    bignum=0
    rname = ""
    for r in racelist:
        rnum = int(r["_id"])
        if (rnum>bignum):
            bignum = rnum
            rname = r["data"]
    rname = rname["data"]

    returnstr = "<h1>Today's Race: " + rname + "</h1>\n"
    returnstr += "<h2>Starters:</h2>\n"

    rname = "race"+rname
    racenumbers = ldg.get_all_data(rname)
    racenumbers = racenumbers[0]["data"]

    athletes = ldg.get_all_data("athletes")

    returnstr+="<Table><tr><th>Race Number</th><th>Name</th><th>division</th></tr>\n"


    for key in racenumbers:
        returnstr += "<tr><td>"+str(key)+"</td><td>"
        athid = int(racenumbers[key])

        for athletecount in range(len(athletes)):
            if (int((athletes[athletecount])["_id"]) == athid): break
        athlete = athletes[athletecount]["data"]


        athlete = json.loads(athlete)
        returnstr+=""+athlete["name"] + "</td><td>"+str(athlete["division"])+"</td></tr>\n"

    returnstr += "</table>\n"

    return returnstr

if __name__ == "__main__":
    app.run(debug=True, port=5001)
