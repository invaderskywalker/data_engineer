

##### src/utils/knowledge/KnwoeldgeAgent.py
from src.database.Database import db_instance

class KnowledgeAgent:
    def __init__(self):
        pass
    
    def fetchKnowledgeForProjectCategories(self, categories=[], outcome=[]):
        outcome_filter = "and outcome in ('success', 'failure')"
        # if len(outcome) > 0:
        #     outcome_str = f"({', '.join(map(str, outcome))})"
        #     outcome_filter = f"and outcome in {outcome_str}"
        
        categories_str = ", ".join(f"'{str(c)}'" for c in categories) 
        categories_str = f"({categories_str})"
        query = f"""
            select * from tango_knowledge
            where project_type in {categories_str}
            {outcome_filter}
        """
        data = db_instance.retrieveSQLQueryOld(query)
        if (len(data) > 0):
            return data
        return []
    
    def fetchKnowledgeForProjects(self, project_ids, outcome=[]):
        if len(project_ids) >0:
            project_ids_str = f"({', '.join(map(str, project_ids))})"
            query = f"""
                select DISTINCT(project_type) as project_type from tango_projectanalysis
                where project_id in {project_ids_str}
            """
            try:
                data = db_instance.retrieveSQLQueryOld(query)
                if (len(data) > 0):
                    categories =  [d["project_type"] for d in data]
                    return self.fetchKnowledgeForProjectCategories(categories=categories, outcome=outcome)
            except Exception as e:
                return []
        return []
    
    def fetchProjectCategoriesForProjects(self,project_ids):
        if len(project_ids) >0:
            project_ids_str = f"({', '.join(map(str, project_ids))})"
            query = f"""
                select  wp.title as project_title, tpa.project_type  from tango_projectanalysis as tpa
                left join workflow_project as wp on wp.id = tpa.project_id
                where project_id in {project_ids_str}
            """
            try:
                return db_instance.retrieveSQLQueryOld(query)
            except Exception as e:
                return []
        return []
    
        