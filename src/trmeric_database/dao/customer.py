from src.trmeric_database.Database import db_instance


class CustomerDao:
    @staticmethod
    def FetchCustomerPersona(tenant_id):
        query = f"""
        SELECT persona,org_info FROM tenant_customer where tenant_id = {tenant_id}
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def FetchCustomerOrgDetailInfo(tenant_id):
        query = f"""
        SELECT org_info FROM tenant_customer where tenant_id = {tenant_id}
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def getCustomerDataForProvider(provider_id):
        query = f"""
        select customer_name, website from provider_externalcustomer where id={provider_id}
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def getCustomerProfileDetails(tenant_id):
        query = f"""
            SELECT 
                id,
                created_at,
                updated_at,
                organization_details ->> 'name' AS organization_name,
                organization_details ->> 'industry' AS industry,
                key_contacts,
                demographics AS region,
                solutions_offerings,
                business_goals_and_challenges,
                technological_landscape  AS technological_landscape
            FROM 
                customer_profile
            WHERE 
                tenant_id = {tenant_id}
            ORDER BY 
                updated_at DESC
        """
        return db_instance.retrieveSQLQueryOld(query)

