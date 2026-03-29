from peewee import (
    CharField,
    TextField,
    IntegerField,
    DateTimeField,
    SmallIntegerField,
)
from src.trmeric_database.BaseModel import BaseModel


class ChatModel(BaseModel):
    id = IntegerField(primary_key=True)
    type = SmallIntegerField()  # 1 for dicover chatbot. #2 for tango
    msg_text = TextField()
    updated_on = DateTimeField()
    session_id = CharField(max_length=100)
    customer_id = IntegerField()
    project_id = IntegerField()
    tenant_id = IntegerField()
    user_id = IntegerField()

    class Meta:
        table_name = "discovery_tangochat"
