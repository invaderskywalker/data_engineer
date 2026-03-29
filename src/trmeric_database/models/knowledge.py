"""
    model definitions for knowledge
"""
from peewee import *
from src.trmeric_database.BaseModel import BaseModel
from datetime import datetime
import uuid


PROJECTS_KNOWLEDGE_TYPE_CHOICES = [
    ('portfolio', 'Portfolio'),
    ('tenant', 'Tenant'),
]

class ProjectsKnowledgeModel(BaseModel):
    """
        KnowledgeModel
    """
    id = UUIDField(primary_key=True, default=uuid.uuid4)
    tenant_id = IntegerField()
    portfolio_id = IntegerField()
    type = CharField()
    knowledge_summary = TextField()
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    class Meta:
        table_name = 'tango_projectsknowledge'
    
    
# class Knowledge(Model):
#     id = BigAutoField(primary_key=True)  # bigint IDENTITY
#     project_type = CharField(max_length=100, null=False)
#     outcome = CharField(max_length=100, null=False)
#     insight = TextField(null=True)  # nullable text column
#     created_at = DateTimeTZField(null=False, default=datetime.now)
#     updated_at = DateTimeTZField(null=False, default=datetime.now)

#     def save(self, *args, **kwargs):
#         self.updated_at = datetime.now()  # Update timestamp on save
#         super(Knowledge, self).save(*args, **kwargs)

#     class Meta:
#         table_name = 'tango_knowledge'
        
        
# class ProjectAnalysis(Model):
#     id = BigAutoField(primary_key=True)
#     project_type = CharField(max_length=100, null=False)
#     outcome = CharField(max_length=100, null=False)
#     created_at = DateTimeTZField(null=False, default=datetime.now)
#     updated_at = DateTimeTZField(null=False, default=datetime.now)
#     project = IntegerField()

#     def save(self, *args, **kwargs):
#         self.updated_at = datetime.now()
#         super(ProjectAnalysis, self).save(*args, **kwargs)

#     class Meta:
#         table_name = 'tango_projectanalysis'
