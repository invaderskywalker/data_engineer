"""
SQL Queries for Data Fetching

Provides SQL queries for fetching project, roadmap, and related data from PostgreSQL.
"""

from typing import List, Dict, Set, Any
from collections import defaultdict

STATE_MAP = {
    0:  "Intake",
    1:  "Approved",
    2:  "Execution",
    3:  "Archived",
    4:  "Elaboration",
    5:  "Solutioning",
    6:  "Prioritize",
    99: "Hold",
    100:"Rejected",
    999:"Cancelled",
    200:"Draft"
}

APPROVAL_MAP = {
    1: "pending",
    2: "approved",
    3: "rejected"
}

class ProjectQueries:
    """SQL queries for project-related data."""
    
    @staticmethod
    def fetch_all_project_ids(cursor, tenant_id: int, limit: int = None) -> Set[int]:
        """
        Fetch all project IDs for a tenant.
        
        Args:
            cursor: Database cursor
            tenant_id: Tenant identifier
            limit: Optional limit on number of projects
            
        Returns:
            Set of project IDs
        """
        limit_clause = f"LIMIT {limit}" if limit else ""
        query = f"""
            SELECT id 
            FROM workflow_project 
            WHERE tenant_id_id = {tenant_id}
                AND archived_on IS NULL
                AND parent_id IS NOT NULL
            ORDER BY created_on DESC
            {limit_clause}
        """
        cursor.execute(query)
        return {row[0] for row in cursor.fetchall()}
    
    @staticmethod
    def fetch_projects(cursor, tenant_id: int, project_ids: Set[int]) -> List[Dict]:
        """
        Fetch project data for given tenant and project IDs.
        
        Args:
            cursor: Database cursor
            tenant_id: Tenant identifier
            project_ids: Set of project IDs to fetch
            
        Returns:
            List of project dictionaries
        """
        project_ids_str = f"({','.join(map(str, project_ids))})" if project_ids else "(0)"
        query = f"""
            SELECT 
                wp.id AS project_id,
                wp.title AS name,
                wp.description AS description,
                wp.start_date AS start_date,
                wp.end_date AS end_date,
                wp.project_type AS project_type,
                wp.sdlc_method AS sdlc_method,
                wp.state AS project_state,
                wp.project_category AS project_category,
                wp.delivery_status AS delivery_status,
                wp.scope_status AS scope_status,
                wp.spend_status AS spend_status,
                wp.objectives AS project_objectives,
                wp.org_strategy_align AS org_strategy,
                wp.technology_stack AS technology_stack,
                wp.project_location as project_location,
                wp.total_external_spend
            FROM workflow_project AS wp
            WHERE wp.tenant_id_id = {tenant_id}
                AND wp.id IN {project_ids_str}
                AND wp.archived_on IS NULL
                AND wp.parent_id IS NOT NULL
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            print(f"Fetched {len(data)} project records")
            return [dict(zip(columns, row)) for row in data]
        except Exception as e:
            print(f"Error fetching project data: {e}")
            return []
    
    @staticmethod
    def fetch_portfolios(cursor, project_id: int) -> List[Dict]:
        """Fetch portfolio data for a specific project."""
        query = f"""
            SELECT 
                pp.id AS portfolio_id,
                pp.title AS name
            FROM workflow_projectportfolio AS wpport
            LEFT JOIN projects_portfolio AS pp ON wpport.portfolio_id = pp.id
            WHERE wpport.project_id = {project_id}
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in data]
        except Exception as e:
            print(f"Error fetching portfolio data for project {project_id}: {e}")
            return []
    
    @staticmethod
    def fetch_milestones(cursor, project_id: int) -> List[Dict]:
        """Fetch milestone data for a specific project."""
        query = f"""
            SELECT 
                wpm.id AS milestone_id,
                wpm.name AS milestone_name,
                wpm.planned_spend AS planned_spend_amount,
                wpm.actual_spend AS actual_spend_amount,
                wpm.target_date,
                wpm.actual_date,
                wpm.comments,
                CASE 
                    WHEN wpm.status_value = 1 THEN 'not_started'
                    WHEN wpm.status_value = 2 THEN 'in_progress'
                    WHEN wpm.status_value = 3 THEN 'completed'
                END AS status,
                CASE
                    WHEN wpm.type = 1 THEN 'scope_milestone'
                    WHEN wpm.type = 2 THEN 'schedule_milestone'
                    WHEN wpm.type = 3 THEN 'spend_milestone'
                END AS milestone_type,
                CASE 
                    WHEN wpm.actual_date IS NOT NULL AND wpm.target_date IS NOT NULL 
                    THEN EXTRACT(DAY FROM (wpm.actual_date::timestamp - wpm.target_date::timestamp))
                    ELSE NULL
                END AS duration_days
            FROM workflow_projectmilestone AS wpm
            WHERE wpm.project_id = {project_id}
                AND wpm.type IN (1, 2, 3)
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in data]
        except Exception as e:
            print(f"Error fetching milestone data for project {project_id}: {e}")
            return []
    
    @staticmethod
    def fetch_statuses(cursor, project_id: int) -> List[Dict]:
        """Fetch status data for a specific project."""
        query = f"""
            SELECT 
                wps.id AS status_id,
                CASE 
                    WHEN wps.type = 1 THEN 'Scope'
                    WHEN wps.type = 2 THEN 'Schedule'
                    WHEN wps.type = 3 THEN 'Spend'
                    ELSE 'Unknown Type'
                END AS status_type,
                CASE 
                    WHEN wps.value = 1 THEN 'On Track'
                    WHEN wps.value = 2 THEN 'At Risk'
                    WHEN wps.value = 3 THEN 'Compromised'
                    ELSE 'Unknown Value'
                END AS name,
                wps.comments AS status_comments,
                wps.created_date
            FROM workflow_projectstatus AS wps
            WHERE wps.project_id = {project_id}
            ORDER BY wps.created_date ASC
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in data]
        except Exception as e:
            print(f"Error fetching status data for project {project_id}: {e}")
            return []
    
    @staticmethod
    def fetch_key_results(cursor, project_id: int) -> List[Dict]:
        """Fetch key results (KPIs) for a specific project."""
        query = f"""
            SELECT 
                wpk.id AS kpi_id,
                wpk.name AS kpi_name,
                wpk.baseline_value
            FROM workflow_projectkpi AS wpk
            WHERE wpk.project_id = {project_id}
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in data]
        except Exception as e:
            print(f"Error fetching key result data for project {project_id}: {e}")
            return []
    
    @staticmethod
    def fetch_team(cursor, project_id: int) -> List[Dict]:
        """Fetch team members for a specific project."""
        query = f"""
            SELECT
                pts.is_external,
                pts.location,
                pts.team_members,
                CASE 
                    WHEN pts.spend_type = 1 THEN 'Internal'
                    WHEN pts.spend_type = 2 THEN 'External'
                    ELSE 'Unknown'
                END AS spend_type,
                pts.average_spend,
                pts.member_role as role,
                pts.member_utilization
            FROM 
                public.workflow_projectteamsplit pts
            WHERE 
                pts.project_id = {project_id}
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in data]
        except Exception as e:
            print(f"Error fetching team data for project {project_id}: {e}")
            return []
    
    @staticmethod
    def fetch_risks(cursor, project_ids: Set[int]) -> Dict[int, List[Dict]]:
        """
        Fetch risks for multiple projects.
        
        Returns:
            Dictionary mapping project_id to list of risks
        """
        project_ids_str = f"({', '.join(map(str, project_ids))})"
        risk_status_mapping = {
            'Active': 1,
            'Resolved': 2,
            'Monitoring': 3,
            'Escalated': 4,
            'Mitigated': 5,
            'Closed': 6,
        }
        
        query = f"""
            SELECT 
                wpr.project_id,
                wpr.id,
                wpr.description,
                wpr.impact,
                wpr.mitigation,
                wpr.due_date,
                CASE wpr.status_value
                    WHEN {risk_status_mapping['Active']} THEN 'Active'
                    WHEN {risk_status_mapping['Resolved']} THEN 'Resolved'
                    WHEN {risk_status_mapping['Monitoring']} THEN 'Monitoring'
                    WHEN {risk_status_mapping['Escalated']} THEN 'Escalated'
                    WHEN {risk_status_mapping['Mitigated']} THEN 'Mitigated'
                    WHEN {risk_status_mapping['Closed']} THEN 'Closed'
                    ELSE 'Unknown'
                END AS status  
            FROM workflow_projectrisk AS wpr
            WHERE wpr.project_id IN {project_ids_str}
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            # Group by project_id
            risks_by_project = defaultdict(list)
            for row in data:
                row_dict = dict(zip(columns, row))
                project_id = row_dict.pop('project_id')
                risks_by_project[project_id].append(row_dict)
            
            print(f"Fetched risks for {len(risks_by_project)} projects")
            return dict(risks_by_project)
        except Exception as e:
            print(f"Error fetching risks: {e}")
            return {}
    
    @staticmethod
    def fetch_technologies(project: Dict) -> List[Dict]:
        """Extract technologies from project's technology_stack field."""
        technology_stack = project.get("technology_stack", "")
        if not technology_stack or technology_stack == "":
            return []
        technologies = [tech.strip() for tech in technology_stack.split(",") if tech.strip()]
        return [{"tech_id": tech.lower(), "name": tech} for tech in technologies]
    
    @staticmethod
    def fetch_project_types(project: Dict) -> List[Dict]:
        """Extract project type from project data."""
        project_type = project.get("project_type", "")
        if not project_type or project_type == "":
            return []
        return [{"project_type_id": project_type.lower(), "name": project_type}]
    
    @staticmethod
    def fetch_sdlc_methods(project: Dict) -> List[Dict]:
        """Extract SDLC method from project data."""
        sdlc_method = project.get("sdlc_method", "")
        if not sdlc_method or sdlc_method == "":
            return []
        return [{"sdlc_method_id": sdlc_method.lower(), "name": sdlc_method}]
    
    @staticmethod
    def fetch_project_categories(project: Dict) -> List[Dict]:
        """Extract project categories from project data."""
        project_category = project.get("project_category", "")
        if not project_category or project_category == "":
            return []
        categories = [cat.strip() for cat in project_category.split(",") if cat.strip()]
        return [{"project_category_id": cat.lower(), "name": cat} for cat in categories]
    
    @staticmethod
    def fetch_project_locations(project: Dict) -> List[Dict]:
        """Extract project locations from project data."""
        project_location = project.get("project_location", "")
        if not project_location or project_location == "":
            return []
        locations = [loc.strip() for loc in project_location.split(",") if loc.strip()]
        return [{"project_location_id": loc.lower(), "name": loc} for loc in locations]


class RoadmapQueries:
    """SQL queries for roadmap-related data."""
    
    @staticmethod
    def fetch_all_roadmap_ids(cursor, tenant_id: int, limit: int = None) -> Set[int]:
        """
        Fetch all roadmap IDs for a tenant.
        
        Args:
            cursor: Database cursor
            tenant_id: Tenant identifier
            limit: Optional limit on number of roadmaps
            
        Returns:
            Set of roadmap IDs
        """
        limit_clause = f"LIMIT {limit}" if limit else ""
        query = f"""
            SELECT id 
            FROM roadmap_roadmap 
            WHERE tenant_id = {tenant_id}
                AND archived_on IS NULL
            ORDER BY created_on DESC
            {limit_clause}
        """
        cursor.execute(query)
        return {row[0] for row in cursor.fetchall()}
    
    @staticmethod
    def fetch_roadmaps(cursor, tenant_id: int, roadmap_ids: Set[int]) -> List[Dict]:
        """
        Fetch roadmap data for given tenant and roadmap IDs.
        
        Args:
            cursor: Database cursor
            tenant_id: Tenant identifier
            roadmap_ids: Set of roadmap IDs to fetch
            
        Returns:
            List of roadmap dictionaries
        """
        roadmap_ids_str = f"({','.join(map(str, roadmap_ids))})" if roadmap_ids else "(0)"
        query = f"""
            SELECT 
                rr.id AS roadmap_id,
                rr.title AS name,
                rr.description AS description,
                rr.objectives AS roadmap_objectives,
                rr.solution AS solution,
                rr.start_date AS start_date,
                rr.end_date AS end_date,
                rr.budget,
                rr.category,
                rr.org_strategy_align,
                rr.priority,
                rr.current_state,
                CASE 
                    WHEN rr.type = 1 THEN 'Program'
                    WHEN rr.type = 2 THEN 'Project'
                    WHEN rr.type = 3 THEN 'Enhancement'
                    WHEN rr.type = 4 THEN 'New Development'
                    ELSE 'Unknown'
                END AS roadmap_type
            FROM roadmap_roadmap AS rr
            WHERE rr.tenant_id = {tenant_id}
                AND rr.id IN {roadmap_ids_str}
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            print(f"Fetched {len(data)} roadmap records")
            return [dict(zip(columns, row)) for row in data]
        except Exception as e:
            print(f"Error fetching roadmap data: {e}")
            return []
    
    @staticmethod
    def fetch_portfolios(cursor, roadmap_ids: Set[int]) -> Dict[int, List[Dict]]:
        """Fetch portfolio data for multiple roadmaps."""
        roadmap_ids_str = f"({', '.join(map(str, roadmap_ids))})"
        query = f"""
            SELECT 
                rrp.roadmap_id,
                pp.id AS portfolio_id,
                pp.title AS name
            FROM roadmap_roadmapportfolio AS rrp
            LEFT JOIN projects_portfolio AS pp ON rrp.portfolio_id = pp.id
            WHERE rrp.roadmap_id IN {roadmap_ids_str}
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            portfolios_by_roadmap = defaultdict(list)
            for row in data:
                row_dict = dict(zip(columns, row))
                roadmap_id = row_dict.pop('roadmap_id')
                portfolios_by_roadmap[roadmap_id].append(row_dict)
            
            return dict(portfolios_by_roadmap)
        except Exception as e:
            print(f"Error fetching portfolio data: {e}")
            return {}
    
    @staticmethod
    def fetch_constraints(cursor, roadmap_ids: Set[int]) -> Dict[int, List[Dict]]:
        """Fetch constraint data for multiple roadmaps."""
        roadmap_ids_str = f"({', '.join(map(str, roadmap_ids))})"
        query = f"""
            SELECT 
                rrc.roadmap_id,
                rrc.id AS constraint_id,
                rrc.name AS constraint_name,
                CASE 
                    WHEN rrc.type = 1 THEN 'Cost'
                    WHEN rrc.type = 2 THEN 'Resource'
                    WHEN rrc.type = 3 THEN 'Risk'
                    WHEN rrc.type = 4 THEN 'Scope'
                    WHEN rrc.type = 5 THEN 'Quality'
                    WHEN rrc.type = 6 THEN 'Time'
                    ELSE 'Unknown'
                END AS constraint_type
            FROM roadmap_roadmapconstraints AS rrc
            WHERE rrc.roadmap_id IN {roadmap_ids_str}
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            constraints_by_roadmap = defaultdict(list)
            for row in data:
                row_dict = dict(zip(columns, row))
                roadmap_id = row_dict.pop('roadmap_id')
                constraints_by_roadmap[roadmap_id].append(row_dict)
            
            return dict(constraints_by_roadmap)
        except Exception as e:
            print(f"Error fetching constraint data: {e}")
            return {}
    
    @staticmethod
    def fetch_key_results(cursor, roadmap_ids: Set[int]) -> Dict[int, List[Dict]]:
        """Fetch key results (KPIs) for multiple roadmaps."""
        roadmap_ids_str = f"({', '.join(map(str, roadmap_ids))})"
        query = f"""
            SELECT 
                rrk.roadmap_id,
                rrk.id AS kpi_id,
                rrk.name AS kpi_name,
                rrk.baseline_value
            FROM roadmap_roadmapkpi AS rrk
            WHERE rrk.roadmap_id IN {roadmap_ids_str}
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            kpis_by_roadmap = defaultdict(list)
            for row in data:
                row_dict = dict(zip(columns, row))
                roadmap_id = row_dict.pop('roadmap_id')
                kpis_by_roadmap[roadmap_id].append(row_dict)
            
            return dict(kpis_by_roadmap)
        except Exception as e:
            print(f"Error fetching key result data: {e}")
            return {}
    
    @staticmethod
    def fetch_team(cursor, roadmap_ids: Set[int]) -> Dict[int, List[Dict]]:
        """Fetch team members for multiple roadmaps."""
        roadmap_ids_str = f"({', '.join(map(str, roadmap_ids))})"
        query = f"""
            SELECT
                rre.roadmap_id,
                rre.id AS team_id,
                rre.name AS team_name,
                rre.unit AS team_unit_size,
                CASE 
                    WHEN rre.labour_type = 1 THEN 'Labour'
                    WHEN rre.labour_type = 2 THEN 'Non Labour'
                    ELSE 'Unknown'
                END AS labour_type,
                rre.estimate_value AS labour_estimate_value,
                CASE 
                    WHEN rre.type = 1 THEN 'person_days'
                    WHEN rre.type = 2 THEN 'person_months'
                    ELSE 'Unknown'
                END AS effort_type
            FROM roadmap_roadmapestimate AS rre
            WHERE rre.roadmap_id IN {roadmap_ids_str}
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            team_by_roadmap = defaultdict(list)
            for row in data:
                row_dict = dict(zip(columns, row))
                roadmap_id = row_dict.pop('roadmap_id')
                team_by_roadmap[roadmap_id].append(row_dict)
            
            return dict(team_by_roadmap)
        except Exception as e:
            print(f"Error fetching team data: {e}")
            return {}
    
    @staticmethod
    def fetch_scopes(cursor, roadmap_ids: Set[int]) -> Dict[int, List[Dict]]:
        """Fetch scope data for multiple roadmaps."""
        roadmap_ids_str = f"({', '.join(map(str, roadmap_ids))})"
        query = f"""
            SELECT 
                rrs.roadmap_id,
                rrs.id AS scope_id,
                rrs.name AS scope_name
            FROM roadmap_roadmapscope AS rrs
            WHERE rrs.roadmap_id IN {roadmap_ids_str}
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            scopes_by_roadmap = defaultdict(list)
            for row in data:
                row_dict = dict(zip(columns, row))
                roadmap_id = row_dict.pop('roadmap_id')
                scopes_by_roadmap[roadmap_id].append(row_dict)
            
            return dict(scopes_by_roadmap)
        except Exception as e:
            print(f"Error fetching scope data: {e}")
            return {}
    
    @staticmethod
    def fetch_priorities(cursor, roadmap_ids: Set[int]) -> Dict[int, List[Dict]]:
        """Fetch priority data for multiple roadmaps."""
        roadmap_ids_str = f"({', '.join(map(str, roadmap_ids))})"
        query = f"""
            SELECT 
                rr.id AS roadmap_id,
                CASE 
                    WHEN rr.priority = 1 THEN 'High'
                    WHEN rr.priority = 2 THEN 'Medium'
                    WHEN rr.priority = 3 THEN 'Low'
                    ELSE 'Unknown'
                END AS priority_level
            FROM roadmap_roadmap AS rr
            WHERE rr.id IN {roadmap_ids_str}
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            priorities_by_roadmap = defaultdict(list)
            for row in data:
                row_dict = dict(zip(columns, row))
                roadmap_id = row_dict.pop('roadmap_id')
                priorities_by_roadmap[roadmap_id].append(row_dict)
            
            return dict(priorities_by_roadmap)
        except Exception as e:
            print(f"Error fetching priority data: {e}")
            return {}
    
    @staticmethod
    def fetch_statuses(cursor, roadmap_ids: Set[int]) -> Dict[int, List[Dict]]:
        """Fetch status data for multiple roadmaps."""
        roadmap_ids_str = f"({', '.join(map(str, roadmap_ids))})"
        query = f"""
            SELECT 
                rr.id AS roadmap_id,
                CASE 
                    WHEN rr.current_state = 0 THEN 'Intake'
                    WHEN rr.current_state = 1 THEN 'Approved'
                    WHEN rr.current_state = 2 THEN 'Execution'
                    WHEN rr.current_state = 3 THEN 'Archived'
                    WHEN rr.current_state = 4 THEN 'Elaboration'
                    WHEN rr.current_state = 5 THEN 'Solutioning'
                    WHEN rr.current_state = 6 THEN 'Prioritize'
                    WHEN rr.current_state = 99 THEN 'Hold'
                    WHEN rr.current_state = 100 THEN 'Rejected'
                    WHEN rr.current_state = 999 THEN 'Cancelled'
                    WHEN rr.current_state = 200 THEN 'Draft'
                    ELSE 'Unknown'
                END AS status
            FROM roadmap_roadmap AS rr
            WHERE rr.id IN {roadmap_ids_str}
        """
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            statuses_by_roadmap = defaultdict(list)
            for row in data:
                row_dict = dict(zip(columns, row))
                roadmap_id = row_dict.pop('roadmap_id')
                statuses_by_roadmap[roadmap_id].append(row_dict)
            
            return dict(statuses_by_roadmap)
        except Exception as e:
            print(f"Error fetching status data: {e}")
            return {}

    def fetch_timelines(cursor, roadmap_ids: Set[int], tenant_id: int) -> Dict[int, List[str]]:
        """Fetch timeline transition data and convert them into readable strings."""
        if not roadmap_ids:
            return {}
        roadmap_ids_str = f"({', '.join(map(str, roadmap_ids))})"

        query = f"""
            SELECT 
                request_date,
                from_state,
                to_state,
                approval_status,
                request_id
            FROM public.authorization_approval_request
            WHERE request_type = 1
            AND tenant_id = {tenant_id}
            AND request_id IN {roadmap_ids_str}
            ORDER BY request_date
        """

        try:
            cursor.execute(query)
            data = cursor.fetchall()
            print(f"Fetched {len(data)} timeline records")
            columns = [desc[0] for desc in cursor.description]

            # Step 1: group raw rows by roadmap_id
            raw_by_roadmap = defaultdict(list)
            for row in data:
                row_dict = dict(zip(columns, row))
                raw_by_roadmap[row_dict["request_id"]].append(row_dict)

            # Step 2: convert entries into readable timeline strings
            timelines_by_roadmap = {}

            for roadmap_id, entries in raw_by_roadmap.items():
                result_strings = []

                for i, entry in enumerate(entries):
                    date = entry["request_date"]
                    from_state = STATE_MAP.get(entry["from_state"], "Unknown")
                    to_state   = STATE_MAP.get(entry["to_state"], "Unknown")
                    approval   = APPROVAL_MAP.get(entry["approval_status"], "unknown status")

                    date_str = date.strftime("%Y-%m-%d")

                    # Base natural-language string
                    text = f"On {date_str}, moved from {from_state} to {to_state}, {approval}."

                    if i < len(entries) - 1:
                        # Add duration before next transition
                        next_date = entries[i + 1]["request_date"]
                        days_in_stage = (next_date - date).days
                        text += f" ({days_in_stage} days in this stage)"
                    else:
                        # Last entry
                        text += " (current)"

                    result_strings.append(text)

                timelines_by_roadmap[roadmap_id] = result_strings
            
            return timelines_by_roadmap

        except Exception as e:
            print(f"Error fetching timeline data: {e}")
            return {}


    @staticmethod
    def fetch_categories(roadmap: Dict) -> List[Dict]:
        """Extract roadmap categories from roadmap data."""
        category = roadmap.get("category", "")
        if not category or category == "":
            return []
        return [{"roadmap_category_id": category.lower(), "name": category}]
    
    @staticmethod
    def fetch_roadmap_types(roadmap: Dict) -> List[Dict]:
        """Extract roadmap type from roadmap data."""
        roadmap_type = roadmap.get("roadmap_type", "")
        if not roadmap_type or roadmap_type == "":
            return []
        return [{"roadmap_type_id": roadmap_type.lower(), "name": roadmap_type}]
    
    @staticmethod
    def fetch_solutions(roadmap: Dict) -> List[Dict]:
        """Extract solution data from roadmap data."""
        solution_content = roadmap.get("solution", "")
        if not solution_content or solution_content == "":
            return []
        
        # Create solution vertex with unique ID based on roadmap
        roadmap_id = roadmap.get("roadmap_id", 0)
        solution_id = f"solution_{roadmap_id}"
        
        return [{
            "solution_id": solution_id,
            "title": f"Solution for Roadmap {roadmap_id}",
            "description": solution_content
        }]
