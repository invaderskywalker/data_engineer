from datetime import datetime, timedelta

class CachingUsers:
    # Store user_id and timestamp as tuple
    ALL_USERS = []

    @staticmethod
    def addUser(user_id):
        # Add user_id with current timestamp
        CachingUsers.ALL_USERS.append((user_id, datetime.now()))

    @staticmethod
    def checkUser(user_id):
        # Current time
        now = datetime.now()
        # Check if user exists and was added within last minute
        for uid, timestamp in CachingUsers.ALL_USERS:
            if uid == user_id and now - timestamp <= timedelta(minutes=5):
                return True
        return False