from src.trmeric_database.Database import db_instance
import traceback
from datetime import datetime
import json


class IntegrationDao:

    @staticmethod
    def fetchProjectMapping(tenant_id, project_id, integration_type):
        query = f"""
        select * from integration_projectmapping where tenant_id = {tenant_id} and projec
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchActiveIntegrationForUser(user_id, integration_type):
        query = f"""
        select * 
        from integration_userconfig 
        where user_id = {user_id} 
        -- and status = 'Active'  
        and integration_type = '{integration_type}'
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    

    @staticmethod
    def fetchMappingForConfig(user_config_id):
        query = f"""
        select * from integration_projectmapping where user_config_id = {user_config_id}
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchMappingsForTenant(tenant_id, integration_type):
        query = f"""
        SELECT *
        FROM integration_projectmapping
        WHERE tenant_id = {tenant_id}
        AND integration_type = '{integration_type}'
        """
        return db_instance.retrieveSQLQueryOld(query)


    @staticmethod
    def fetchAllProjectIntegrations(project_id):
        # SQL query to fetch all mappings and corresponding data
        query = f"""
            SELECT DISTINCT ON (ip.integration_type)
                ip.id AS id,
                ip.integration_type AS type,
                ip.metadata AS metadata,
                ipd.data AS data,
                ipd.last_updated_date
            FROM 
                integration_projectmapping ip
            LEFT JOIN 
                integration_projectdata ipd
                ON ip.id = ipd.project_mapping_id
            WHERE 
                ip.trmeric_project_id = {project_id}
            ORDER BY 
                ip.integration_type,
                ipd.last_updated_date DESC;
        """
        # Execute the query
        integrationData = db_instance.retrieveSQLQueryOld(query)

        # Aggregate the data into a dictionary
        projectIntegrations = []
        for integration in integrationData:
            projectIntegrations.append({
                "project_id": project_id,
                "type": integration["type"],
                "metadata": integration["metadata"],
                "data": integration["data"]
            })

        return projectIntegrations

    @staticmethod
    def getJiraDataYesterdayUpdateData(tenant_id):
        query = f"""
            WITH latest_entries AS (
                SELECT 
                    project_mapping_id,
                    MAX(last_updated_date) AS max_last_updated_date
                FROM 
                    public.integration_projectdata
                WHERE 
                    tenant_id = {tenant_id}
                GROUP BY 
                    project_mapping_id
            )
            SELECT 
                wp.title,
                ipm.metadata,
                ipd.data,
                ipd.last_updated_date
            FROM 
                public.integration_projectdata ipd
            JOIN 
                latest_entries le
            ON 
                ipd.project_mapping_id = le.project_mapping_id
                AND ipd.last_updated_date = le.max_last_updated_date
            join workflow_project wp
            on 
            ipd.project_mapping_id = wp.id
            join integration_projectmapping ipm
            on 
            ipd.project_mapping_id = ipm.id
            WHERE 
                ipd.tenant_id = {tenant_id} and ipm.integration_type = 'jira';
        """
        results = db_instance.retrieveSQLQueryOld(query)
        final_data = []
        try:
            if results:
                for res in results:
                    json_data = res.get("data", {})
                    if isinstance(json_data, dict) and json_data.get("module") in ["v1", "v2"]:
                        projects_data = json_data.get("projects", [])
                        for project in projects_data:
                            project_name = project.get("project", None)
                            project_data_array = project.get("data", [])
                            for project_data in project_data_array:
                                if project_data.get("sprint_status") == "in_progress":
                                    sprint_name = project_data.get(
                                        "sprint_name")
                                    # Extract burndown_chart dictionary
                                    burndown_chart = project_data.get(
                                        "burndown_chart", {})

                                    # Convert burndown_chart to a list of tuples (date, remaining_story_points)
                                    burndown_list = [
                                        (date, details["remaining_story_points"]) for date, details in burndown_chart.items()]

                                    # Sort the list by date in descending order
                                    burndown_list.sort(key=lambda x: datetime.strptime(
                                        x[0], "%Y-%m-%d"), reverse=True)

                                    # Get the last two entries
                                    last_two_entries = burndown_list[:2]

                                    # Convert back to dictionary
                                    burndown_data = {
                                        date: {"remaining_story_points": points} for date, points in last_two_entries}

                                    final_data.append({
                                        "project_name": project_name,
                                        "ongoing_sprint_name": sprint_name,
                                        "burndown_data": burndown_data
                                    })
                                    # burndown = project_data.get("burndown_chart", [])
                                    # burndown = burndown[-2:]
                                    # final_data.append({
                                    #     "project_name": project_name,
                                    #     "ongoing_sprint_name": sprint_name,
                                    #     "burndown_data": burndown
                                    # })
        except Exception as e:
            print("error in fetching latest jira data ",
                  e, traceback.format_exc())
        return final_data

    @staticmethod
    def getJiraLatestDataForMappingId(mapping_id, module, get_all_data=True):
        query = f"""
            select * 
            from integration_projectdata 
            where project_mapping_id = {mapping_id}
            order by last_updated_date desc 
            limit 1
        """
        # print("debug -- getJiraLatestDataForMappingId --- ", query, module)
        result = ""
        epics_taken = []
        projects_taken = []
        try:
            result_set = db_instance.retrieveSQLQueryOld(query)
            if not result_set:
                return "No data found"
            # print("debug -- getJiraLatestDataForMappingId ------ result_set --- ", True if result_set else False, len(result_set))
            # if result_set:
            res = result_set[0]
            try:
                json_data = res.get("data", {})
                # print("debug --- ", module)
                # return json.dumps(json_data)
                if module == "v4":
                    result += f"""
                        -------------------------
                    """
                    for res in json_data.get("epics_analysis", []) or []:
                        for item in res.get("child_epics_stats", []) or []:
                            epic_id = item.get("epic_id", "") or ""
                            if (epic_id == ""):
                                continue
                            if epic_id in epics_taken:
                                continue

                            epics_taken.append(epic_id)
                            result += f"""
                                Epic Stats:
                                Epic Id - {item.get("epic_id")}
                                Epic Name - {item.get("epic_name")}
                                
                                child_epics_stats:
                                {item}
                            """
                    result += f"""
                    --------------
                    Projects to be reviewed for this-
                    ---------------------   
                    """
                    for res in json_data.get("epics_analysis") or []:
                        result += f"""
                            {[d["project"] for d in res.get("projects") or []]}
                        """

                    # Adding issues of the ongoing sprint for v4
                    for res in json_data.get("epics_analysis", []) or []:
                        for project in res.get("projects", []) or []:
                            if project.get("sprint_status") == "in_progress":
                                result += json.dumps(project)
                                # result += f"""
                                # -----------------------
                                # For Sprint with name: {project.get("sprint_name")} - status of sprint: {project.get("sprint_status")}
                                # Issues in the project {project.get("project")}:
                                # <issues_of_sprint>
                                # {project.get("all_issues")}
                                # <issues_of_sprint>
                                # ---------------------
                                # """

                if module == "v2":
                    result += f"""
                    --------------------------
                    Epic Info - {json_data.get("metadata")}
                        Child Epic Stats ---
                        {json_data.get("child_epics_stats", [])}
            
                    """
                    result += f"""
                    Projects to be reviewed for this-
                        {[d["project"] for d in json_data.get("projects") or []]}
                    """

                    # Adding issues of the ongoing sprint for v2
                    for project in json_data.get("projects", []) or []:
                        if project.get("sprint_status") == "in_progress":
                            result += json.dumps(project)
                            # result += f"""
                            # -----------------------
                            # For Sprint with name: {project.get("sprint_name")} - status of sprint: {project.get("sprint_status")}
                            # Issues in the project {project.get("project")}:
                            # <issues_of_sprint>
                            # {project.get("all_issues")}
                            # <issues_of_sprint>
                            # ---------------------
                            # """

                if module == "v1":
                    result += f"""
                    Jira Project Data:
                    ----------
                    """
                    # print("debug -*****-- ",projects_taken)
                    for pd in json_data.get("projects", []) or []:
                        if pd.get("project") in projects_taken:
                            continue
                        projects_taken.append(pd.get("project"))

                        for d in pd.get("data", []) or []:
                            if d.get("sprint_status") == "in_progress":
                                text = ''
                                if get_all_data:
                                    text = f"""
                                    Epics in the project {d.get("project")} are:
                                    <epics>
                                    {d.get("epics")}
                                    <epics>
                                    <burndown_chart>
                                    {d.get("burndown_chart")}
                                    <burndown_chart>
                                    """
                                result += f"""
                                -----------------------
                                For Sprint with name: {d.get("sprint_name")} - status of sprint: {pd.get("sprint_status")}
                                Sprint Start : {d.get("sprint_start_date")} and End at: {d.get("sprint_end_date")}
                                
                                Sprint Possible Risks: {d.get("risks")}
                                
                                {text}
                                
                                Always do a detail list of this to user. Also remember to always mention the required issues names
                                One by one check all issues/features/bug/stories_of_ongoing_sprint and do correct analysis:
                                <issues/features/bug/stories_of_ongoing_sprint>
                                {d.get("issue_level_analysis").get("all_issues")}
                                <issues/features/bug/stories_of_ongoing_sprint>
                                ---------------------
                                """

                # projects_data = json_data.get("projects", [])
                # for project in projects_data:
                #     project_name = project.get("project", None)
                #     project_data_array = project.get("data", [])
                #     for project_data in project_data_array:
                #         if project_data.get("sprint_status") == "in_progress":
                #             sprint_name = project_data.get("sprint_name")
                #             all_issues = project.get("")
                #             # print("debug in getJiraLatestDataForMappingId 7",
                #             #       project_data.get("sprint_status"), module)
                #             if module == "v1":
                #                 result += f"""
                #                     For Jira Project: {project_name}
                #                     Ongoing Sprint: {sprint_name}
                #                     Current Sprint Data and other analysis result:
                #                     {json.dumps(project_data, indent=4)}
                #                 """
                #             elif module == "v2":
                #                 result += f"""
                #                     For Jira Project: {project_name}
                #                     Ongoing Sprint: {sprint_name}
                #                     Current Sprint Data and other analysis result:
                #                     {json.dumps(project_data, indent=4)}
                #                 """
                #             elif module == "v4":
                #                 result += f"""
                #                     For Jira Project: {project_name}
                #                     Ongoing Sprint: {sprint_name}
                #                     Current Sprint Data and other analysis result:
                #                     {json.dumps(project_data, indent=4)}
                #                 """

                return result
            except Exception as e1:
                print("debug -- error ", e1, traceback.format_exc())
                return ""

                # projects_data = json_data.get("projects", []) or []
                # for project in projects_data:
                #     project_name = project.get("project", None)
                #     project_data_array = project.get("data", []) or []
                #     for project_data in project_data_array:
                #         if project_data.get("sprint_status") == "in_progress":
                #             sprint_name = project_data.get("sprint_name")
                #             temp = project_data["issue_level_analysis"]
                #             del temp["all_issues"]
                #             pd = {
                #                 "project_id": project_name,
                #                 "sprint_name": project_data["sprint_name"],
                #                 "committed_sp": project_data["committed_sp"],
                #                 "delivered_sp": project_data["delivered_sp"],
                #                 "in_progress_sp": project_data["in_progress_sp"],
                #                 "sprint_status": project_data["sprint_status"],
                #                 "velocity_of_sprint": project_data["delivered_sp"],
                #                 "sprint_end_date": project_data["sprint_end_date"],
                #                 "sprint_start_date": project_data["sprint_start_date"],
                #                 "predicted_sp_to_be_delivered_for_ongoing_sprint": project_data["predicted_sp_delivered"],
                #                 "issue_level_analysis": temp,
                #                 "issue_level_analysis_llm": project_data["issue_level_analysis_llm"],
                #                 "burndown_chart": project_data["project_name"],
                #             }
                #             if module == "v1":
                #                 result += f"""
                #                     For Jira Project: {project_name}
                #                     Ongoing Sprint: {sprint_name}
                #                     Current Sprint Data and other analysis result:
                #                     {json.dumps(pd, indent=4)}
                #                 """
                #             elif module == "v2":
                #                 result += f"""
                #                     For Jira Project: {project_name}
                #                     Ongoing Sprint: {sprint_name}
                #                     Current Sprint Data and other analysis result:
                #                     {json.dumps(pd, indent=4)}
                #                 """
                #             elif module == "v4":
                #                 result += f"""
                #                     For Jira Project: {project_name}
                #                     Ongoing Sprint: {sprint_name}
                #                     Current Sprint Data and other analysis result:
                #                     {json.dumps(pd, indent=4)}
                #                 """
                # else:
                #     if module == "v2" or module == "v3":
                #         result += f"""
                #             Other Jira Projects for this Mapping
                #             ----
                #             Jira Project: {project_name}
                #             ----
                #         """

        except Exception as e:
            print("exception happened here ... ", e, traceback.format_exc())
            # return result

        return result

    @staticmethod
    def getAdoLatestDataForMapping(mapping_id, module):
        query = f"""
            select * 
            from integration_projectdata 
            where project_mapping_id = {mapping_id}
            order by last_updated_date desc 
            limit 1
        """
        result = db_instance.retrieveSQLQueryOld(query)
        if len(result) > 0:
            return json.dumps(result[0]["data"])
        else:
            return ""
        # return json.dumps(result)

    @staticmethod
    def getSmartsheetLatestDataForMapping(mapping_id):
        query = f"""
            select * 
            from integration_projectdata 
            where project_mapping_id = {mapping_id}
            order by last_updated_date desc 
            limit 1
        """
        result = db_instance.retrieveSQLQueryOld(query)
        return json.dumps(result)

    @staticmethod
    def getGithubLatestDataForMapping(mapping_id):
        query = f"""
            select * 
            from integration_projectdata 
            where project_mapping_id = {mapping_id}
            order by last_updated_date desc 
            limit 1
        """
        result = db_instance.retrieveSQLQueryOld(query)
        return result

    @staticmethod
    def fetchIntegrationMappingForTenantAndUser(tenant_id, user_id, integration_type):
        query = f"""
            select * from integration_projectmapping
            where user_id = {user_id} and tenant_id = {tenant_id}
            and integration_type = '{integration_type}'
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchAllIntegratinoMappingForUser(user_id):
        query = f"""
        SELECT trmeric_project_id, user_id , tenant_id FROM public.integration_projectmapping
            where  user_id = {user_id}
        ORDER BY id ASC 
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchIntegrationDataForTenantAndUser(tenant_id, user_id, integration_type):
        query = f"""
            SELECT 
                ipd.project_mapping_id,
                ipd.last_updated_date,
                ipd.data
            FROM 
                integration_projectdata ipd
            WHERE 
                ipd.last_updated_date = (
                    SELECT 
                        MAX(ipd_sub.last_updated_date)
                    FROM 
                        integration_projectdata ipd_sub
                    WHERE 
                        ipd_sub.project_mapping_id = ipd.project_mapping_id
                )
                AND ipd.project_mapping_id IN (
                    SELECT 
                        ipm.id
                    FROM 
                        integration_projectmapping ipm
                    WHERE 
                        ipm.user_id = {user_id}
                        AND ipm.tenant_id = {tenant_id}
                        AND ipm.integration_type = '{integration_type}'
                )
            ORDER BY 
                ipd.last_updated_date DESC;

        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchIntegrationMappingForProjectForIntegrationType(project_id, integration_type):
        project_ids_str = f"({', '.join(map(str, project_id))})"
        query = f"""
            select * from integration_projectmapping 
                where trmeric_project_id in {project_ids_str}
                and integration_type = '{integration_type}'
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def getJiraLatestDataForMappingIdV2(mapping_id, module, get_all_data=True):
        query = f"""
            select * 
            from integration_projectdata 
            where project_mapping_id = {mapping_id}
            order by last_updated_date desc 
            limit 1
        """
        result = ""
        epics_taken = []
        projects_taken = []
        try:
            result_set = db_instance.retrieveSQLQueryOld(query)
            if not result_set:
                return "No data found", ""

            res = result_set[0]
            try:
                json_data = res.get("data", {})
                _module = json_data.get("module") or ""
                print("debug getJiraLatestDataForMappingIdV2--- ", module, _module)
                if _module == "v6":
                    return res, "v6"

                if module == "v4":
                    return json_data,  "v4"

                if module == "v5":
                    return res, "v5"

                if module == "v2":
                    result += f"""
                    --------------------------
                    Epic Info - {json_data.get("metadata")}
                        Child Epic Stats ---
                        {json_data.get("child_epics_stats", [])}
            
                    """
                    result += f"""
                    Projects to be reviewed for this-
                        {[d["project"] for d in json_data.get("projects") or []]}
                    """

                    # Adding issues of the ongoing sprint for v2
                    for project in json_data.get("projects", []) or []:
                        if project.get("sprint_status") == "in_progress":
                            result += json.dumps(project)

                if module == "v1":
                    result += f"""
                    Jira Project Data:
                    ----------
                    """
                    # print("debug -*****-- ",projects_taken)
                    for pd in json_data.get("projects", []) or []:
                        if pd.get("project") in projects_taken:
                            continue
                        projects_taken.append(pd.get("project"))

                        for d in pd.get("data", []) or []:
                            if d.get("sprint_status") == "in_progress":
                                text = ''
                                if get_all_data:
                                    text = f"""
                                    Epics in the project {d.get("project")} are:
                                    <epics>
                                    {d.get("epics")}
                                    <epics>
                                    <burndown_chart>
                                    {d.get("burndown_chart")}
                                    <burndown_chart>
                                    """
                                result += f"""
                                -----------------------
                                For Sprint with name: {d.get("sprint_name")} - status of sprint: {pd.get("sprint_status")}
                                Sprint Start : {d.get("sprint_start_date")} and End at: {d.get("sprint_end_date")}
                                
                                Sprint Possible Risks: {d.get("risks")}
                                
                                {text}
                                
                                Always do a detail list of this to user. Also remember to always mention the required issues names
                                One by one check all issues/features/bug/stories_of_ongoing_sprint and do correct analysis:
                                <issues/features/bug/stories_of_ongoing_sprint>
                                {d.get("issue_level_analysis").get("all_issues")}
                                <issues/features/bug/stories_of_ongoing_sprint>
                                ---------------------
                                """

                return result, ""
            except Exception as e1:
                print("debug -- error ", e1, traceback.format_exc())
                return ""

        except Exception as e:
            print("exception happened here ... ", e, traceback.format_exc())
            # return result

        return result

    @staticmethod
    def fetchIntegrationListForTenantAndUserAndType(tenant_id, user_id, integration_type):
        query = f"""
            SELECT 
                pm.*
            FROM 
                integration_userconfig uc
                JOIN integration_projectmapping pm ON uc.id = pm.user_config_id
            WHERE 
                uc.tenant_id = {tenant_id}
                AND pm.user_id = {user_id}
                AND uc.status = 'Active'
                AND uc.integration_type = '{integration_type}';
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def fetchActiveIntegrationForUserV2(user_id, integration_type):
        query = f"""
        select * 
        from integration_userconfig 
        where user_id = {user_id} 
        and status = 'Active'  
        and integration_type = '{integration_type}'
        """
        res = db_instance.retrieveSQLQueryOld(query)
        if len(res) > 0:
            return res[0]
        else:
            return None

    def insertEntryToIntegrationProjectMapping(
        tenant_id,
        user_id,
        user_config_id,
        integration_project_identifier,
        integration_type,
        trmeric_project_id,
        metadata
    ):
        query = """
            INSERT INTO public.integration_projectmapping (
                integration_project_identifier,
                integration_type,
                created_date,
                metadata,
                tenant_id,
                trmeric_project_id,
                user_id,
                user_config_id
            )
            VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s)
            RETURNING id
        """
        params = (
            integration_project_identifier,
            integration_type,
            metadata,
            tenant_id,
            trmeric_project_id,
            user_id,
            user_config_id
        )
        return db_instance.executeSQLQuery(query, params)

    def fetchIntegrationUserConfigId(user_id, integration):
        query = f"""
        select * from integration_userconfig where user_id = {user_id} and integration_type = '{integration}'
        """
        res = db_instance.retrieveSQLQueryOld(query)
        if len(res) > 0:
            return res[0]["id"]
        else:
            return None

    def fetchLatestIntegrationMappingOfUser(user_id, integration):
        query = f"""
        select * from integration_projectmapping 
        where user_id = {user_id} and integration_type = '{integration}'
        order by id desc
        """
        res = db_instance.retrieveSQLQueryOld(query)
        if len(res) > 0:
            return res[0]["id"]
        else:
            return None
        
        
    @staticmethod
    def fetchLatestGithubData(tenant_id,user_id,project_id):
        query = f"""
            SELECT 
                data,last_updated_date 
            FROM 
                integration_projectdata
            WHERE 
                project_mapping_id IN (
                SELECT id FROM integration_projectmapping
                WHERE integration_type = 'github'
                AND trmeric_project_id = {project_id}
            )
            AND 
                tenant_id = {tenant_id} and user_id = {user_id}
            ORDER BY 
                last_updated_date DESC
            LIMIT 1
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception:
            return None
        
        
        
    @staticmethod
    def fetchMappingsForTenantAndProjectId(tenant_id, project_id):
        if not project_id or not tenant_id:
            return []
        
        query = f"""
        SELECT ipm.*, wp.title as project_title
        FROM integration_projectmapping as ipm
        left join workflow_project as wp on wp.id = ipm.trmeric_project_id
        WHERE ipm.tenant_id = {tenant_id}
        AND ipm.trmeric_project_id = {project_id}
        order by id desc
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception:
            return []
    
    
    @staticmethod
    def getIntegrationDataForMapping(mapping_id):
        query = f"""
            select * 
            from integration_projectdata 
            where project_mapping_id = {mapping_id}
            order by last_updated_date desc 
            limit 1
        """
        result = db_instance.retrieveSQLQueryOld(query)
        if len(result) > 0:
            return result[0]["data"]
        else:
            return ""


    @staticmethod
    def fetchIntegrationMappingInfoFromId(id):
        query = f"""
            select * 
            from integration_projectmapping 
            where id = {id}
        """
        result = db_instance.retrieveSQLQueryOld(query)
        if len(result) > 0:
            return result[0]
        else:
            return None
        
    @staticmethod
    def getRefreshTokenFromIntegrationConfig(tenant_id, user_id, integration_type):
        query = f"""
            select * 
            from integration_userconfig 
            where user_id = {user_id} and integration_type = '{integration_type}'
        """
        result = db_instance.retrieveSQLQueryOld(query)
        # print("resfresh tojkenn -- data -- ", result[0])
        if len(result) > 0:
            res = result[0]
            meta = res.get("metadata") or {}
            return meta.get("refresh_token")
        else:
            return ""
        
    @staticmethod
    def fetchActiveProjectMappingsFortenant(tenant_id):
        query = f"""
            SELECT ipm.id, ipm.user_id, ipm.tenant_id, ipm.trmeric_project_id, ipm.integration_type
            FROM integration_projectmapping AS ipm
            LEFT JOIN integration_userconfig AS iuc 
                ON iuc.id = ipm.user_config_id
            LEFT JOIN workflow_project AS wp
                ON wp.id = ipm.trmeric_project_id
                AND wp.tenant_id_id = ipm.tenant_id
            WHERE iuc.status = 'Active'
            AND ipm.tenant_id = {tenant_id}
            AND wp.archived_on is null
            ORDER BY ipm.id ASC
        """
        data = db_instance.retrieveSQLQueryOld(query)
        return data
    
    
    @staticmethod
    def fetchActiveProjectSourcesForTenant(tenant_id):
        query = f"""
            SELECT  wp.id as project_id, wp.title as project_title, ipm.integration_type, ipm.integration_project_identifier, ipm.metadata
            FROM integration_projectmapping AS ipm
            LEFT JOIN integration_userconfig AS iuc 
                ON iuc.id = ipm.user_config_id
            LEFT JOIN workflow_project AS wp
                ON wp.id = ipm.trmeric_project_id
                AND wp.tenant_id_id = ipm.tenant_id
            WHERE iuc.status = 'Active'
            AND ipm.tenant_id = {tenant_id}
            AND wp.archived_on is null
            ORDER BY ipm.id ASC
        """
        data = db_instance.retrieveSQLQueryOld(query)
        return data
    
    @staticmethod
    def fetchAllProjectMappingsFortenant(tenant_id):
        query = f"""
            SELECT ipm.id, ipm.user_id, ipm.tenant_id, ipm.trmeric_project_id, ipm.integration_type
            FROM integration_projectmapping AS ipm
            LEFT JOIN workflow_project AS wp
                ON wp.id = ipm.trmeric_project_id
                AND wp.tenant_id_id = ipm.tenant_id
            WHERE ipm.tenant_id = {tenant_id}
            AND wp.archived_on is null
            ORDER BY ipm.id ASC
        """
        data = db_instance.retrieveSQLQueryOld(query)
        return data

    
        
    @staticmethod
    def getIntegrationLatestUpdatedDataForIntegrationOfProjectId(project_id):
        query = f"""
            SELECT 
                ipm.integration_type, 
                ipd_latest.last_updated_date
            FROM integration_projectmapping AS ipm
            LEFT JOIN LATERAL (
                SELECT *
                FROM integration_projectdata AS ipd
                WHERE ipd.project_mapping_id = ipm.id
                ORDER BY ipd.id DESC
                LIMIT 1
            ) AS ipd_latest ON true
            WHERE ipm.trmeric_project_id IN (
                {project_id}
            );
        """
        return db_instance.retrieveSQLQueryOld(query)
    

    def insertOrUpdateIntegrationUserConfig(tenant_id, user_id, integration_type, metadata, status="Active"):
        """
        Inserts a new integration_userconfig row or updates the existing one if it already exists
        for the same tenant_id, user_id, and integration_type.
        """
        # Check if already exists
        check_query = f"""
            SELECT id FROM public.integration_userconfig
            WHERE tenant_id = {tenant_id} AND user_id = {user_id} AND integration_type = '{integration_type}'
        """
        existing = db_instance.retrieveSQLQueryOld(check_query)
        if existing and len(existing) > 0:
            existing_id = existing[0]["id"]
            update_query = """
                UPDATE public.integration_userconfig
                SET status = %s,
                    metadata = %s,
                    created_date = NOW()
                WHERE id = %s
                RETURNING id
            """
            params = (status, metadata, existing_id)
            return db_instance.executeSQLQuery(update_query, params)
        else:
            insert_query = """
                INSERT INTO public.integration_userconfig
                    (integration_type, created_date, status, metadata, tenant_id, user_id)
                VALUES (%s, NOW(), %s, %s, %s, %s)
                RETURNING id
            """
            params = (integration_type, status, metadata, tenant_id, user_id)
            return db_instance.executeSQLQuery(insert_query, params)



    @staticmethod
    def is_user_on_prem_jira(user_id):
        results = IntegrationDao.fetchActiveIntegrationForUser(user_id=user_id, integration_type='jira')
        for r in results:
            meta = r.get("metadata")
            auth = meta.get("auth_method")
            if auth == "PAT":
                return True
        return False
        