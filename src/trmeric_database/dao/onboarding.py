from src.trmeric_database.Database import db_instance


##this onboarding is not in system now so no use
class OnboardingDao:
    @staticmethod
    def getOnboardingV2Steps( id):
        query = f"""
            SELECT *
            FROM tango_onboardingv2step 
            WHERE onboarding_id = {id}
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    def getOnboardingV2EntryOfTenant(tenant_id):
        query = f"""
            SELECT * FROM tango_onboardingv2info 
            WHERE tenant_id = {tenant_id}
            LIMIT 1;
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    def insertEntryToOnboardingV2Info(tenant_id, user_id, onboarding_data):
        query = f"""
            INSERT INTO tango_onboardingv2info (tenant_id, user_id, onboarding_data, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            RETURNING id
        """
        params = (tenant_id, user_id, onboarding_data)
        db_instance.executeSQLQuery(query, params)
        
    def insertEntryOnboardingV2Step(onboarding_id, step, sub_step, session_id):
        # session_id = str(uuid.uuid4())
        query = f"""
            INSERT INTO tango_onboardingv2step (onboarding_id, step, sub_step, session_id, state, saved, created_at, updated_at)
            VALUES (%s, %s, %s, %s, 'pending', %s, NOW(), NOW())
        """
        params = (onboarding_id, step, sub_step, session_id, False)
        db_instance.executeSQLQuery(query, params)
        
    @staticmethod
    def updateEntryOnboardingV2Step(onboarding_id, step, sub_step, state):
        query = """
            UPDATE tango_onboardingv2step 
            SET state = %s, updated_at = NOW()
            WHERE onboarding_id = %s AND step = %s AND sub_step = %s
        """
        params = (state, onboarding_id, step, sub_step)
        db_instance.executeSQLQuery(query, params)
        
    @staticmethod
    def deleteEntryOnboardingV2Step(onboarding_id):
        query = """
            DELETE FROM tango_onboardingv2step 
            WHERE onboarding_id = %s
            AND saved = %s
        """
        params = (onboarding_id, False)
        db_instance.executeSQLQuery(query, params)










from src.trmeric_database.Redis import RedClient
from src.trmeric_database.dao import *

class CommonDao:

    """"
        The purpose of this dao is to create utils fxn to retrieve the most common data across other dao(s) 
        to reduce redundant database calls with redis caching
    """
    @staticmethod
    def fetch_all_tenants()->list:
        try:
            tenants = RedClient.execute(query=lambda:TenantDao.FetchAllTenantIDs(),key_set=f"AllTenantIds",expire=10**9)
            return tenants
        except Exception:
            return []

    @staticmethod
    def fetch_all_tenant_users(tenant_id:int) -> list:
        try:
            all_users = RedClient.execute(query=lambda:TenantDao.FetchUsersOfTenant(tenant_id),key_set=f"tenantUsers::tenantId::{tenant_id}", expire= 10**6)
            return all_users
        except Exception:
            return []

    @staticmethod
    def fetch_auth_info_utils(tenant_id:int, user_id:int) -> None:
        try:
            user_roles = RedClient.execute(query=lambda:AuthDao.fetchAllRolesOfUserInTenant(user_id=user_id),key_set=f"userRole::userId::{user_id}",expire=86400)
            tenant_roles = RedClient.execute(query=lambda:AuthDao.fetchAllRolesInTrmericForTenant(tenant_id=tenant_id),key_set=f"tenantRoles::tenantId::{tenant_id}",expire=86400*2)
            return user_roles,tenant_roles
        except Exception:
            return None,None

    @staticmethod
    def fetch_tenant_config_utils(tenant_id:int) -> dict:
        try:
            result = RedClient.execute(query=lambda: TenantDao.checkTenantConfig(tenant_id=tenant_id),key_set=f"tenantConfig::tenantId::{tenant_id}",expire=86400*24*7)
            return result
        except Exception:
            return {"currency_format": "USD"}


    @staticmethod
    def fetch_applicable_portfolios_utils(tenant_id:int, user_id:int) -> list[dict]:

        try:
            result = RedClient.execute(
                query = lambda: PortfolioDao.fetchApplicablePortfolios(user_id=user_id,tenant_id =tenant_id),
                key_set = f"applicablePortfolios::tenantId::{tenant_id}::userId::{user_id}"
            )
            return result
        except Exception:
            return []

    @staticmethod
    def fetch_trucible_customer_context_utils(tenant_id:int) -> dict:
        try:
            print()
            result = RedClient.execute(
                query = lambda: TenantDaoV2.fetch_trucible_customer_context(tenant_id=tenant_id),
                key_set = f"customerContext::tenantId::{tenant_id}",
                expire = 86400
            )
            return result
        except Exception:
            return {}

    @staticmethod
    def fetch_eligible_projects_utils(tenant_id:int,user_id:int, mode='vr') -> list[dict]:
        try:
            if mode == 'vr':
                project_ids = CommonDao.fetch_eligible_projects_with_archived(tenant_id=tenant_id,user_id=user_id)
            else:
                project_ids = CommonDao.fetch_eligible_projects(tenant_ido=tenant_id,user_id=user_id)
            eligible_project_id_and_names = RedClient.execute(
                query = lambda: ProjectsDao.fetchProjectsIdAndTItle(project_ids=project_ids),
                key_set = f"eligibleProjectsIdTitle::tenantId::{tenant_id}::projects::{'_'.join(str(x) for x in project_ids)}",
                expire = 86400*2
            )
            return eligible_project_id_and_names
        except Exception:
            return []

    @staticmethod
    def fetch_eliglible_roadmaps_utils(tenant_id:int, user_id:int) -> list[dict]:
        try:
            return RedClient.execute(
                query = lambda:RoadmapDao.fetchEligibleRoadmapList(tenant_id=tenant_id,user_id=user_id),
                key_set = f"eligibleRoadmaps::tenantId::{tenant_id}::userId::{user_id}",
                expire = 86400
            )
        except Exception: 
            return []

    @staticmethod
    def fetch_eliglible_programs_utils(tenant_id:int) -> list[dict]:
        try:
            return RedClient.execute(
                query = lambda: ProjectsDao.fetchAllProgramFortenant(tenant_id=tenant_id),
                key_set = f"eligiblePrograms::tenantId::{tenant_id}",
                expire = 86400
            )
        except Exception: 
            return []



    @staticmethod
    def fetch_eligible_projects(tenant_id:int,user_id:int) -> list[dict]:
        try:
            project_ids = RedClient.execute(
                query = lambda: ProjectsDao.FetchAvailableProject(tenant_id=tenant_id,user_id=user_id),
                key_set = f"eligibleProjects::tenantId::{tenant_id}::userId::{user_id}",
                expire = 86400*2
            )
            return project_ids  
        except Exception:
            return []

    @staticmethod
    def fetch_eligible_projects_with_archived(tenant_id:int,user_id:int) -> list[dict]:
        try:
            return RedClient.execute(
                query = lambda:ProjectsDao.FetchEligibleProjectsForVRAgent(tenant_id=tenant_id,user_id=user_id),
                key_set = f"eligibleProjectsWithArchived::tenantId::{tenant_id}::userId::{user_id}",
                expire = 86400*2
            )
        except Exception:
            return []



   
