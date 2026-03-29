from peewee import *
from src.trmeric_database.BaseModel import BaseModel

class Opportunity(BaseModel):
    id = BigAutoField()
    title = TextField()
    description = TextField()
    win_theme = TextField()

    class Meta:
        table_name = "opportunity_opportunity"
