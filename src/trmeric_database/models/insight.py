from peewee import *
from src.trmeric_database.BaseModel import BaseModel

class InsightModel(BaseModel):
    tenant_id = IntegerField()
    # customer_id = IntegerField()
    insight_type = IntegerField()
    meta_id = IntegerField()
    details_text = TextField()
    updated_on = DateTimeField()
    class Meta:
        table_name = 'actions_insightsprojectspace'
class Insights(BaseModel):
    STATE_CHOICES = (
        (1, 'Created'),
        (2, 'Completed'),
        (3, 'Snooze'),
        (4, 'Hide'),
    )
    
    id = AutoField()
    tenant_id_id = IntegerField()
    user_id_id = IntegerField()
    type = CharField(max_length=50, null=True)
    tag = CharField(max_length=50, null=True)
    head_text = CharField(max_length=250, null=True)
    label_text = CharField(max_length=250, null=True)
    details_text = TextField(null=True)
    details_highlight_text = TextField(null=True)
    state = IntegerField(choices=STATE_CHOICES)
    snooze_date = DateTimeField(null=True)
    update_date = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')], null=True)
    created_date = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')], null=True)
    cron_expiry_date = DateTimeField(null=True)

    class Meta:
        table_name = 'actions_insights'
