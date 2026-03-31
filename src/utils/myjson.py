from datetime import date, datetime, timedelta
from uuid import UUID
from decimal import Decimal
import numpy as np
import pandas as pd
import json

class UniversalJSONEncoder(json.JSONEncoder):
    def default(self, obj):

        # 🔥 datetime
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()

        # 🔥 timedelta
        if isinstance(obj, timedelta):
            return obj.total_seconds()

        # 🔥 UUID
        if isinstance(obj, UUID):
            return str(obj)

        # 🔥 Decimal (DB values)
        if isinstance(obj, Decimal):
            return float(obj)

        # 🔥 numpy types
        if isinstance(obj, (np.integer,)):
            return int(obj)

        if isinstance(obj, (np.floating,)):
            return float(obj)

        if isinstance(obj, (np.bool_,)):
            return bool(obj)

        if isinstance(obj, np.ndarray):
            return obj.tolist()

        # 🔥 pandas types
        if isinstance(obj, (pd.Timestamp,)):
            return obj.isoformat()

        if isinstance(obj, (pd.Timedelta,)):
            return str(obj)

        if isinstance(obj, pd.Series):
            return obj.tolist()

        # 🔥 set
        if isinstance(obj, set):
            return list(obj)

        # 🔥 bytes
        if isinstance(obj, bytes):
            try:
                return obj.decode("utf-8")
            except Exception:
                return obj.hex()

        return super().default(obj)
    
import math

def sanitize(data):
    if isinstance(data, dict):
        return {k: sanitize(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize(v) for v in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
    return data


class MyJSON:

    @staticmethod
    def dumps(data, **kwargs):
        clean = sanitize(data)
        return json.dumps(clean, cls=UniversalJSONEncoder, **kwargs)

    @staticmethod
    def dump(data, f, **kwargs):
        clean = sanitize(data)
        return json.dump(clean, f, cls=UniversalJSONEncoder, **kwargs)
    

def safe_iso(val):
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return val


def safe_datetime(val):
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)  # fallback

