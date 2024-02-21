#!/bin/bash

cd ~toddd/workspace/racetrack
PATH=/usr/bin
python3 -m venv venv && source venv/bin/activate
python3 /home/toddd/workspace/racetrack/src/hawaiisim.py >> out.txt
