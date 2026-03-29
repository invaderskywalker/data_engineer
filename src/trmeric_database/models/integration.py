from peewee import *
from playhouse.postgres_ext import JSONField, DateTimeField
from datetime import datetime
from src.trmeric_database.BaseModel import BaseModel


class Integrations(BaseModel):
    integration_name = CharField(max_length=100)
    created_date = DateTimeField(
        default=datetime.now
    )  # Corrected to datetime.now without parentheses
    created_by_id = IntegerField()
    tenant_id = IntegerField()
    status = CharField(
        max_length=20,
        choices=[("Active", "Active"), ("Inactive", "Inactive")],
        default="Active",
    )
    metadata = JSONField()

    class Meta:
        table_name = "integration_integrations"


class IntegrationProjectsMapping(BaseModel):
    external_id = CharField(max_length=100)
    project_id = IntegerField()
    integration_name = CharField(max_length=100)
    created_date = DateTimeField(default=datetime.now)
    created_by_id = IntegerField()
    tenant_id = IntegerField()

    class Meta:
        table_name = "integration_integrationprojectsmapping"


class IntegrationData(BaseModel):
    external = ForeignKeyField(
        IntegrationProjectsMapping, backref="integrations_mapping"
    )
    # external_id = CharField(max_length=100)
    created_date = DateTimeField(default=datetime.now)
    metadata = JSONField()

    class Meta:
        table_name = "integration_integrationdata"


class UserConfig(BaseModel):
    id = AutoField()
    integration_type = CharField(max_length=100)
    created_date = DateTimeField(default=datetime.now)
    user_id = IntegerField()
    tenant_id = IntegerField()
    status = CharField(max_length=20, choices=(
        ('Active', 'Active'), ('Inactive', 'Inactive')), default='Active')
    metadata = JSONField(null=True)

    class Meta:
        table_name = "integration_userconfig"


class ProjectMapping(BaseModel):
    id = AutoField()
    integration_project_identifier = CharField(max_length=100)
    trmeric_project_id = IntegerField()
    integration_type = CharField(max_length=100)
    created_date = DateTimeField(default=datetime.now)
    user_id = IntegerField()
    tenant_id = IntegerField()
    metadata = JSONField(null=True)
    # user_config = ForeignKeyField(
    #     UserConfig, backref='mapping_user_config', null=True, on_delete='SET NULL')
    
    user_config_id = IntegerField()

    class Meta:
        table_name = "integration_projectmapping"


class ProjectData(BaseModel):
    user_id = IntegerField()
    tenant_id = IntegerField()
    data = JSONField()
    last_updated_date = DateTimeField(default=datetime.now)
    trmeric_project_id = IntegerField()
    project_mapping = ForeignKeyField(
        ProjectMapping, backref='integration_project_data_mapping', null=True, on_delete='SET NULL')

    class Meta:
        table_name = "integration_projectdata"