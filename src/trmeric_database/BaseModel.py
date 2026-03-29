from peewee import PostgresqlDatabase, Model
from src.trmeric_database.Database import db_instance


class BaseModel(Model):
    class Meta:
        database = db_instance.database
