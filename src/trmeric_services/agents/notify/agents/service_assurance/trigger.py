from src.trmeric_database.dao import ProjectsDao, TangoDao
from src.trmeric_services.agents.precache import ServiceAssurancePrecache
import traceback
from .analysis import ServiceAssuranceNotificationAnalyst


class TriggerServiceAssuranceNotify:
    def __init__(self):
        self.tenant_id = 625 #681
        self.user_id = 400 #381
        self.service_assurnace_precache = ServiceAssurancePrecache(tenant_id=self.tenant_id, user_id=self.user_id, init=False)
    
            
    def trigger_end_date_check_v2(self, tenant_id, user_id):
        try:
            projects_by_pms = ProjectsDao.findProjectByPmForTenant(tenant_id=tenant_id)
            self.analyst = ServiceAssuranceNotificationAnalyst(tenant_id=tenant_id, user_id=user_id)
            return self.analyst.create_end_date_analysis(projects_by_pms=projects_by_pms)
        except Exception as e:
            print("error in TriggerServiceAssuranceNotify trigger_end_date_check ", e, traceback.format_exc())
            
    def send_execution_update(self, tenant_id, user_id):
        try:
            self.analyst = ServiceAssuranceNotificationAnalyst(tenant_id=tenant_id, user_id=user_id)
            return self.analyst.send_execution_update()
        except Exception as e:
            print("error in TriggerServiceAssuranceNotify trigger_end_date_check ", e, traceback.format_exc())
            
        