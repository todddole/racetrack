#!/usr/bin/env python3

from flask import Flask, request, url_for, render_template
from markupsafe import escape

app = Flask(__name__)

@app.route("/")
def main():
    return '''
     <form action="/echo_user_input" method="POST">
         Lattitude:<input name="lattitude">
	 Longitude:<input name="longitude">
         <input type="submit" value="Submit!">
     </form>
     '''

@app.route("/echo_user_input", methods=["POST"])
def echo_input():
    input_lat = request.form.get("lattitude", "")
    input_long = request.form.get("longitude", "")
    return render_template('map.html') + f"<script>initMap( {escape(input_lat)}, {escape(input_long)} );</script>"
