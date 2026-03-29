## src.trmeric_database/mongo/dao/job.py


from pymongo import ASCENDING
from bson.objectid import ObjectId
from datetime import datetime
from src.trmeric_database.mongo.client import mongo_client
from src.trmeric_database.mongo.models.job import JobModel



class JobDAO:
    def __init__(self):
        """Initialize DAO with MongoDB client."""
        self.client = mongo_client
        self.collection = self.client.get_collection("jobs")
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create indexes for efficient querying."""
        self.collection.create_index(
            [("tenant_id", ASCENDING), ("user_id", ASCENDING), ("status", ASCENDING), ("created_at", ASCENDING)]
        )

    def create(self, job_model):
        """Create a new job document and return its ID."""
        job_dict = job_model.to_dict()
        result = self.collection.insert_one(job_dict)
        return str(result.inserted_id)

    def read(self, job_id):
        """Read a job by its _id."""
        data = self.collection.find_one({"_id": ObjectId(job_id)})
        return JobModel.from_dict(data) if data else None

    def read_by_status(self, status, limit=100):
        """Read jobs by status, sorted by created_at."""
        data = self.collection.find({"status": status}).sort("created_at", ASCENDING).limit(limit)
        return [JobModel.from_dict(item) for item in data]

    def update_status(self, job_id, status):
        """Update the status of a job."""
        update_doc = {
            "$set": {
                "status": status,
                "updated_at": datetime.utcnow()
            }
        }
        if status == "done":
            update_doc["$set"]["done_at"] = datetime.utcnow()
        
        self.collection.update_one(
            {"_id": ObjectId(job_id)},
            update_doc
        )


    def update_payload(self, job_id, payload):
        """Update the payload of a job."""
        self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"payload": payload, "updated_at": datetime.utcnow()}}
        )

    def delete(self, job_id):
        """Delete a job by its _id."""
        self.collection.delete_one({"_id": ObjectId(job_id)})

    def get_pending_job(self):
        """Get one pending job and mark it as processing (for fallback polling)."""
        data = self.collection.find_one_and_update(
            {"status": "pending"},
            {"$set": {"status": "processing", "updated_at": datetime.utcnow()}},
            sort=[("created_at", ASCENDING)],
            return_document=True
        )
        return JobModel.from_dict(data) if data else None

    def watch_jobs(self):
        """Return a change stream for new job inserts."""
        return self.collection.watch([{"$match": {"operationType": "insert"}}])

    def create_collection(self):
        """Explicitly create the jobs collection."""
        return self.client.create_collection("jobs")

    def drop_collection(self):
        """Drop the jobs collection (use with caution)."""
        return self.client.drop_collection("jobs")

    def close(self):
        """Close the MongoDB connection."""
        self.client.close()
        