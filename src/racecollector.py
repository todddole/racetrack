# racecollector.py by Todd Dole
# api which accepts post requests with a database key and data
# then deposits the data in mongodb

# V1.0 February 1
# V1.1 February 10: Updated add_data call to include collection name (colname)
# V1.2 February 15:
#    Rewrote to use new /data endpoint
# V1.3 February 17:
#    Switched to upsert data, so if part of a multipart fails to update the
#      first time around, it won't cause problems on the second try

from flask import Flask, request, Response
from flask_restful import Resource, Api
from components.LocationDataGateway import LocationDataGateway
import os
import json



app = Flask(__name__)
#api = Api(app)
API_KEY = ""
DEFAULT_API_KEY = "2468appreciate"
LDG = None


@app.route('/data', methods=['GET'])
def get_data():
    return Response("Hello World!", status=200)
@app.route('/location/<string:data_key>/', methods=['POST'])
def put_loc_data(data_key:str):
    # add a document to mongodb
    global LDG
    putdata = json.loads(request.data)
    data = putdata['data']
    colname = putdata['colname']
    seccolname = colname.replace("location", "locationlast")
    api_key = putdata['api-key']

    if (api_key != API_KEY):
        response = Response(status=401)
        return response

    # Request is authorized.  Add to DB
    if data_key == "multipart":

        if type(data)==str :
            data = json.loads(data)
        retstat = 201
        try:
            for key in data:
                value = data[key]

                x = LDG.upsert_data(key, value, colname)
                if (x!=key):
                    print("  Error: x=" + x + " key=" + key + " value=" + value)
                    retstat = 500
                key2=key.split("-")[0]
                x = LDG.upsert_data(key2, value, seccolname)
                if (x != key2):
                    print("  Error: x=" + x + " key=" + key + " value=" + value)
                    retstat = 500


        except Exception as e:
            retstat = 500

        if (retstat == 201):
            response = Response(status=201)
        else:
            response = Response(status=500)

    else:

        try:
            x = LDG.add_data(data_key, data, colname)

        except Exception as e:
            x = 0

        if (x == data_key):
            response = Response(status=201)
        else:
            response = Response(status=500)

        key2 = data_key.split("-")[0]
        x = LDG.upsert_data(key2, data, seccolname)
        if (x != key2):
            print("  Error: x=" + x + " key=" + key + " value=" + value)
            response = Response(status=500)

    return response

@app.route('/data/<string:data_key>/', methods=['POST'])
def put_data(data_key:str):
    global LDG
    # add a document to mongodb
    putdata = json.loads(request.data)
    data = putdata['data']
    colname = putdata['colname']
    api_key = putdata['api-key']

    if (api_key != API_KEY):
        response = Response(status=401)
        return response

    # Request is authorized.  Add to DB
    if data_key == "multipart":
        if type(data)==str :
            data = json.loads(data)
        retstat = 201
        try:

            for key in data:
                value = data[key]

                x = LDG.upsert_data(key, value, colname)
                if (x!=key):
                    print("  Error: x=" + x + " key=" + key + " value=" + value)
                    retstat = 500

        except Exception as e:
            retstat = 500

        if (retstat == 201):
            response = Response(status=201)
        else:
            response = Response(status=500)

    else:

        try:
            ldg = LocationDataGateway()

            x = LDG.add_data(data_key, data, colname)
        except Exception as e:
            x = 0

        if (x == data_key):
            response = Response(status=201)
        else:
            response = Response(status=500)
    return response

#api.add_resource(PostLocData, '/<string:segment_id>')



if __name__ == '__main__':
    API_KEY = os.getenv("API_KEY", DEFAULT_API_KEY)
    print("API KEY: " + API_KEY)
    LDG = LocationDataGateway()
    app.run(debug=False, port=5000)
