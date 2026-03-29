from src.trmeric_database.Database import db_instance


class KnowledgeDao:
    @staticmethod
    def FetchProjectPortfolioKnowledge(tenant_id, portfolio_id):
        if portfolio_id is None:
            query = f"""
                SELECT knowledge_summary FROM tango_projectsknowledge
                WHERE tenant_id = {tenant_id} 
                AND portfolio_id IS NULL
            """
        else:
            query = f"""
                SELECT knowledge_summary FROM tango_projectsknowledge
                WHERE tenant_id = {tenant_id} 
                AND portfolio_id = {portfolio_id}
            """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def FetchAllPortfolioKnowledgeOfTenant(tenant_id):
        query = f"""
            SELECT knowledge_summary FROM tango_projectsknowledge
                where tenant_id = {tenant_id} 
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    
    @staticmethod
    def fetchKnowledgeV1DataForProjectTypeAndOutcome(project_type, outcome):
        query = f"""
            SELECT * from tango_knowledge
            where project_type = '{project_type}' and outcome = '{outcome}'
        """
        result = db_instance.retrieveSQLQueryOld(query)
        if len(result) > 0:
            return result[0]
        else:
            return None
