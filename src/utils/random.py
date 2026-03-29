
import uuid
import base64


def getShortUUID():
    uuid_value = uuid.uuid4()
    short_uuid = base64.urlsafe_b64encode(uuid_value.bytes).rstrip(b'=').decode('utf-8')[:8]
    return short_uuid


def getUUID():
    return uuid.uuid4()