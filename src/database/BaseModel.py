from peewee import Model
from src.database.Database import db_instance


class BaseModel(Model):
    class Meta:
        database = db_instance.database
