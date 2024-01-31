#!/usr/bin/env python3

# by Todd Dole
# MVP web application for Software Architecture project
# Prompts user to input a latitude and longitude
# Then displays the location on a google map

from flask import Flask, request, url_for, render_template
from markupsafe import escape

app = Flask(__name__)

@app.route("/")
def main():
    return '''
     <form action="/echo_user_input" method="POST">
         Latitude:<input name="latitude">
	 Longitude:<input name="longitude">
         <input type="submit" value="Submit!">
     </form>
     '''

@app.route("/echo_user_input", methods=["POST"])
def echo_input():
    input_lat = request.form.get("latitude", "")
    input_long = request.form.get("longitude", "")
    return render_template('map.html') + f"<script>initMap( {escape(input_lat)}, {escape(input_long)} );</script> You entered: {escape(input_lat)}, {escape(input_long)}</body></html>"
