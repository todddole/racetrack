from dotenv import load_dotenv
import os
import json
import pymongo
import logging

class LocationDataGateway:
    def __init__(self):   
        self.db = self.setup_db()

    def setup_db(self):
        """
        Configuration method to return db instance
        """

        load_dotenv()
        dbString = f'mongodb+srv://racecollector:{os.environ.get("password")}'\
        '@rtcluster0.pctg1sv.mongodb.net/?retryWrites=true&w=majority'

        client = pymongo.MongoClient(dbString) # establish connection
        mongo_db = client.racetrackdb

        return mongo_db

    def add_data(self, id, data, collection_name):
        try:
            dbcollection = self.db[collection_name]
            x=dbcollection.insert_one({"_id": id, "data":data}).inserted_id
        except Exception as e:
            return None
        return x

    def upsert_data(self, id, data, collection_name):
        try:
            dbcollection = self.db[collection_name]
        except Exception as e:
            return None

        try:
            x = dbcollection.insert_one({"_id": id, "data": data}).inserted_id
            if (x is not None): return x
        except Exception as e:
            pass

        try:
            x=dbcollection.delete_one({"_id": id})
            x=dbcollection.insert_one({"_id": id, "data":data}).inserted_id
        except Exception as e:
            return None
        return x

    def del_data(self, id, collection_name):
        try:
            dbcollection = self.db[collection_name]
            return dbcollection.delete_one({"_id": id}).deleted_count
        except Exception as e:
            return None

    def get_data(self, id, collection_name):
        try:
            dbcollection = self.db[collection_name]
            return dbcollection.find_one({"_id":id})['data']
        except Exception as e:
            return None

    def get_all_data(self, collection_name):
        try:
            dbcollection = self.db[collection_name]
            return list(dbcollection.find())
        except Exception as e:
            return None


    def drop_collection(self, collection_name:str):
        try:
            dbcollection = self.db[collection_name]
            a = dbcollection.drop()
            logging.info("Dropped collection " + str(a))
            return dbcollection.drop()
        except Exception as e:
            print("error")
            return None

