from src.trmeric_database.dao import ProjectsDao, RoadmapDao,PortfolioDao
from collections import defaultdict
from datetime import datetime
from .BasePortfolioApiService import BaseAgentService
from src.trmeric_services.agents.apis.prompts.portfolio_api import PortfolioApiPrompts
import traceback
from src.trmeric_database.Redis import RedClient
from typing import List, Dict, Any

NEW_SPEND_TENANTS = [227,237, 776,'776',"227","237","776"]

class PortfolioApiService(BaseAgentService):
    def __init__(self):
        super().__init__()
    
    def addActualSpendToProjects(self, projects, key='project', tenant_id = None):
        """Add actual spend data to each project based on its milestones."""
        for project in projects:
            if tenant_id and tenant_id in NEW_SPEND_TENANTS:
                new_actual = (project.get('capex_actuals') or 0) + (project.get('opex_actuals') or 0)
                new_planned = (project.get('capex_pr_planned') or 0) + (project.get('opex_pr_planned') or 0)

                project['actual_spend'] = float(new_actual)
                project['planned_spend'] = float(new_planned)
                # print("---debug here-------", tenant_id," project_id: ", (project.get('project_id','') or ''), project['actual_spend'], project['planned_spend'])
                # project.pop('capex_actuals',None)
                # project.pop('opex_actuals',None)
                # project.pop('capex_pr_planned',None)
                # project.pop('opex_pr_planned',None)
            
            else:
                if key == 'project':
                    milestones = project.get("milestones", [])  or []
                    project['actual_spend'] = sum(milestone.get("actual_spend", 0) or 0 for milestone in milestones)
                    project['planned_spend'] = sum(milestone.get("planned_spend", 0) or 0 for milestone in milestones)
                if key == 'roadmap':
                    project['actual_spend'] = 0
                    project['planned_spend'] = project['planned_spend']

                                
            project['type'] = key

        return projects
    
    def remove_duplicates(self, projects, key='project_id'):
        seen = set()
        unique_projects = []
        for project in projects:
            identifier = project.get(key)
            if identifier not in seen:
                seen.add(identifier)
                unique_projects.append(project)
        return unique_projects

    def fetchSpendBycategoryNew(self, tenant_id, applicable_projects, portfolio_ids, ongoing=False, start_date=None, end_date=None):
        ongoing_projects = []
        archived_projects = []
        future_projects = []
        import time
        start_time = time.time()

        if ongoing:
            projects = self.fetchProjectsWithAttributesV2(portfolio=portfolio_ids, tenant_id=tenant_id, applicable_projects=applicable_projects, id='fetchSpendBycategory', start_date=None, end_date=None)
            ongoing_projects = self.addActualSpendToProjects(projects['ongoing_projects'], tenant_id=tenant_id)
        else:
            projects = self.fetchProjectsWithAttributesV2(portfolio=portfolio_ids, tenant_id=tenant_id, applicable_projects=applicable_projects, id='fetchSpendBycategory', start_date=None, end_date=None)
            archived_projects = self.addActualSpendToProjects(projects['archived_projects'], tenant_id=tenant_id)
            future_projects = self.addActualSpendToProjects(projects['future_projects'], 'roadmap', tenant_id=tenant_id)
        
       
        if ongoing:
            self.get_all_portfolios_for_projects(ongoing_projects,tenant_id,"ongoing")
        else:
            # self.get_all_portfolios_for_projects(ongoing_projects,tenant_id,"ongoing")
            self.get_all_portfolios_for_projects(archived_projects,tenant_id,"archived")
            self.get_all_portfolios_for_projects(future_projects,tenant_id,"future")
        # print("--deubg projects----",ongoing_projects,"\n",archived_projects," ",future_projects)

        
        # Filter projects based on date range: barStart <= rangeEnd && barEnd >= rangeStart
        def filter_by_date_range(project_list, start_date, end_date):
            if not start_date or not end_date:
                return project_list
            filtered = []
            for project in project_list:
                bar_start = project.get('start_date')
                bar_end = project.get('end_date')
                if bar_start and bar_end:
                    try:
                        # Assuming dates are in a format that can be compared (e.g., strings in 'YYYY-MM-DD' or datetime objects)
                        if bar_start <= end_date and bar_end >= start_date:
                            filtered.append(project)
                    except (TypeError, ValueError):
                        # Skip projects with invalid date formats
                        continue
                else:
                    # Include projects with missing dates (optional, adjust based on requirements)
                    filtered.append(project)
            return filtered
        
        
        # Apply date range filtering
        # ongoing_projects = filter_by_date_range(ongoing_projects, start_date, end_date)
        # archived_projects = filter_by_date_range(archived_projects, start_date, end_date)
        # future_projects = filter_by_date_range(future_projects, start_date, end_date)
        
        
        spend_by_type = defaultdict(lambda: {"planned": 0, "actual": 0})
        unique_projects = set()
        myset = []
        if (ongoing):
            ongoing_projects = filter_by_date_range(ongoing_projects, start_date, end_date)
            myset = [ongoing_projects]
        else:
            archived_projects = filter_by_date_range(archived_projects, start_date, end_date)
            future_projects = filter_by_date_range(future_projects, start_date, end_date)
            myset = [archived_projects, ongoing_projects]
            

        # for category_projects in myset:
        #     for project in category_projects:
        #         project_id = project['project_id']
        #         project_type = project['project_type']
                
        #         if project_id not in unique_projects:
        #             unique_projects.add(project_id)
        #             spend_by_type[project_type]["planned"] += project['planned_spend']
        #             spend_by_type[project_type]["actual"] += project['actual_spend']
        # graph_data = {
        #     "categories": list(spend_by_type.keys()),  # Use project types as labels
        #     "planned": [data["planned"] for data in spend_by_type.values()],
        #     "actual": [data["actual"] for data in spend_by_type.values()],
        # }
        
        ongoing_projects = self.remove_duplicates(ongoing_projects)
        archived_projects = self.remove_duplicates(archived_projects)
        # future_projects = self.remove_duplicates(future_projects)
        # print("fetchSpendBycategory final ", len(future_projects))


        if ongoing:
            table_data_response = {
                "ongoing_projects": ongoing_projects,
                # "archived_projects": [],
                # "future_projects": [],
            }
        else:
            table_data_response = {
                # "ongoing_projects": ongoing_projects,
                "archived_projects": archived_projects,
                "future_projects": future_projects,
            }

        print("--debug fetchSpendBycategoryNew time: ", time.time() - start_time)

        return {
            "table_data":table_data_response,
            # "graph_data": graph_data,
            "elapsed_time": time.time() - start_time
        }

      
      
    def fetchSpendBycategory(self, tenant_id, applicable_projects, portfolio_ids, ongoing=False, start_date=None, end_date=None):
        ongoing_projects = []
        archived_projects = []
        future_projects = []

        projects = self.fetchProjectsWithAttributesV2(portfolio=portfolio_ids, tenant_id=tenant_id, applicable_projects=applicable_projects, id='fetchSpendBycategory', start_date=None, end_date=None)
        # print("debug fetchSpendBycategory 3 ,,, ", len(projects['future_projects']))
        ongoing_projects = self.addActualSpendToProjects(projects['ongoing_projects'], tenant_id=tenant_id)
        archived_projects = self.addActualSpendToProjects(projects['archived_projects'], tenant_id=tenant_id)
        future_projects = self.addActualSpendToProjects(projects['future_projects'], 'roadmap', tenant_id=tenant_id)
        # print("fetchSpendBycategory 1 ", len(future_projects))
        
        self.get_all_portfolios_for_projects(ongoing_projects,tenant_id,"ongoing")
        self.get_all_portfolios_for_projects(archived_projects,tenant_id,"archived")
        self.get_all_portfolios_for_projects(future_projects,tenant_id,"future")
        # print("--deubg projects----",ongoing_projects[0],"\n",archived_projects[0]," ",future_projects[0])
        
        # Filter projects based on date range: barStart <= rangeEnd && barEnd >= rangeStart
        def filter_by_date_range(project_list, start_date, end_date):
            if not start_date or not end_date:
                return project_list
            filtered = []
            for project in project_list:
                bar_start = project.get('start_date')
                bar_end = project.get('end_date')
                if bar_start and bar_end:
                    try:
                        # Assuming dates are in a format that can be compared (e.g., strings in 'YYYY-MM-DD' or datetime objects)
                        if bar_start <= end_date and bar_end >= start_date:
                            filtered.append(project)
                    except (TypeError, ValueError):
                        # Skip projects with invalid date formats
                        continue
                else:
                    # Include projects with missing dates (optional, adjust based on requirements)
                    filtered.append(project)
            return filtered
        
        
        # Apply date range filtering
        ongoing_projects = filter_by_date_range(ongoing_projects, start_date, end_date)
        archived_projects = filter_by_date_range(archived_projects, start_date, end_date)
        future_projects = filter_by_date_range(future_projects, start_date, end_date)
        
        
        spend_by_type = defaultdict(lambda: {"planned": 0, "actual": 0})
        unique_projects = set()
        myset = []
        if (ongoing):
            myset = [ongoing_projects]
        else:
            myset = [archived_projects, ongoing_projects]
            

        for category_projects in myset:
            for project in category_projects:
                project_id = project['project_id']
                project_type = project['project_type']
                
                if project_id not in unique_projects:
                    unique_projects.add(project_id)
                    spend_by_type[project_type]["planned"] += project['planned_spend']
                    spend_by_type[project_type]["actual"] += project['actual_spend']


        graph_data = {
            "categories": list(spend_by_type.keys()),  # Use project types as labels
            "planned": [data["planned"] for data in spend_by_type.values()],
            "actual": [data["actual"] for data in spend_by_type.values()],
        }
        
        ongoing_projects = self.remove_duplicates(ongoing_projects)
        archived_projects = self.remove_duplicates(archived_projects)
        # future_projects = self.remove_duplicates(future_projects)
        # print("fetchSpendBycategory final ", len(future_projects))

        table_data_response = {
            "ongoing_projects": ongoing_projects,
            "archived_projects": archived_projects,
            "future_projects": future_projects,
        }


        return {
            "table_data":table_data_response,
            "graph_data": graph_data 
        }

        
    def fetchSpendVsActual(self, tenant_id, applicable_projects, portfolio_ids, ongoing=False):
        projects = self.fetchProjectsWithAttributesV2(portfolio=portfolio_ids, tenant_id=tenant_id, applicable_projects=applicable_projects, id="fetchSpendVsActual")
        ongoing_projects = self.addActualSpendToProjects(projects['ongoing_projects'], tenant_id=tenant_id)
        archived_projects = self.addActualSpendToProjects(projects['archived_projects'], tenant_id=tenant_id)
        future_projects = self.addActualSpendToProjects(projects['future_projects'], 'roadmap', tenant_id=tenant_id)
        
     
        monthly_spend = defaultdict(lambda: {"planned": 0, "actual": 0})

        unique_projects = set()
        
        myset = []
        if (ongoing):
            myset = [ongoing_projects]
        else:
            myset = [ongoing_projects, archived_projects, future_projects]
            
        for category_projects in myset:
            for project in category_projects:
                project_id = project['project_id']
                if project_id not in unique_projects:
                    unique_projects.add(project_id)

                    milestones = project.get("milestones", [])  or []
                    

                    for milestone in milestones:
                        if not milestone["target_date"]:
                            continue
                        # date = datetime.strptime(milestone["target_date"], "%Y-%m-%d")
                        # year_month = (date.year, date.month)
                        # planned_spend = milestone.get("planned_spend", 0) or 0
                        # actual_spend = milestone.get("actual_spend", 0) or 0

                        # monthly_spend[year_month]["planned"] += planned_spend
                        # monthly_spend[year_month]["actual"] += actual_spend
                        
                        date = datetime.strptime(milestone["target_date"], "%Y-%m-%d")
                        year_month = (date.year, date.month)
                        planned_spend = milestone.get("planned_spend", 0) or 0
                        actual_spend = milestone.get("actual_spend", 0) or 0

                        monthly_spend[year_month]["planned"] += planned_spend
                        monthly_spend[year_month]["actual"] += actual_spend

        # graph_data = {
        #     "labels": [f"{year}-{month:02}" for year, month in monthly_spend.keys()],
        #     "planned": [data["planned"] for data in monthly_spend.values()],
        #     "actual": [data["actual"] for data in monthly_spend.values()],
        # }
        
        # Sort the dates by year and month
        sorted_months = sorted(monthly_spend.keys())

        # Prepare cumulative spend and formatted date labels
        cumulative_planned = 0
        cumulative_actual = 0
        graph_data = {
            "labels": [],
            "planned": [],
            "actual": [],
        }
        
        for year_month in sorted_months:
            planned = monthly_spend[year_month]["planned"]
            actual = monthly_spend[year_month]["actual"]

            cumulative_planned += planned
            cumulative_actual += actual

            # Format the label as "Month Year" (e.g., "March 2024")
            # label = datetime(year=year_month[0], month=year_month[1], day=1).strftime("%B %y")
            label = datetime(year=year_month[0], month=year_month[1], day=1).strftime("%b %y")
        
            
            graph_data["labels"].append(label)
            graph_data["planned"].append(cumulative_planned)
            graph_data["actual"].append(cumulative_actual)

        
        table_data_response = {
            "ongoing_projects": ongoing_projects, 
            "archived_projects": archived_projects, 
            "future_projects": future_projects,  
        }

        return {
            # "table_data":table_data_response,
            "graph_data": graph_data 
        }
        
        
    def fetch_actual_planned_spend_by_portfolio(self, tenant_id, applicable_projects, portfolio_ids, ongoing=False):
        """
        Fetch the actual and planned spend by portfolio.
        This aggregates the spend across all projects within each portfolio.
        """
        # Initialize containers to accumulate the spend data by portfolio
        portfolio_spend_data = defaultdict(lambda: {"planned": 0, "actual": 0, "budget": 0})

        ongoing_projects = []
        archived_projects = []
        future_projects = []
        
        unique_projects = set()
        
        projects = self.fetchProjectsWithAttributesV2(portfolio=portfolio_ids, tenant_id=tenant_id, applicable_projects=applicable_projects, id="fetch_actual_planned_spend_by_portfolio")
        ongoing_projects = self.addActualSpendToProjects(projects['ongoing_projects'], tenant_id=tenant_id)
        archived_projects = self.addActualSpendToProjects(projects['archived_projects'], tenant_id=tenant_id)
        future_projects = self.addActualSpendToProjects(projects['future_projects'], 'roadmap', tenant_id=tenant_id)
        
        all_projects = ongoing_projects + archived_projects + future_projects
        if ongoing:
            all_projects = ongoing_projects
            
            
        # print("debug [[[[[[]]]]]]", portfolio_ids,  all_projects)
            
        for project in all_projects:
            project_id = project.get('project_id') or project.get("roadmap_id")
            # print("project id .. lop ", project_id, project)
            if project_id not in unique_projects:
                unique_projects.add(project_id)
                portfolio_name = project['portfolio_title']
                
                if project.get("type") == "roadmap":
                    portfolio_spend_data[portfolio_name]["planned"] = project.get("planned_spend")
                
                milestones = project.get("milestones", [])  or []
                portfolio_spend_data[portfolio_name]["budget"] += project.get("project_budget") or 0 
                
                for milestone in milestones:
                    planned_spend = milestone.get("planned_spend", 0) or 0
                    actual_spend = milestone.get("actual_spend", 0) or 0

                    portfolio_spend_data[portfolio_name]["planned"] += planned_spend
                    portfolio_spend_data[portfolio_name]["actual"] += actual_spend
                    # portfolio_spend_data[portfolio_name]["budget"] += planned_spend 

        graph_data = {
            "categories": list(portfolio_spend_data.keys()),  # Portfolio IDs as labels
            "planned": [data["planned"] for data in portfolio_spend_data.values()],
            "actual": [data["actual"] for data in portfolio_spend_data.values()],
            "budget": [data["budget"] for data in portfolio_spend_data.values()],
        }


        return {
            "graph_data": graph_data,
            # "extra_data": {
            #     "roadmap_count": len(future_projects),
            #     "project_count": len(ongoing_projects + archived_projects)
            # }
        }

   
    def createSpendByCategoryInsight(self, tenant_id, user_id, portfolio_ids, applicable_projects):
        """
        createSpendByCategoryInsight
        """
        data = self.fetchSpendBycategory(tenant_id, applicable_projects, portfolio_ids)
        graph_data = data["graph_data"]
        
        ## creating insight
        prompt = PortfolioApiPrompts.planned_and_actual_by_category_prompt(graph_data)
        return self.runLLM(user_id=user_id, tenant_id=tenant_id, prompt=prompt, category="planned_and_actual_by_category")
    
    def createPlannedVsActualInsight(self, tenant_id, user_id, portfolio_ids, applicable_projects):
        """
        createSpendByCategoryInsight
        """
        data = self.fetchSpendVsActual(tenant_id,applicable_projects, portfolio_ids, True)
        graph_data = data["graph_data"]
        
        ## creating insight
        prompt = PortfolioApiPrompts.planned_vs_actual_insight_prompt(graph_data)
        return self.runLLM(user_id=user_id, tenant_id=tenant_id, prompt=prompt, category="planned_vs_actual_month_wise")
    
    def createActualAndPlannedByPortfolioInsight(self, tenant_id, user_id, portfolio_ids, applicable_projects):
        """
        createActualAndPlannedByPortfolioInsight
        """
        data = self.fetch_actual_planned_spend_by_portfolio(tenant_id, applicable_projects, portfolio_ids)
        graph_data = data["graph_data"]
        
        ## creating insight
        prompt = PortfolioApiPrompts.planned_and_actual_by_portfolio(graph_data)
        return self.runLLM(user_id=user_id, tenant_id=tenant_id, prompt=prompt, category="planned_and_actual_by_portfolio")
    
    def createOverallSuccessRate(self, tenant_id, user_id, portfolio_ids, applicable_projects):
        """
        createOverallSuccessRate
        """
        data = self.fetch_health_of_projects_last_week_and_current(tenant_id,applicable_projects, portfolio_ids)
        graph_data = data["overall_sankey_data"]
        
        ## creating insight
        prompt = PortfolioApiPrompts.overall_success_rate(graph_data)
        return self.runLLM(user_id=user_id, tenant_id=tenant_id, prompt=prompt, category="overall_performance_compared_from_last_week")
    
    def performance_by_type(self, tenant_id, user_id, portfolio_ids, applicable_projects):
        """
        performance_by_type
        """
        data = self.fetch_health_of_projects_last_week_and_current(tenant_id,applicable_projects, portfolio_ids=portfolio_ids)
        graph_data = data["type_specific_json"]
        
        ## creating insight
        prompt = PortfolioApiPrompts.overall_performance_compared_from_last_week_by_type(graph_data)
        return self.runLLM(user_id=user_id, tenant_id=tenant_id, prompt=prompt, category="overall_performance_compared_from_last_week_by_type")
    
    def status_by_portfolio(self, tenant_id, user_id, portfolio_ids, applicable_projects):
        """
        status_by_portfolio
        """
        data = self.fetch_health_of_projects_last_week_and_current(tenant_id,applicable_projects, portfolio_ids)
        graph_data = data["type_specific_json"]
        
        ## creating insight
        prompt = PortfolioApiPrompts.overall_performance_compared_from_last_week_by_type(graph_data)
        return self.runLLM(user_id=user_id, tenant_id=tenant_id, prompt=prompt, category="overall_performance_compared_from_last_week_by_type")
    
    
    def impact_analysis(self, tenant_id, user_id, portfolio_ids, applicable_projects):
        """
        impact_analysis
        """
        data = self.get_projects_vs_org_strategy(project_ids=applicable_projects, portfolio_ids=portfolio_ids)

        ## creating insight
        prompt = PortfolioApiPrompts.impact_analysis(data)
        return self.runLLM(user_id=user_id, tenant_id=tenant_id, prompt=prompt, category="impact_analysis")
    
    
    
    def get_projects_vs_org_strategy(self, project_ids, portfolio_ids):

        # print("--debug calling get_projects_vs_org_strategy-----------------")
        key_components = [
            f"get_projects_vs_org_strategy",
            f"portfolio:{'_'.join((str(x) for x in portfolio_ids))}",
            f"applicable_projects:{'_'.join(str(x) for x in project_ids)}"
        ]
        key_set = RedClient.create_key(components=key_components)
        project_info_with_org_alignment = RedClient.execute(
            query = lambda: ProjectsDao.fetchProjectOrgAnignment(project_ids=project_ids, portfolio_ids=portfolio_ids),
            key_set=key_set,
            expire = 120 
        )

        # project_info_with_org_alignment = ProjectsDao.fetchProjectOrgAnignment(project_ids=project_ids, portfolio_ids=portfolio_ids)
        link_accumulator = defaultdict(int)
        
        # Check if any project has org_strategy_align
        has_strategies = any(project.get('org_strategy_align') for project in project_info_with_org_alignment)
        
        # Iterate through project data and accumulate links and weights
        for project in project_info_with_org_alignment:
            project_id = project['id']
            project_title = project['title']
            org_strategy_align = project.get('org_strategy_align')
            kpi_names = project.get('kpi_names', [])
            
            if not kpi_names:
                continue
            
            kpis = [s.strip() for s in kpi_names if isinstance(s, str) and s.strip()]
            # strategies = [s.strip() for s in org_strategy_align.split(',') if isinstance(s, str) and s.strip()]
            
            # If no strategies exist, only accumulate project -> KPI links
            if not has_strategies:
                for kpi in kpis:
                    link_accumulator[(project_title, kpi)] += 1
            else:
                # If strategies exist, accumulate both project -> KPI and KPI -> strategy links
                if not org_strategy_align:
                    continue
                strategies = [s.strip() for s in org_strategy_align.split(',') if s.strip()]
                for kpi in kpis:
                    link_accumulator[(project_title, kpi)] += 1
                    for strategy in strategies:
                        link_accumulator[(kpi, strategy)] += 1
        
        # Prepare the data in the desired format
        sankey_data = [["From", "To", "Weight"]]
        
        # Add the links (From -> To with Weight)
        for (source, target), value in link_accumulator.items():
            sankey_data.append([source, target, value])
        
        # print("get_projects_vs_org_strategy", sankey_data)
        return {
            "has_strategies": has_strategies, 
            "sankey_data": sankey_data
        }



    def get_projects_vs_org_strategy_future(self, tenant_id, portfolio_ids):

        key_components = [f"get_projects_vs_org_strategy_future",f"tenant_id:{tenant_id}"]
        key_set = RedClient.create_key(components=key_components)

        org_strategies = RedClient.execute(
            query=lambda: RoadmapDao.fetchOrgStrategyAlignMentOfTenant(tenant_id),
            key_set=key_set,
            expire=300
        )

        key_components1 = [f"get_projects_vs_org_strategy_future",f"tenant_id:{tenant_id}",f"portfolio:{'_'.join((str(x) for x in portfolio_ids))}"]
        key_set = RedClient.create_key(components=key_components1)
        roadmaps = RedClient.execute(
            query = lambda:RoadmapDao.fetchRoadmapForTenant(tenant_id=tenant_id, portfolio_ids=portfolio_ids),
            key_set= key_set,
            expire = 120
        )

        # org_strategies = RoadmapDao.fetchOrgStrategyAlignMentOfTenant(tenant_id)
        # roadmaps = RoadmapDao.fetchRoadmapForTenant(tenant_id=tenant_id, portfolio_ids=portfolio_ids)
        
        link_accumulator = defaultdict(int)
        org_strategy_titles = [s['title'].strip().lower() for s in org_strategies]
        
        # Check if org_strategies exist
        has_strategies = len(org_strategy_titles) > 0
        
        # Iterate through project data and accumulate links and weights
        for project in roadmaps:
            project_id = project['id']
            project_title = project['title']
            org_strategy_align = project.get('org_strategy_align')
            kpi_names = project.get('kpi_names', [])
            
            if not kpi_names:
                continue
            
            kpis = [s.strip() for s in kpi_names if isinstance(s, str) and s.strip()]
            
            # If no strategies exist, only accumulate roadmap -> KPI links
            if not has_strategies:
                for kpi in kpis:
                    link_accumulator[(project_title, kpi)] += 1
            else:
                # If strategies exist, accumulate both roadmap -> KPI and KPI -> strategy links
                if not org_strategy_align:
                    continue
                strategies = []
                for ost in org_strategy_titles:
                    if ost.strip().lower() in org_strategy_align.strip().lower():
                        strategies.append(ost)
                
                for kpi in kpis:
                    link_accumulator[(project_title, kpi)] += 1
                    for strategy in strategies:
                        link_accumulator[(kpi, strategy)] += 1
        
        sankey_data = [["From", "To", "Weight"]]
        for (source, target), value in link_accumulator.items():
            sankey_data.append([source, target, value])
        
        return {
            "has_strategies": has_strategies, 
            "sankey_data": sankey_data
        }






    def get_health_of_projects_status_by_portfolio(self, tenant_id, applicable_projects, portfolio_ids):
        
        ongoing_projects = self.fetchOngonigProjectsWithAttributesV2(portfolio=portfolio_ids, tenant_id=tenant_id, applicable_projects=applicable_projects)
        
        projects_by_portfolio = {}
        for project in ongoing_projects:
            portfolio_id = project.get("portfolio_id", "No Portfolio")
            portfolio_name = project.get("portfolio_title", "Unknown Portfolio")

            if portfolio_id not in projects_by_portfolio:
                projects_by_portfolio[portfolio_id] = {
                    "portfolio_name": portfolio_name,
                    "projects": []
                }
            projects_by_portfolio[portfolio_id]["projects"].append(project)

        health_status_by_portfolio = []
        for portfolio_id, data in projects_by_portfolio.items():
            health_stats = self.calculate_health_status(data["projects"])
            health_status_by_portfolio.append({
                "portfolio_id": portfolio_id,
                "portfolio_name": data["portfolio_name"],
                "projects_health_stats": health_stats
            })

        return health_status_by_portfolio



    def calculate_health_status(self, ongoing_projects):
        """
        Calculate health status data for ongoing projects by portfolio.
        Health status includes: compromised, on_track, at_risk, no_update.
        
        Args:
            ongoing_projects (list[dict]): List of ongoing projects with spend_status, scope_status, and delivery_status.

        Returns:
            dict: Health status data with counts for each category.
        """
        health_status_counts = {
            "compromised": 0,
            "on_track": 0,
            "at_risk": 0,
            "no_update": 0
        }

        for project in ongoing_projects:
            spend_status = project.get("spend_status")
            scope_status = project.get("scope_status")
            delivery_status = project.get("delivery_status")
            
            # if spend_status == "on_track" and scope_status == "on_track" and delivery_status == "on_track":
            #     health_status_counts["on_track"] += 1
            # el
            # if spend_status is None and scope_status is None and delivery_status is None:
            #     health_status_counts["no_update"] += 1
            if spend_status == "compromised" or scope_status == "compromised" or delivery_status == "compromised":
                health_status_counts["compromised"] += 1
            elif spend_status == "at_risk" or scope_status == "at_risk" or delivery_status == "at_risk":
                health_status_counts["at_risk"] += 1
            elif spend_status == "on_track" or scope_status == "on_track" or delivery_status == "on_track":
                health_status_counts["on_track"] += 1
            else:
                health_status_counts["no_update"] += 1
            

        return health_status_counts


    def fetch_health_of_projects_last_week_and_current(self, tenant_id, applicable_projects, portfolio_ids):
        ongoing_projects = self.fetchOngonigProjectsWithAttributesV2(portfolio=portfolio_ids, tenant_id=tenant_id, applicable_projects=applicable_projects)
        # last_week_status_of_projectrs = ProjectsDao.fetchStatusOfProjectsLastWeek(project_ids=applicable_projects, tenant_id=tenant_id)

        # key_components = [f"fetch_health_of_projects_last_week_and_current",f"tenant_id:{tenant_id}",f"portfolio_ids:{'_'.join(portfolio_ids)}"]
        key_components = [
            "fetch_health_of_projects_last_week_and_current",
            f"tenant_id:{tenant_id}",
            f"portfolio_ids:{'_'.join(str(pid) for pid in portfolio_ids)}"  # convert to string
        ]

        key_set = RedClient.create_key(components=key_components)

        last_week_status_of_projectrs = RedClient.execute(
            query = lambda: ProjectsDao.fetchStatusOfProjectsLastWeek(project_ids=applicable_projects, tenant_id=tenant_id),
            key_set = key_set
        )

        print("debug ooo ", len(ongoing_projects), len(last_week_status_of_projectrs))
        last_week_status_map = {}
        for status_entry in last_week_status_of_projectrs:
            project_id = status_entry["project_id"]
            if project_id not in last_week_status_map:
                last_week_status_map[project_id] = {}
            last_week_status_map[project_id][status_entry["type"]] = status_entry["value"]
            
        # print("debug ooo1 ", len(ongoing_projects), (last_week_status_map))
            
        def normalize_status(status):
            return status if status is not None else "grey_status"
        
        def combiner_status(current_scope, current_schedule, current_spend):
            # if (current_scope == "on_track" and current_schedule == "on_track" and current_spend == "on_track"):
            #     combined_current_status = 'on_track'
            # el
            if (current_scope == "compromised" or current_schedule == "compromised" or current_spend == "compromised"):
                combined_current_status = 'compromised'
            elif (current_scope == "at_risk" or current_schedule == "at_risk" or current_spend == "at_risk"):
                combined_current_status = 'at_risk'
            elif (current_scope == "on_track" or current_schedule == "on_track" or current_spend == "on_track"):
                combined_current_status = 'on_track'
            else:
                combined_current_status = 'grey_status'
            return combined_current_status
        
        def combine_status(project_health):
            combined_current_status = None
            current_spend = normalize_status(project_health["curr_spend_status"])
            current_schedule = normalize_status(project_health["curr_schedule_status"])
            current_scope = normalize_status(project_health["curr_scope_status"])
            
            previous_spend = normalize_status(project_health["prev_spend_status"])
            previous_schedule = normalize_status(project_health["prev_scope_status"])
            previous_scope = normalize_status(project_health["prev_scope_status"])
            
            project_health["combined_current_status"] = combiner_status(
                current_scope, 
                current_schedule, 
                current_spend
            )
            project_health["combined_previous_status"] = combiner_status(
                current_scope=previous_scope, 
                current_schedule=previous_schedule, 
                current_spend=previous_spend
            )
            return project_health
            

        health_status_json = []
        for project in ongoing_projects:
            
            project_id = project["project_id"]
            
            last_week_status = last_week_status_map.get(project_id, {})

            project_health = {
                "id": project_id,
                "prev_spend_status": last_week_status.get("spend_status", None),  # Last week's status
                "prev_scope_status": last_week_status.get("scope_status", None),
                "prev_schedule_status": last_week_status.get("delivery_status", None),
                
                "curr_spend_status": project.get("spend_status", None),
                "curr_scope_status": project.get("scope_status", None),
                "curr_schedule_status": project.get("delivery_status", None),
            }
            project_health = combine_status(project_health)
            health_status_json.append(project_health)
            
        transitions = defaultdict(set)
        
        for project in health_status_json:
            # print("deubg obngoing projects ", project )
            prev_status = project["combined_previous_status"]
            curr_status = project["combined_current_status"]
            transitions[(prev_status, curr_status)].add(project["id"])
            
        # print("debug again --- ", transitions)
            
        nodes_set = set()
        links = []

        for (source, target), project_ids in transitions.items():
            nodes_set.add(source)
            nodes_set.add(target)
            links.append({'source': source, 'target': target, 'value': len(project_ids)})


        nodes = [{'id': node, 'label': node.replace('_', ' ').capitalize()} for node in nodes_set]
        sankey_data = {
            'nodes': nodes,
            'links': links
        }
        
        # New structure to track multiple statuses like on_track, at_risk, compromised, etc.
        status_type_map = {
            'spend': defaultdict(int),
            'scope': defaultdict(int),
            'schedule': defaultdict(int),
        }
        
        old_map = {
            'spend': defaultdict(int),
            'scope': defaultdict(int),
            'schedule': defaultdict(int),
        }

        # Define status categories and mapping to respective project counts
        status_categories = ["on_track", "at_risk", "compromised", "no_update"]

        def normalize_status(status):
            return status if status is not None else "no_update"

        def categorize_status(status):
            if status == "on_track":
                return "on_track"
            elif status == "at_risk":
                return "at_risk"
            elif status == "compromised":
                return "compromised"
            else:
                return "no_update"
            
        check_arr = []
        for category in ['spend', 'scope', 'schedule']:
            for project in health_status_json:   
                unique_key = f"{project['id']}_{category}"    
                if unique_key in check_arr:
                    # print(f"Duplicate found: {unique_key}")
                    continue         
                prev_status = normalize_status(project[f'prev_{category}_status'])
                curr_status = normalize_status(project[f'curr_{category}_status'])

                prev_status = categorize_status(prev_status)
                curr_status = categorize_status(curr_status)

                status_type_map[category][curr_status] += 1
                old_map[category][prev_status] += 1
                check_arr.append(unique_key)
                
                # print("debug -- test -- ", project["id"],  category, curr_status, prev_status)

        # Ensure all status categories are present in the maps, even if they have 0 count
        for category in ['spend', 'scope', 'schedule']:
            for status in status_categories:
                if status not in status_type_map[category]:
                    status_type_map[category][status] = 0
                if status not in old_map[category]:
                    old_map[category][status] = 0

        # Prepare the final data structure for the stacked bar chart
        final_data = []
        
        # print("debug -- ", applicable_projects)
        # print("debug -- status_type_map ", status_type_map )
        # print("debug -- status_type_map ", old_map )

        return {
            "overall_sankey_data": sankey_data, 
            "type_specific_json": {
                "current_status": status_type_map,
                "old_status": old_map
            }
        }
        
        
    def fetchOngoingProjectDetails(self, tenant_id, applicable_projects, portfolio_ids):
        ongoing_projects = []
        projects = self.fetchOngonigProjectsWithAttributesV2(portfolio=portfolio_ids, tenant_id=tenant_id, applicable_projects=applicable_projects)
        ongoing_projects = self.addActualSpendToProjects(projects, tenant_id=tenant_id)
        spend_by_type = defaultdict(lambda: {"planned": 0, "actual": 0})
        unique_projects = set()
        ongoing_projects = self.remove_duplicates(ongoing_projects)
        return {
            "ongoing_projects_table_data": ongoing_projects
        }
        
    def get_all_portfolios_for_projects(self,projects,tenant_id,category = "ongoing"):
        
        # print("--debug get_all_portfolios_for_projects ",category, len(projects), tenant_id)
        if category == "future": #roadmaps
            for project in projects:
                roadmap_id = project.get("roadmap_id")
                portfolios = ""
                
                if roadmap_id:
                    # res = PortfolioDao.fetchAllPortfoliosForRoadmap(roadmap_id=roadmap_id, tenant_id=tenant_id)
                    key_components1 = [f"get_all_portfolios_for_projects",f"tenant_id:{tenant_id}",f"roadmap_id:{roadmap_id}"]
                    key_set = RedClient.create_key(components=key_components1)
                    res = RedClient.execute(
                        query= lambda: PortfolioDao.fetchAllPortfoliosForRoadmap(roadmap_id=roadmap_id, tenant_id=tenant_id),
                        key_set=key_set
                    )

                    if res is not None and len(res)>0:
                        all_portfolios = ", ".join([portfolio["portfolio_title"] for portfolio in res])
                        # print(f"\n\n--deubg all_portfiolis------", all_portfolios)
                    project["all_portfolios"] = all_portfolios or portfolios
        else:
            for project in projects:
                project_id = project.get("project_id")
                portfolios = ""
                
                if project_id:
                    #res = PortfolioDao.fetchAllPortfoliosForProject(project_id=project_id, tenant_id=tenant_id)
                    key_components = [f"get_all_portfolios_for_projects",f"tenant_id:{tenant_id}",f"project_id:{project_id}"]
                    key_set = RedClient.create_key(components=key_components)
                    res = RedClient.execute(
                        query =lambda:PortfolioDao.fetchAllPortfoliosForProject(project_id=project_id, tenant_id=tenant_id),
                        key_set=key_set
                    )

                    if res is not None and len(res)>0:
                        all_portfolios = ", ".join([portfolio["portfolio_title"] for portfolio in res])
                        # print("\n\n--deubg all_portfiolis------", all_portfolios)
                    project["all_portfolios"] = all_portfolios or portfolios
        return

        
        
    def get_subportfolios_mapping(self, portfolios):
       
        if not portfolios:
            return {}
        
        # Build a map of parent_id to list of child portfolio IDs
        children_map = defaultdict(list)
        for p in portfolios:
            parent_id = p.get('parent_id') or None
            if parent_id is not None:
                if parent_id not in children_map:
                    children_map[parent_id] = []
                children_map[parent_id].append(p['id'])
        
        return children_map
    
    
    
    def build_hierarchy(self,node_id,children_map, id_to_node, level=1, params=[]):
        """Recursively build the hierarchy starting from node_id."""
        
        if node_id not in id_to_node:
            return None
        
        node = id_to_node[node_id].copy()
        node['level'] = level
        node['children'] = []
        
        if params:
            for param in params:
                node[param.get("key") or "Unknown"] = param.get("value") or None
        
        child_ids = children_map.get(node_id, [])
        # Recursively build children
        for child_id in child_ids:
            child = self.build_hierarchy(child_id,children_map,id_to_node, level + 1,params=params)
            if child:
                node['children'].append(child)
        
        return node
    
    
    def get_portfolio_context_of_user(self, tenant_id, user_id):
        portfolios = PortfolioDao.fetchApplicablePortfolios(user_id=user_id, tenant_id=tenant_id)
        import json
        # with open("portfolio3.json","w") as f:
        #     json.dump(portfolios,f, indent=4)
        children_map = self.get_subportfolios_mapping(portfolios)
        # print("debug get_portfolio_context_of_user children_map ", children_map)
        id_to_node = {p['id']: p.copy() for p in portfolios}
        child_ids = {p['id'] for p in portfolios if p['parent_id'] in id_to_node}
        roots = [node for node_id, node in id_to_node.items() if node_id not in child_ids]
        tree = [
            self.build_hierarchy(
                node_id=root['id'],
                children_map = children_map,
                id_to_node = id_to_node,
                level = 1,
                params = [{"key":"expanded","value":True},{"key":"selected","value":True}]
            )
            for root in roots
        ]
        def filter_portfolio_tree(tree):
            """Keep only id, title, and children in the hierarchy."""
            filtered = []
            for node in tree:
                filtered_node = {
                    "portfolio_id": node["id"],
                    "portfolio_title": node["title"],
                    "project_count": node.get("project_count"),
                    "roadmap_count": node.get("roadmap_count"),
                    "children": filter_portfolio_tree(node.get("children", []))
                }
                filtered.append(filtered_node)
            return filtered
        
        filtered_tree = filter_portfolio_tree(tree)
        
        # with open("portfolio2.json","w") as f:
        #     json.dump(filtered_tree,f, indent=4)
            
        
        return filtered_tree
    