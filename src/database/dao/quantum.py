from src.database.Database import db_instance
from collections import defaultdict
from src.api.logging.AppLogger import appLogger


class QuantumDao:
                
    @staticmethod
    def fetchQuantumProfileForProvider(tenant_id,provider_id):
        query = f"""
            SELECT 
                tenant_id,provider_id,description,updated_by_id 
            FROM provider_profile
            WHERE tenant_id = {tenant_id} AND provider_id = {provider_id}
        """
        
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({
                "function": "fetchQuantumProfileForProvider",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []
        
        
    @staticmethod
    def fetch_aspiration(tenant_id: int, provider_id: int):
        query = f"""
            SELECT description, aspiration_docs
            FROM provider_profile
            WHERE tenant_id = {tenant_id} AND provider_id = {provider_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({
                "function": "fetch_aspiration",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []


    @staticmethod
    def fetch_core_capabilities(tenant_id: int, provider_id: int):
        query = f"""
            SELECT ptl.name AS technology_name, ptml.name AS module_name
            FROM provider_technology pt
            JOIN provider_technology_list ptl ON pt.technology_id = ptl.id
            LEFT JOIN provider_technology_module_list ptml ON pt.module_id = ptml.id
            JOIN provider_profile pp ON pt.tenant_id = pp.tenant_id
            WHERE pt.tenant_id = {tenant_id} AND pp.provider_id = {provider_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({
                "function": "fetch_core_capabilities",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []
    
    
    
    @staticmethod
    def fetch_service_catalog(tenant_id: int, provider_id: int):
        query = f"""
            SELECT ppsc.category, ppsc.name, ppsc.description, ppsc.tech_list, 
                ppsc.industry_list, ppsc.projects_executed_count, ppsc.consultants_count
            FROM provider_profile_service_category ppsc
            JOIN provider_profile pp ON ppsc.tenant_id = pp.tenant_id
            WHERE ppsc.tenant_id = {tenant_id} AND pp.provider_id = {provider_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({
                "function": "fetch_service_catalog",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []
        
        


    @staticmethod
    def fetch_industry_and_domain(tenant_id: int, provider_id: int):
        query = f"""
            SELECT 
                ppsc.category,
                ppsc.name,
                ppsc.description,
                ppsc.tech_list,
                ppsc.framework_ip_list,
                ppsc.industry_list
            FROM provider_profile_service_category ppsc
            JOIN provider_profile pp ON ppsc.tenant_id = pp.tenant_id
            WHERE ppsc.tenant_id = {tenant_id} AND pp.provider_id = {provider_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
            
        except Exception as e:
            appLogger.error({
                "function": "fetch_industry_and_domain",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []
    
    
    
    @staticmethod
    def fetch_leadership_and_team(tenant_id: int, provider_id: int):
        query_composition = f"""
            SELECT ptc.role_name, ptc.role_count
            FROM provider_team_composition ptc
            JOIN provider_profile pp ON ptc.tenant_id = pp.tenant_id
            WHERE ptc.tenant_id = {tenant_id} AND pp.provider_id = {provider_id}
        """
        query_projections = f"""
            SELECT ptp.name, ptp.month, ptp.size, ptp.year
            FROM provider_team_projections ptp
            JOIN provider_profile pp ON ptp.tenant_id = pp.tenant_id
            WHERE ptp.tenant_id = {tenant_id} AND pp.provider_id = {provider_id}
        """
        try:
            composition = db_instance.retrieveSQLQueryOld(query_composition)
            projections = db_instance.retrieveSQLQueryOld(query_projections)
            return {
                "team_composition": composition,
                "team_projections": projections
            }
        except Exception as e:
            appLogger.error({
                "function": "fetch_leadership_and_team",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return {}
    
    
    
    @staticmethod
    def fetch_voice_of_customer(tenant_id: int, provider_id: int):
        query = f"""
            SELECT 
                pvc.name as customer_name,
                pvc.email as customer_email,
                pvc.designation as customer_designation,
                pvc.org_name as customer_org_name
            FROM provider_voice_of_customer pvc
            JOIN provider_profile pp 
            ON pvc.tenant_id = pp.tenant_id
            WHERE pvc.tenant_id = {tenant_id} AND pp.provider_id = {provider_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({
                "function": "fetch_voice_of_customer",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []
    
    
    
    @staticmethod
    def fetch_offers(tenant_id: int, provider_id: int):
        query = f"""
            SELECT 
                ppo.offer_title as offer_title,
                ppo.offer_core_value_proposition as value_proposition,
                ppo.offer_solution as solution,
                ppo.offer_execution as execution, 
                ppo.outcome_for_customer as outcome_for_customer,
                ppo.pricing_model as pricing_model
            FROM provider_profileoffer ppo
            JOIN provider_profile pp 
            ON ppo.tenant_id = pp.tenant_id
            WHERE ppo.tenant_id = {tenant_id} AND pp.provider_id = {provider_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({
                "function": "fetch_offers",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []
    
    
    
    @staticmethod
    def fetch_case_studies(tenant_id: int, provider_id: int):
        query = f"""
            SELECT case_study_docs
            FROM provider_profile
            WHERE tenant_id = {tenant_id} AND provider_id = {provider_id}
        """
        try:
            result = db_instance.retrieveSQLQueryOld(query)
            return result[0]["case_study_docs"] if result else None
        except Exception as e:
            appLogger.error({
                "function": "fetch_case_studies",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return None
    
    
    
    @staticmethod
    def fetch_partnerships(tenant_id: int, provider_id: int):
        query = f"""
            SELECT ppsc.partner_list
            FROM provider_profile_service_category ppsc
            JOIN provider_profile pp 
            ON ppsc.tenant_id = pp.tenant_id
            WHERE ppsc.tenant_id = {tenant_id} AND pp.provider_id = {provider_id}
        """
        try:
            result = db_instance.retrieveSQLQueryOld(query)
            return [{"partners": row["partner_list"]} for row in result]
        except Exception as e:
            appLogger.error({
                "function": "fetch_partnerships",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []
    
    
    
    @staticmethod
    def fetch_ways_of_working(tenant_id: int, provider_id: int):
        query_steps = f"""
            SELECT psds.name, psds.description, psds.rank
            FROM provider_service_delivery_steps psds
            JOIN provider_profile pp ON psds.tenant_id = pp.tenant_id
            WHERE psds.tenant_id = {tenant_id} AND pp.provider_id = {provider_id}
        """
        query_profile = f"""
            SELECT quality_management,risk_management,payment_terms
            FROM provider_profile
            WHERE tenant_id = {tenant_id} AND provider_id = {provider_id}
        """
        try:
            steps = db_instance.retrieveSQLQueryOld(query_steps)
            profile_data = db_instance.retrieveSQLQueryOld(query_profile)
            return {
                "delivery_steps": steps,
                "profile_data": profile_data
            }
        except Exception as e:
            appLogger.error({
                "function": "fetch_ways_of_working",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return {}
    
    
    
    @staticmethod
    def fetch_information_and_security(tenant_id: int, provider_id: int):
        query = f"""
            SELECT 
                data_privacy_protocals,
                future_data_privacy_protocals, 
                info_security_protocals,
                future_info_security_protocals
            FROM provider_profile
            WHERE tenant_id = {tenant_id} AND provider_id = {provider_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({
                "function": "fetch_information_and_security",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []
    
    
    

    @staticmethod
    def fetch_certifications_and_audit(tenant_id: int, provider_id: int):
        query = f"""
            SELECT pcl.name AS certification_name, ptc.count
            FROM provider_team_certification ptc
            JOIN provider_certification_list pcl ON ptc.certificate_id = pcl.id
            JOIN provider_profile pp ON ptc.tenant_id = pp.tenant_id
            WHERE ptc.tenant_id = {tenant_id} AND pp.provider_id = {provider_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({
                "function": "fetch_certifications_and_audit",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []