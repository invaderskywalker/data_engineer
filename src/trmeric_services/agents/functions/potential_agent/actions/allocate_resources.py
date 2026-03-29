import os
import json
import datetime
import requests
import traceback
from src.trmeric_database.Database import db_instance
from src.trmeric_database.dao import TangoDao, TenantDaoV2
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_services.agents.functions.potential_agent.prompts import  allocate_resources_prompt_v2
from src.trmeric_services.integration.project_status.base import BaseInsightsProcessorClass
from src.trmeric_services.agents.functions.potential_agent.utils import restrict_check,find_best_resource_match,register_action


"""
    Analysing the user query and the conversation user may say I wish to assign project to a resource.then the first understanding llm
    similar to update_details_prompt will ask clarifying info like which resource we are talking about and tell me the project(s).
    
    Then user will say the name of the projects and resources and accordingly it should get all those in assign_data  List[Dict[str, Any]] (like resource_data)
    if resource has mentioned a project name then you will get the project ids from workflow_project
    query: select id,title from workflow_project where title ilike '%{project_name}%'
    If multiple projects are matching then ask user which ones to go with
    Using project ids then you have to check whether a team is present in the project or not and project manager is assigned?
    
    query: select team_id from workflow_projectteamsplit
            where project_id = 3725 and team_id is not null;
            select project_manager_id_id from workflow_project where title ilike '%{project_name}%'
    
    If these are not present then tell the user and exit the flow
    else: 
        you need to prepare a nice mapping of resource_ids and the project they will be assigned to as per the user query    
"""

@register_action("assign_to_project")
def allocate_resources(
    tenantID: int,
    userID: int,
    llm=None,
    plan=None,
    user_query=None,
    socketio=None,
    client_id=None,
    session_id=None,
    context_string=None,
    **kwargs
):
    """
    Assign resources to projects based on user query, validating project team and manager assignments.
    Returns assign_data with resource_id, project_id, and project details.
    """
    tenant_id =tenantID
    user_id = userID
    sender = kwargs.get("step_sender")
    model_opts = kwargs.get("model_opts2")
    conversation = kwargs.get("conversation",[]) or []
    print("\n\n----debug conversation ------------------------------1", conversation)

    print("--debug in allocate_resources---", user_query, session_id, user_id, tenant_id)
    try:
       
        formatted_conversation = conversation
        assign_params = plan.get("assign_params",[]) or []
        print("--debug assign_params-----", plan, "\n update pasrsr", assign_params)
        resource_data = TenantDaoV2.fetchResourceDataWithProjectionAttrs(
            tenant_id=tenant_id,
            projection_attrs=["id","first_name","last_name","role",
                "current_allocation",
                "past_projects","current_projects","future_projects","org_team","portfolio",
            ]
        )

        resources_in_context = []
        for data in assign_params:
            name = data.get('resource_name', '').strip().lower()
            
            # Try to find exact or close match
            # for r in resource_data:
            #     full_name = f"{r.get('first_name','')} {r.get('last_name','')}".strip().lower()
            #     if name in full_name or full_name in name:
            #         resources_in_context.append(r)
            rmatch = find_best_resource_match(name, resource_data)
            print("--debug match------", name, "→", rmatch)
            if rmatch:
                resources_in_context.append(rmatch)

        print("\n\n--debug resources_in_context-------", resources_in_context)
        context_string += f"""
            These are all the details of the resources to whom projects is to be allocated.
            ----------------------
            Resources data: {json.dumps(resources_in_context,indent=2)}
        """


        # Generate prompt to extract resource targets and project details
        prompt = allocate_resources_prompt_v2(
            user_query=user_query, 
            conversation=formatted_conversation, 
            context_string=context_string
        )
        # print("\n\n--debug allocatre_resources prompot------------", prompt.formatAsString())
        response = llm.run(prompt,model_opts,"agent::potential::extract_assignments",
            {"tenant_id": tenant_id, "user_id": user_id},socketio=socketio,client_id=client_id
        )

        extract_output = extract_json_after_llm(response, step_sender=sender)
        print("\n\n--debug allocate_resources_promptres---", extract_output)
        
        clarifying_info = extract_output.get("clarifying_info", "")
        assign_project_to_resource = extract_output.get("assign_project_to_resources") or []
        # resource_targets = extract_output.get("resource_targets", [])
        # project_details = extract_output.get("project_details", {})
        print("--debug Resource assign_project_to_resource---", assign_project_to_resource)

        # Handle clarification case
        if clarifying_info:
            print(f"Clarifying information extracted: {clarifying_info}")
            TangoDao.insertTangoState(
                tenant_id=tenant_id,
                user_id=user_id,
                key=f"clarification_{session_id}",
                value=json.dumps({"conversation": user_query, "clarification": clarifying_info}),
                session_id=session_id
            )
            return clarifying_info

        # Check for valid resource targets
        resource_targets = [item["resource_name"] for item in assign_project_to_resource if "resource_name" in item]
        if not resource_targets:
            error_msg = "⚠️ No resource targets identified in the query. Please specify the resources to proceed."
            return error_msg

        

        # Resolve project details to project IDs
        assign_data = [] #to be sent in API payload
        project_clarification_needed = []
        # is_per_resource = all(key in resource_targets for key in project_details.keys())
        
        

        for data in assign_project_to_resource:
            proj_id = data.get("project_id")
            resource_name = data.get("resource_name")
            resource_id = data.get("resource_id")
            project_title = data.get("project_title")

            # Validate team and project manager
            team_query = f"SELECT id FROM public.workflow_projectteam WHERE project_id = {proj_id}"
            team_matched = db_instance.retrieveSQLQueryOld(team_query)
            
            pm_query = f"SELECT project_manager_id_id,start_date,end_date FROM public.workflow_project WHERE id = {proj_id};"
            pm_matched = db_instance.retrieveSQLQueryOld(pm_query)

            if not team_matched or not pm_matched:
                error_msg = f"⚠️ Project '{project_title}' is missing either a team or project manager.Please ensure both are assigned before proceeding."
                return error_msg

            # Validate allocation
            allocation = data.get("allocation",0) or 0
            if allocation in (None, '', " "):
                allocation = 0  # default to 0 if empty or None
            if allocation is not None:
                try:
                    alloc = int(allocation)
                    if not 0 <= alloc <= 100:
                        error_msg = f"⚠️ Invalid allocation {alloc}% for resource {resource_name}. Allocation must be between 0 and 100."
                        return error_msg
                except (ValueError, TypeError):
                    error_msg = f"Invalid allocation format for resource {resource_name}: {allocation}"
                    return error_msg

            # Validate dates if provided
            start_date = pm_matched[0].get("start_date") or None
            end_date = pm_matched[0].get("end_date") or None
            # print("--proj timeline---------", start_date,end_date)
            if start_date and end_date:
                try:
                    start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                    end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
                    if end < start:
                        return f"End date {end_date} must be after start date {start_date} for resource {resource_name}"
                        
                except ValueError:
                    return f"Invalid date format for resource {resource_name}: start_date={start_date}, end_date={end_date}"

            # Build assign_data
            assign_entry = {
                "id": resource_id,
                "name":resource_name,
                "project_id": proj_id,
                "project_title": project_title,
                "start_date": start_date,
                "end_date": end_date,
                **{k: v for k, v in data.items() if k in ["allocation"]}
            }
            assign_data.append(assign_entry)

        print("\n\n---debug assign_data-------", assign_data)

        # If clarification is needed for projects, send options
        if project_clarification_needed:
            print(f"Multiple project matches found: {project_clarification_needed}")
            return f"Multiple projects found for names: {', '.join(set([d.get('project_title') for d in assign_project_to_resource.values()]))}. Please specify the name."

        # print("--debug assign_data--------", assign_data)

       
    
        # Insert assignments into capacity_resource_timeline
        responses = []
        assign_data = restrict_check(user_id = user_id,tenant_id=tenant_id,resource_data=assign_data,responses = responses,type='assign')

        print("--debug resource_data after------------------ 2", assign_data)
        for data in assign_data:
            print("--deubg data----------", data)
            
            resource_id = data["id"]
            resource_name = data['name']
            project_id = data["project_id"]
            project_name = data['project_title']
            project_start_date, project_end_date = data.get("start_date",None) , data.get("end_date",None)
            print("\n--debug project timeline: ", project_id, "Dates: ", project_start_date, project_end_date)
            
            fields = ["resource_id", "trmeric_project_id", "tenant_id", "created_by_id", "created_on","project_name"]
            values = [resource_id, project_id, tenant_id, user_id, datetime.datetime.now(),project_name]
            placeholders = ["%s"] * len(fields)

            for key in ["start_date", "end_date", "allocation","project_name"]:
                if data.get(key) is not None:  # Only include non-null values
                    fields.append(key)
                    values.append(data[key])
                    placeholders.append("%s")

            check_query = f"""
                SELECT id FROM public.capacity_resource_timeline
                WHERE resource_id = {resource_id} AND trmeric_project_id = {project_id}
            """
            check_res = db_instance.retrieveSQLQueryOld(check_query)
            
            role_query = f"""
                SELECT role, email, country FROM public.capacity_resource
                WHERE id = {resource_id}
            """
            role_data = db_instance.retrieveSQLQueryOld(role_query)
            _role = ''
            _email = ''
            _location = ''
            if len(role_data) > 0:
                _role = role_data[0].get("role") or ''
                _email = role_data[0].get("email") or ''
                _location = role_data[0].get("country") or ''
            
            team_member_entry = {
                "member_name": resource_name,
                "member_email": _email,
                "project_id": project_id,
                "member_role": _role,
                "member_utilization": data.get("allocation") or 0,
                "location": _location,
                "average_spend": 0,
                "is_external": False,
                "resource_id": resource_id,
                "start_date": project_start_date,
                "end_date": project_end_date,
            }
            print("--debug team_member_entry----", team_member_entry)
            msg = ''
            if check_res:
                # If a record exists, update it
                update_query = f"""
                    UPDATE public.capacity_resource_timeline
                    SET {', '.join([f"{field} = %s" for field in fields[1:]])}
                    WHERE id = {check_res[0]['id']}
                """
                db_instance.executeSQLQuery(update_query, values[1:])
                
                BaseInsightsProcessorClass().createProjectEntryInDB(team_member_entry, tenant_id=tenant_id, user_id=user_id, project_id=project_id, entryType="project_teamsplit")
                msg = f"✅ {resource_name} allocation has been updated assigned to project '{project_name}'.\n\n"
            else:
                query = f"""
                    INSERT INTO public.capacity_resource_timeline ({', '.join(fields)})
                    VALUES ({', '.join(placeholders)})
                    RETURNING id;
                """
                db_instance.executeSQLQuery(query, values)
                BaseInsightsProcessorClass().createProjectEntryInDB(team_member_entry, tenant_id=tenant_id, user_id=user_id, project_id=project_id, entryType="project_teamsplit")
                msg = f"✅ {resource_name} has been successfully assigned to project '{project_name}'.\n\n"

            print(f"Assigned resource ID {resource_id} to project ID {project_id}: {data}")

            # response = {
            #     "resource_id": resource_id,
            #     "project_id": project_id,
            #     "status": "success",
            #     "message": f"✅ {resource_name} has been successfully assigned to project '{project_name}'."
            # }
            # responses.append(response["message"])
            responses.append(msg)
            socketio.emit('potential_agent',{"event": "info_updated","resource_id":resource_id},room=client_id)

        print("\n\n--debug responses------",responses)
        return responses

    except Exception as e:
        # sender.sendError(key=f"Error in allocate_resources: {e}", function="potential:allocate_resources")
        appLogger.error({"event": "Resource assignment failed", "error": str(e), "traceback": traceback.format_exc()})
        return "Something went off, please retry!"
    
    
    


####V1:
    # # Get resource IDs
        # target_to_id = {}
        # valid_assignments = []
        # clarification_needed = []
        # for target in resource_targets:
           
        #     check_query = f"""
        #         SELECT id, first_name, last_name
        #         FROM public.capacity_resource
        #         WHERE (first_name ILIKE '%{target}%' OR last_name ILIKE '%{target}%' OR (first_name || ' ' || last_name) ILIKE '%{target}%')
        #         AND tenant_id = {tenant_id};
        #     """
        #     # patterns = [f"'%{target}%'"] * 4 + [tenant_id]
        #     matched = db_instance.retrieveSQLQueryOld(check_query)
            
        #     if len(matched) > 1:
        #         clarification_needed.extend([{"id": row['id'], "name": f"{row['first_name']} {row['last_name']}"} for row in matched])
        #     elif matched:
        #         target_to_id[target] = matched[0]['id']
        #         resource_name = matched[0]['first_name'] + ' ' + matched[0]['last_name']
        #         valid_assignments.append((matched[0]['id'], target, resource_name))

        # print("clarification_needed,target_to_id", clarification_needed, target_to_id)

        # # If clarification is needed for resources, send options
        # if clarification_needed:
        #     clarification_msg = json.dumps({
        #         "error": "Multiple resources matched",
        #         "options": clarification_needed,
        #         "message": f"Multiple resources found for targets: {', '.join([t for t in resource_targets if not t.startswith('ID:')])} Please specify which to assign."
        #     })
        #     print(f"Multiple resource matches found: {clarification_needed}")
        #     # if socketio and client_id:
        #     #     socketio.emit("agent_chat_user", clarification_msg, room=client_id)
        #     TangoDao.insertTangoState(
        #         tenant_id=tenant_id,
        #         user_id=user_id,
        #         key=f"clarification_{session_id}",
        #         value=json.dumps({"options": clarification_needed}),
        #         session_id=session_id
        #     )
        #     return [json.dumps(f"Multiple resources found for targets: {', '.join([t for t in resource_targets if not t.startswith('ID:')])} Please specify which to assign.")]

        # print("\n\n---debug valid_resource_ids---------", [vid[0] for vid in valid_assignments])

        # if not valid_assignments:
        #     error_msg = f"No matching resources found for targets: {resource_targets}"
        #     print("--debug error in allocate_resources:", error_msg)
        #     return error_msg



def save_resources(assign_data):
    try:
        
         # api_payload = {
        #     "tenant_id": tenant_id,
        #     "user_id": user_id,
        #     "resource_ids": [data["resource_id"]],
        #     "project_id": data["project_id"],
        #     "allocation": data.get("allocation"),
        #     "start_date": data.get("start_date"),
        #     "end_date": data.get("end_date")
        # }
        print("--debug [Django Backend URL]-----", os.getenv("DJANGO_BACKEND_URL"))
        
        allocate_url = os.getenv("DJANGO_BACKEND_URL") + "api/capacity/allocate_resource_to_project_from_tango"
        print("--debug allocate_url----", allocate_url)
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.post(allocate_url, headers=headers, json=assign_data, timeout=4)
        print("\n\n---debug response----------", response.content,'\n')
        
        # b'{"status":"success","statusCode":200,"message":"Provider Profile saved successfully"}'
        # result = json.loads(response.content)
        # print("content", result)
        # print(response.raw, response.content,response.encoding, response.headers, response.history, response.reason)
        # print("\n\nStatus Code:", response.status_code)
        # print("Response Content:", response.text)
        
        result = {"status_code": response.status_code, "message": response.text}
        return result
    except Exception as e:
        print("--debug error in save_quantum_canvas", str(e))
        appLogger.error({"event": "save_quantum_canvas", "error": str(e), "traceback": traceback.format_exc()})
        return {"status": "error", "response": str(e)}