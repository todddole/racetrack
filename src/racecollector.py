# racecollector.py by Todd Dole
# api which accepts post requests with a database key and data
# then deposits the data in mongodb

# V1.0 February 1
# V1.1 February 10: Updated add_data call to include collection name (colname)
# V1.2 February 15:
#    Rewrote to use new /data endpoint


from flask import Flask, request, Response
from flask_restful import Resource, Api
from components.LocationDataGateway import LocationDataGateway
import os
import json



app = Flask(__name__)
#api = Api(app)
API_KEY = ""
DEFAULT_API_KEY = "youareanironman"

@app.route('/data', methods=['GET'])
def get_data():
    return Response("Hello World!", status=200)
@app.route('/data/<string:data_key>/', methods=['POST'])
def put_data(data_key:str):
    # add a document to mongodb
    putdata = json.loads(request.data)
    data = putdata['data']
    colname = putdata['colname']
    api_key = putdata['api-key']

    if (api_key != API_KEY):
        response = Response(status=401)
        return response

    # Request is authorized.  Add to DB

    try:
        ldg = LocationDataGateway()

        x=ldg.add_data(data_key, data, colname)
    except Exception as e:
        x=0

    if (x==data_key):
        response = Response(status=201)
    else:
        response = Response(status=500)
    return response

	

#api.add_resource(PostLocData, '/<string:segment_id>')



if __name__ == '__main__':
    API_KEY = os.getenv("API_KEY", DEFAULT_API_KEY)
    app.run(debug=True, port=5000)
