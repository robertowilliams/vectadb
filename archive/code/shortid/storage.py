from pymongo import MongoClient, errors
from datetime import datetime

class IDStorage:
    def __init__(self, uri, db_name, collection_name):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.collection.create_index("id", unique=True)

    def store(self, uid):
        try:
            self.collection.insert_one({
                "id": uid,
                "created_at": datetime.utcnow()
            })
            return {"status": "ok", "id": uid}
        except errors.DuplicateKeyError:
            return {"status": "duplicate", "id": uid}
