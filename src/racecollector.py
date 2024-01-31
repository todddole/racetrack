# racecollector.py by Todd Dole
# api which accepts post requests with a database key and data
# then deposits the data in mongodb

from flask import Flask, request, Response
from flask_restful import Resource, Api
from components.LocationDataGateway import LocationDataGateway


app = Flask(__name__)
api = Api(app)

class PostLocData(Resource):
    def get(self):
        return {'hello': 'world'}

    def put(self, segment_id):
        data = request.form['data']
        # Add to DB
        #print("" + segment_id + " - " + data)
        ldg = LocationDataGateway()

        x=ldg.add_data(segment_id, data)
        if (x==segment_id):
            response = Response(status=201)
        else:
            response = Response(status=500)
        return response

	

api.add_resource(PostLocData, '/<string:segment_id>')

if __name__ == '__main__':
    app.run(debug=True)
