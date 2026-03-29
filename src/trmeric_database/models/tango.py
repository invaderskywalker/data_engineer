
from peewee import *
from playhouse.postgres_ext import JSONField, DateTimeField
from datetime import datetime
from src.trmeric_database.BaseModel import BaseModel
import uuid


class UserCache(BaseModel):
    id = AutoField()
    cache = TextField(null=True)
    created_date = DateTimeField(default=datetime.now)
    updated_date = DateTimeField(default=datetime.now)
    user_id = IntegerField()
    tenant_id = IntegerField()

    class Meta:
        table_name = "tango_usercache"


class Stats(BaseModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = IntegerField()
    tenant_id = IntegerField()
    function = CharField(max_length=250, null=True)
    model = CharField(max_length=250, null=True)
    total_tokens = IntegerField(null=True)
    prompt_tokens = IntegerField(null=True)
    completion_tokens = IntegerField(null=True)
    created_date = DateTimeField(default=datetime.now, null=True)

    class Meta:
        table_name = "tango_stats"


class TangoStates(BaseModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = IntegerField()
    tenant_id = IntegerField()
    session_id = CharField(max_length=250, null=True)
    key = CharField(max_length=250, null=True)
    value = TextField(null=True)
    created_date = DateTimeField(default=datetime.now, null=True)

    class Meta:
        table_name = "tango_states"


class TangoIntegrationSummary(BaseModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = IntegerField()
    tenant_id = IntegerField()
    key = CharField(max_length=250, null=True)
    value = TextField(null=True)
    created_date = DateTimeField(default=datetime.now, null=True)

    class Meta:
        table_name = "tango_integrationsummary"
