
## src.trmeric_database/mongo/initializer.py

from .client import mongo_client

class MongoInitializer:
    def __init__(self):
        pass
    
    def initialize_all_models(self):
        """Create collections and indexes for all models/DAOs."""
        # Initialize Job collection
        from src.trmeric_database.mongo.dao import JobDAO
        job_dao = JobDAO()
        job_dao.create_collection()   # Ensure collection exists
        job_dao._ensure_indexes()     # Ensure indexes exist

        print("✅ All Mongo models initialized.")
        