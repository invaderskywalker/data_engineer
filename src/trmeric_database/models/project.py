from peewee import *
from playhouse.postgres_ext import JSONField, DateTimeField
from datetime import datetime
from src.trmeric_database.BaseModel import BaseModel


#model for integration project_workflow update

#Left side of projIntegration data to be populated

# Project Status:
    #Scope status   -> workflow_projectstatus
    #Schedule status ->   """
    #Schedule milestones -> workflow_projectmilestones
    #Spend status ->   """"
    #Spend milestones
#Risk mitigation: -> workflow_projectrisk
#Key accomplishments: -> workflow_project (key_accomplishments)

class Project(BaseModel):
    id = AutoField()
    created_on = DateTimeField(default=datetime.now)
    ended_on = DateTimeField(default=datetime.now)
    state = CharField(max_length=250, null=True)
    current_stage = CharField(max_length=250, null=True)
    title = CharField(max_length=250, null=True)
    description = TextField()
    comparison_criterias = TextField()
    customer_id_id = IntegerField()
    tenant_id_id = IntegerField()
    customer_workflow_id_id = IntegerField()
    delivery_status = CharField(max_length=250, null=True)
    internal_project = BooleanField() 
    partner_project = BooleanField() 
    project_category = CharField(max_length=250, null=True)
    project_location = CharField(max_length=250, null=True)
    project_manager_id_id = IntegerField()
    project_type =CharField(max_length=250, null=True)
    provider_id_id = IntegerField()
    scope_status = CharField(max_length=250, null=True)
    spend_breakout = TextField()
    spend_status = CharField(max_length=250, null=True)
    spend_type = CharField(max_length=250, null=True)
    technology_stack = CharField(max_length=250, null=True)
    total_external_spend = DoubleField()
    portfolio_id_id = IntegerField()
    updated_on = DateTimeField(default=datetime.now, null=True)
    end_date = DateTimeField(default=datetime.now, null=True)
    start_date = DateTimeField(default=datetime.now, null=True)
    objectives = TextField()
    sdlc_method = CharField(max_length=100)
    created_by_id = BigIntegerField()
    archived_by_id = BigIntegerField()
    archived_on = DateTimeField(default=datetime.now, null=True)
    updated_by_id = BigIntegerField()
    parent_id = IntegerField()
    roadmap_id = IntegerField()
    created_on_stage = CharField(max_length=250, null=True)
    form_status = SmallIntegerField()
    key_accomplishments = TextField()
    member_roles = JSONField(null=True)
    archived_reason = CharField(max_length=250, null=True)
    org_strategy_align = TextField()

    class Meta:
        table_name = "workflow_project"


class ProjectStatus(BaseModel):
    id = IntegerField(primary_key=True)
    type = SmallIntegerField()
    value = SmallIntegerField()
    created_date = DateTimeField(default=datetime.now, null=True)
    comments = TextField()
    actual_percentage = SmallIntegerField()
    created_by_id = BigIntegerField()
    project_id = IntegerField()

    class Meta:
        table_name = "workflow_projectstatus"

class ProjectMilestone(BaseModel):
    id = IntegerField(primary_key=True)
    name = CharField(max_length=200)
    target_date = DateTimeField(default=datetime.now, null=True)
    planned_spend = DoubleField()
    actual_spend = DoubleField()
    project_id = IntegerField()
    team_id = IntegerField()
    actual_date = DateTimeField(default=datetime.now, null=True)
    status_value = SmallIntegerField()
    type = SmallIntegerField()
    comments = TextField()
    ref_docs = JSONField(null=True)

    class Meta:
        table_name = "workflow_projectmilestone"


class ProjectRisk(BaseModel):
    id= BigIntegerField(primary_key=True)
    description= TextField()
    impact= CharField(max_length=100)
    mitigation= TextField()
    priority = SmallIntegerField()
    due_date = DateTimeField(default=datetime.now, null=True)
    project_id = IntegerField()
    completed_on = DateTimeField()
    status_value = SmallIntegerField()

    class Meta:
        table_name = "workflow_projectrisk"


class ProjectTeamSplit(BaseModel):
    id= IntegerField(primary_key=True)
    is_external = BooleanField()
    location = CharField(max_length=50)
    team_members = DoubleField()
    spend_type = SmallIntegerField()
    project_id = IntegerField()
    provider_id = BigIntegerField(null=True)
    team_id = IntegerField()
    average_spend = DoubleField()
    member_email = CharField(max_length=255, null=True)
    member_name = CharField(max_length=300, null=True)
    member_role = CharField(max_length=50, null=True)
    member_utilization = SmallIntegerField(null=True)
    approval_status = SmallIntegerField(null=False)

    class Meta:
        table_name = "workflow_projectteamsplit"


class ProjectKPI(BaseModel):
    id= BigIntegerField(primary_key=True)
    name = TextField()
    project_id= IntegerField()
    user_id= IntegerField()
    baseline_value =  CharField(max_length=100, null=True)

    class Meta:
        table_name = "workflow_projectkpi"



#populate the db from resource data fetched from uploaded sheets
class CapacityResource(BaseModel):
    id = BigIntegerField(primary_key=True)
    first_name = CharField()
    last_name = CharField()
    country = CharField()
    email = CharField()
    role = CharField()
    skills = CharField()
    allocation = SmallIntegerField()
    experience_years = SmallIntegerField()
    experience = CharField()
    projects = CharField()
    is_active = BooleanField()
    is_external = BooleanField() #false : internal 
    created_on = DateTimeField()
    updated_on = DateTimeField()
    created_by_id = BigIntegerField()
    tenant_id = BigIntegerField()
    updated_by_id = BigIntegerField()
    trmeric_provider_tenant_id = BigIntegerField()
    external_provider_id = BigIntegerField()
    
    class Meta:
        table_name = "capacity_resource"
    
# for providers: tenant_provider in our platform map in trmeric_provider_tenant_id if exists

# external_provider_id: for this CapacityResourceProviders: id
class CapacityResourceProviders(BaseModel):
    id = BigIntegerField(primary_key=True)
    company_name = CharField()
    address = TextField()
    company_website = CharField()
    created_on = DateTimeField()
    updated_on = DateTimeField()
    created_by_id = BigIntegerField()
    tenant_id = BigIntegerField()
    updated_by_id = BigIntegerField()
    
    class Meta:
        table_name = "capacity_external_providers"
    

class CapacityResourceTimeline(BaseModel):
    
    # resource_id is mapped to CapacityResource: id
    id = BigIntegerField()
    start_date = DateField()
    end_date = DateField()
    allocation = SmallIntegerField()
    project_name = CharField(max_length=250,null=True)
    created_on = DateTimeField()
    updated_on = DateTimeField()
    created_by_id = BigIntegerField()   
    resource_id = BigIntegerField()    
    tenant_id = BigIntegerField()     
    trmeric_project_id= IntegerField()    
    updated_by_id = IntegerField()         
    
    class Meta:
        table_name = "capacity_resource_timeline"




