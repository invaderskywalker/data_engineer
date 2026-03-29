from src.trmeric_database.Database import db_instance
from collections import defaultdict
from src.trmeric_api.logging.AppLogger import appLogger


class ProviderDao:
    @staticmethod
    def fetchAllDataFromServiceProviderDetailsTable():
        query = f"""
            select *  from tenant_serviceproviderdetails;
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    

    @staticmethod
    def fetchDataForRecomendation(service_provider_ids):
        ## fetch service catalog of provider - service category, dservice name, tech expertise
        service_provider_ids_str = f"({', '.join(map(str, service_provider_ids))})" 
        query = f"""
            SELECT service_provider_id, service_category, service_name FROM discovery_trmericproviderservicecatalog
            where service_provider_id in {service_provider_ids_str}
        """
        service_catalog = db_instance.retrieveSQLQueryOld(query)
        
        ## fetch capabilities
        query = f"""
            select service_provider_id, key_technologies, industries_we_work, partnerships, strength_area from tenant_providercapabilities
            where service_provider_id in  {service_provider_ids_str}
        """
        capabilities = db_instance.retrieveSQLQueryOld(query)
        
        
        ## case studies
        query = f"""
            select service_provider_id, case_study_title from tenant_providercasestudies
            where service_provider_id in  {service_provider_ids_str}
        """
        case_studies = db_instance.retrieveSQLQueryOld(query)
        
        
        ## trmeric assesment
        query = f"""
            select 
            service_provider_id, 
            expertise_detail, 
            why_tr_recommends,
                expertise_tr_rating,
                delivery_tr_rating,
                satisfaction_tr_rating,
                innovation_tr_rating,
                communication_tr_rating,
                reliability_tr_rating    
            from tenant_providertrmericassessment
            where service_provider_id in  {service_provider_ids_str}
        """
        assessment = db_instance.retrieveSQLQueryOld(query)
        
        
        
        grouped_data = defaultdict(lambda: {
            "service_catalog": [],
            "capabilities": {},
            "case_studies": [],
            "trmeric_assessment": {}
        })
        
        # Process service catalog
        for row in service_catalog:
            service_provider_id = row["service_provider_id"]
            grouped_data[service_provider_id]["service_catalog"].append({
                "service_category": row["service_category"],
                "service_name": row["service_name"]
            })
            
        # Process capabilities
        for row in capabilities:
            service_provider_id = row["service_provider_id"]
            grouped_data[service_provider_id]["capabilities"] = {
                "key_technologies": row["key_technologies"],
                "industries_we_work": row["industries_we_work"],
                "partnerships": row["partnerships"],
                "strength_area": row["strength_area"]
            }
            
            
        # Process case studies
        for row in case_studies:
            service_provider_id = row["service_provider_id"]
            grouped_data[service_provider_id]["case_studies"].append({
                "case_study_title": row["case_study_title"]
            })
            
            
        # Process trmeric assessment
        for row in assessment:
            service_provider_id = row["service_provider_id"]
            grouped_data[service_provider_id]["trmeric_assessment"] = {
                "expertise_detail": row["expertise_detail"],
                "why_tr_recommends": row["why_tr_recommends"],
                "expertise_tr_rating": row["expertise_tr_rating"],
                "delivery_tr_rating": row["delivery_tr_rating"],
                "satisfaction_tr_rating": row["satisfaction_tr_rating"],
                "innovation_tr_rating": row["innovation_tr_rating"],
                "communication_tr_rating": row["communication_tr_rating"],
                "reliability_tr_rating": row["reliability_tr_rating"]
            }
            
        grouped_data = dict(grouped_data)
        return grouped_data
    
    
    @staticmethod
    def createProviderSummary(grouped_data):
        provider_summaries = []

        # Loop through the grouped data and generate a summary for each provider
        for service_provider_id, data in grouped_data.items():
            summary = []
            
            summary.append(f"----------------Summary of provider id {service_provider_id}--------------------------------------------")

            # Adding Service Catalog to the summary
            summary.append(f"Service Catalog for Provider {service_provider_id}:")
            for catalog in data["service_catalog"]:
                summary.append(f"  - Service Category: {catalog['service_category']}, Service Name: {catalog['service_name']}")
            
            # Adding Capabilities to the summary
            summary.append(f"\nCapabilities for Provider {service_provider_id}:")
            capabilities = data["capabilities"]
            summary.append(f"  - Key Technologies: {capabilities.get('key_technologies')}")
            summary.append(f"  - Industries We Work In: {capabilities.get('industries_we_work')}")
            summary.append(f"  - Partnerships: {capabilities.get('partnerships')}")
            summary.append(f"  - Strength Areas: {capabilities.get('strength_area')}")
            
            # Adding Case Studies to the summary
            summary.append(f"\nCase Studies for Provider {service_provider_id}:")
            for case_study in data["case_studies"]:
                summary.append(f"  - {case_study['case_study_title']}")

            # Adding Trmeric Assessment to the summary
            summary.append(f"\nTrmeric Assessment for Provider {service_provider_id}:")
            assessment = data["trmeric_assessment"]
            summary.append(f"  - Expertise Detail: {assessment.get('expertise_detail')}")
            summary.append(f"  - Why TR Recommends: {assessment.get('why_tr_recommends')}")
            summary.append(f"  - Expertise TR Rating: {assessment.get('expertise_tr_rating')}")
            summary.append(f"  - Delivery TR Rating: {assessment.get('delivery_tr_rating')}")
            summary.append(f"  - Satisfaction TR Rating: {assessment.get('satisfaction_tr_rating')}")
            summary.append(f"  - Innovation TR Rating: {assessment.get('innovation_tr_rating')}")
            summary.append(f"  - Communication TR Rating: {assessment.get('communication_tr_rating')}")
            summary.append(f"  - Reliability TR Rating: {assessment.get('reliability_tr_rating')}")



            summary.append(f"------------------------------------------------------------")

            # Join all the pieces of the summary into one string for this provider
            provider_summary = "\n".join(summary)
            provider_summaries.append(provider_summary)

        # Join all provider summaries into a final string
        return "\n\n".join(provider_summaries)


        
        
        
    @staticmethod
    def fetchProjectBrief(project_id):
        query = f"""
            select * from discovery_projectbrief
            where project_id_id = {project_id}
        """
        return db_instance.retrieveSQLQueryOld(query)
      
          
    @staticmethod
    def fetchProviderIdForTenant(tenant_id):
        try:
            query = f"""
                select id from tenant_provider
                where tenant_id = {tenant_id}
            """
            data = db_instance.retrieveSQLQueryOld(query)
            if len(data) > 0:
                return data[0]["id"]
        except Exception as e:
            appLogger.error({"function": "fetchProviderIdForTenant", "event": "DB_CALL_FAILURE", "error": e})
            return 0
            
    @staticmethod
    def fetchServiceProviderIdFromProviderId(provider_id):
        try:
            query = f"""
                SELECT id FROM tenant_serviceprovider
                WHERE provider_id_id = {provider_id}
            """
            data = db_instance.retrieveSQLQueryOld(query)
            if len(data) > 0:
                return data[0]["id"]
            return 0
        except Exception as e:
            appLogger.error({
                "function": "fetchServiceProviderIdFromProviderId",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return 0
       
    @staticmethod
    def fetchServiceCatalog(service_provider_ids):
        try:
            service_provider_ids_str = f"({', '.join(map(str, service_provider_ids))})"
            query = f"""
                SELECT *
                FROM discovery_trmericproviderservicecatalog
                WHERE service_provider_id IN {service_provider_ids_str}
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({
                "function": "fetchServiceCatalog",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []

    @staticmethod
    def fetchCapabilities(service_provider_ids):
        try:
            service_provider_ids_str = f"({', '.join(map(str, service_provider_ids))})"
            query = f"""
                SELECT *
                FROM tenant_providercapabilities
                WHERE service_provider_id IN {service_provider_ids_str}
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({
                "function": "fetchCapabilities",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []

    @staticmethod
    def fetchCaseStudies(service_provider_ids):
        try:
            service_provider_ids_str = f"({', '.join(map(str, service_provider_ids))})"
            query = f"""
                SELECT *
                FROM tenant_providercasestudies
                WHERE service_provider_id IN {service_provider_ids_str}
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({
                "function": "fetchCaseStudies",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []

    @staticmethod
    def fetchTrmericAssessment(service_provider_ids):
        try:
            service_provider_ids_str = f"({', '.join(map(str, service_provider_ids))})"
            query = f"""
                SELECT service_provider_id, expertise_detail, why_tr_recommends,
                    expertise_tr_rating, delivery_tr_rating, satisfaction_tr_rating,
                    innovation_tr_rating, communication_tr_rating, reliability_tr_rating
                FROM tenant_providertrmericassessment
                WHERE service_provider_id IN {service_provider_ids_str}
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({
                "function": "fetchTrmericAssessment",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []
        
    @staticmethod
    def fetchOpportunitiesByTenantId(tenant_id):
        try:
            query = f"""
                SELECT id, title, scope, service_area, tcv, win_probability, status,
                       start_date, end_date, customer_name, description, win_strategy
                FROM opportunity_opportunity
                WHERE to_tenant_id = {tenant_id}
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({
                "function": "fetchOpportunitiesByTenantId",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []

    @staticmethod
    def fetchWinThemesByTenantId(tenant_id):
        try:
            query = f"""
                SELECT w.id, w.text, w.opportunity_id, o.title as opportunity_title, o.win_strategy
                FROM opportunity_wintheme w
                JOIN opportunity_opportunity o ON w.opportunity_id = o.id
                WHERE o.to_tenant_id = {tenant_id}
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            appLogger.error({
                "function": "fetchWinThemesByTenantId",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []
        
    @staticmethod
    def fetchProvidersListing():
        try:
            query = """
                SELECT 
                tp.id as provider_id , tp.types as provider_type, tp.company_name , tps.id as servide_provider_id
                FROM public.tenant_provider as tp
                left join tenant_serviceprovider as tps on tps.provider_id_id = tp.id
                where tp.created_flag = 'N' and tp.types in ('service_provider', 'expert')
                order by tp.id
            """
            res = db_instance.retrieveSQLQueryOld(query)
            res = [{'provider_type': p.get('provider_type'),'company': p.get("company_name")} for p in res]
            # print("res", res)
            return res
        except Exception as e:
            appLogger.error({
                "function": "fetchProvidersListing",
                "event": "DB_CALL_FAILURE",
                "error": str(e)
            })
            return []
            
            
    @staticmethod
    def fetchTenantIdForProvider(provider_id):
        try:
            query = f"""
                select tenant_id from tenant_provider
                where id = {provider_id}
            """
            data = db_instance.retrieveSQLQueryOld(query)
            if len(data) > 0:
                return data[0]["tenant_id"]
        except Exception as e:
            appLogger.error({"function": "fetchTenantIdForProvider", "event": "DB_CALL_FAILURE", "error": e})
            return None
        
    @staticmethod
    def fetch_provider_email(provider_id):
        try:
            query = f"""
                select email from tenant_provider
                where id = {provider_id}
            """
            data = db_instance.retrieveSQLQueryOld(query)
            if len(data) > 0:
                return data[0]["tenant_id"]
        except Exception as e:
            appLogger.error({"function": "fetchTenantIdForProvider", "event": "DB_CALL_FAILURE", "error": e})
            return None
        