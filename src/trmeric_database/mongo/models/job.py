from datetime import datetime

class JobModel:
    def __init__(
        self,
        tenant_id,
        user_id,
        payload,
        status="pending",
        job_id=None,
        created_at=None,
        updated_at=None,
        done_at=None
    ):
        """Initialize a job model."""
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.status = status
        self.payload = payload
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
        self.done_at = done_at
        if job_id:
            self.job_id = job_id  # Optional custom job_id

    def to_dict(self):
        """Convert model to dictionary for MongoDB insertion."""
        job_dict = {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "status": self.status,
            "payload": self.payload,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "done_at": self.done_at
        }
        if hasattr(self, "job_id"):
            job_dict["job_id"] = self.job_id
        return job_dict

    @staticmethod
    def from_dict(data):
        """Create model from MongoDB document."""
        return JobModel(
            tenant_id=data.get("tenant_id"),
            user_id=data.get("user_id"),
            payload=data.get("payload"),
            status=data.get("status", "pending"),
            job_id=data.get("job_id"),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow()),
            done_at=data.get("done_at")
        )
