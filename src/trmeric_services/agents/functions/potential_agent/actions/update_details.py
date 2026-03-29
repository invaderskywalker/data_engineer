import re
import json
import traceback
from datetime import datetime
from typing import List, Dict, Any
from src.trmeric_database.dao import TenantDaoV2
from src.trmeric_database.Database import db_instance
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_services.agents.functions.potential_agent.prompts import  update_details_prompt_v2
from src.trmeric_services.agents.functions.potential_agent.utils import restrict_check,find_best_resource_match,register_action


@register_action("update_resource_data")
def action_update_resource_data(tenantID: int, userID: int, llm, last_user_message, plan,socketio, client_id, sessionID, context_string, **kwargs):
    resource_data, clarification_msg = update_details(
        tenant_id=tenantID,
        user_id=userID,
        session_id=sessionID,
        llm=llm,
        user_query=last_user_message,
        socketio=socketio,
        client_id=client_id,
        context_string=context_string,
        plan=plan,
        **kwargs
    )

    if clarification_msg is not None:
        yield clarification_msg
        return

    if not resource_data:
        yield "Couldn't update details"
        return

    for response in update_resource_details_fn(
        tenant_id=tenantID,
        user_id=userID,
        resource_data=resource_data,
        socketio=socketio,
        client_id=client_id,
        session_id=sessionID,
        llm=llm,
        **kwargs
    ):
        yield response


def update_details(
    tenant_id: int,
    user_id: int,
    session_id: str,
    llm: Any,
    user_query: str,
    socketio: Any = None,
    client_id: str = None,
    context_string = None,
    plan = None,
    **kwargs
):
    """Extract resource targets and updates from user query and return resource_data."""
    sender = kwargs.get("step_sender")
    model_opts = kwargs.get("model_opts2")
    conversation = kwargs.get("conversation",[]) or []
    portfolio_info = kwargs.get("portfolio_info",[])

    # print("\n\n----debug plan ------------------------------1", plan,"\n, portosflilo info----", portfolio_info)
    try:
        
        formatted_conversation = conversation
        update_params = plan.get("update_resource_params") or []
        print("--debug update pasrsr", update_params)

        portfolio_names = [p.get('portfolio') for p in update_params if p.get('portfolio') is not None]
        # portfolio = update_params.get("portfolio",None) or None

        portfolio_ids = []
        normalize = lambda s: re.sub(r'\s+', ' ', re.sub(r'[&/-]', ' ', s or "").strip().lower().replace("portfolio", ""))
        for portfolio in portfolio_names:
            portfolio_name = (portfolio or "").strip().lower() or None
            if portfolio_name:
                # all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(tenant_id=tenantID)
                # print("--debug portfolio info----------", all_portfolios)
                portfolio_rev_map = {p.get('title','').strip().lower(): p['id'] for p in portfolio_info}
                print("--debug portfolio_rev_map-------", portfolio_rev_map)

                normalized_name = normalize(portfolio_name)
                if normalized_name in portfolio_rev_map:
                    portfolio_id = portfolio_rev_map[normalized_name]
                
                    if portfolio_id:  # ensure it's not None or empty
                        portfolio_ids.append(int(portfolio_id))  # ensure it's int
        print("--debug portfolio_ids------", portfolio_ids)


        resource_data = TenantDaoV2.fetchResourceDataWithProjectionAttrs(
            tenant_id=tenant_id,
            projection_attrs=["id","first_name","last_name","role","experience_in","experience_years",
                "primary_skill","skills","is_external","availability_time","current_allocation",
                "past_projects","current_projects","future_projects","org_team","portfolio",
                "provider_company_name","provider_company_address","provider_company_website"
            ],
            portfolio_ids = portfolio_ids if len(portfolio_ids)>0 else None
        )

        resources_in_context = []
        for data in update_params:
            name = data.get('name', '').strip().lower() if data.get('name') else None
            
            # # Try to find exact or close match
            # for r in resource_data:
            #     full_name = f"{r.get('first_name','')} {r.get('last_name','')}".strip().lower()
            #     if name in full_name or full_name in name:
            #         resources_in_context.append(r)
            rmatch = find_best_resource_match(name, resource_data)
            print("--debug match------", name, "→", rmatch)
            if rmatch:
                resources_in_context.append(rmatch)

        print("\n\n--debug resources_in_context-------", resources_in_context)

        if not resources_in_context:
            return None, f"Couldn't find the resource details to update! Can you name them?"

        context_string += f"""
            These are all the details of the resources whose details to be updated by the user
            ----------------------
            Resources data: {json.dumps(resources_in_context,indent=2)}
        """
        prompt = update_details_prompt_v2(user_query=user_query, conversation=formatted_conversation, context_string=context_string)

        response = llm.run(prompt,model_opts,"agent::potential::extract_resources",
            {"tenant_id": tenant_id, "user_id": user_id},
            socketio=socketio,client_id=client_id
        )
        extract_output = extract_json_after_llm(response, step_sender=sender)
        # print("\n\n--debug update_details_promptres---", extract_output)

        clarifying_info = extract_output.get("clarifying_info", "")

        # Handle clarification case
        if clarifying_info:
            print(f"Clarifying information extracted: {clarifying_info}")
            return None, clarifying_info
        
        resources_to_modify = extract_output.get("resources_to_modify") or []
        # print("--debug resources_to_modify---", resources_to_modify)

        # Check for valid resource targets
        if not resources_to_modify:
            error_msg = "⚠️ No resource targets identified in the query. Please specify which resources to update."
            return None, error_msg


        resource_data = []
        for target in resources_to_modify:
            resource_id = target.get("resource_id")
            fields_to_update = target.get("fields_to_update")
            resource_data.append({
                "id": resource_id,
                "name": target.get("resource_name"),
                **fields_to_update
            })
            
        # resource_data = [{"id": rid, "name": target, **extracted_updates} for rid, target in valid_ids]
        print("--debug resource_data--------", resource_data)
        return resource_data, None
            
    except Exception as e:
        error_msg = f"❌ Update failed in update_details: {str(e)}"
        sender.sendError(key=error_msg, function="potential::update_details")
        appLogger.error({"event": "Update details failed", "error": str(e), "traceback": traceback.format_exc()})
        return None, error_msg





def update_resource_details_fn(
    tenant_id: int,
    user_id: int,
    resource_data: List[Dict[str, Any]],
    socketio: Any = None,
    client_id: str = None,
    llm =None,
    **kwargs
) -> List[str]:
    """Update resource details in capacity_resource and capacity_resource_timeline tables
    """
    try:
        print("--debug update_resource_details_fn data-------", resource_data)
        sender = kwargs.get("step_sender") or None
        print(f"Updating resource details for tenant_id: {tenant_id}, {len(resource_data)} resources")

        responses = []
        resource_data = restrict_check(user_id = user_id,tenant_id=tenant_id,resource_data=resource_data,responses = responses, type='details')
        print("\n--debug resource_data after----------2", resource_data)

        # Valid fields for capacity_resource table based on schema
        resource_fields = [
            'first_name', 'last_name', 'country', 'email', 'role', 'skills', 'allocation',
            'experience_years', 'experience', 'projects', 'is_active', 'is_external',
            'trmeric_provider_tenant_id', 'external_provider_id', 'availability_time',
            'location', 'rate', 'primary_skill'
        ]

        # Valid fields for capacity_resource_timeline table
        # timeline_fields = ['start_date', 'end_date', 'allocation', 'project_name', 'trmeric_project_id']

        ##Anonymize first & last names if in resource_data
        for data in resource_data:
            if data.get("first_name"):
                original_first = data.pop("first_name",None)
                data["first_name"] = db_instance.encrypt_text_to_base64(original_first)

            if data.get("last_name"):
                original_last = data.pop("last_name",None)
                data["last_name"] = db_instance.encrypt_text_to_base64(original_last)

        # print("\n\n--debug resource_data-------------3 ", resource_data)

        for data in resource_data:
            # Validate required fields
            if 'id' not in data:
                error_msg = f"Missing resource_id in data: {data}"
                if sender:
                    sender.sendError(key=error_msg, function="update_resource_details_fn")
                appLogger.error({"event": "Resource update failed", "error": error_msg})
                responses.append(f'{{"resource_id": null, "status": "error", "message": "{error_msg}"}}')
                continue

            resource_id = data['id']
            resource_name =data['name']
            print(f"Processing resource ID {resource_id} and name {resource_name}")
            
            # Separate resource and timeline updates
            resource_updates = {k: v for k, v in data.items() if k in resource_fields and k != 'id'}
            print("\n\n---debug resource_updates----",resource_updates)
            # timeline_updates = {k: v for k, v in data.items() if k in timeline_fields}

            # sender.sendSteps(key=f"Updating Resource {resource_name}", val=False)
            # Validate and process resource updates
            if resource_updates:
                # Handle specific validations (e.g., date formats, allocation range)
                if 'allocation' in resource_updates:
                    try:
                        alloc = int(resource_updates['allocation'])
                        if not 0 <= alloc <= 100:
                            error_msg = f"⚠️ Invalid allocation for {resource_name}: {alloc}. Allocation must be between 0 and 100."

                            if sender:
                                sender.sendError(key=error_msg, function="update_resource_details_fn")
                            appLogger.error({"event": "Resource update failed", "error": error_msg})
                            responses.append(f'{{"resource_id": {resource_id}, "status": "error", "message": "{error_msg}"}}')
                            continue
                    except (ValueError, TypeError):
                        error_msg = f"Invalid allocation format for resource_id {resource_id}: {resource_updates['allocation']}"
                        if sender:
                            sender.sendError(key=error_msg, function="update_resource_details_fn")
                        appLogger.error({"event": "Resource update failed", "error": error_msg})
                        responses.append(f'{{"resource_id": {resource_id}, "status": "error", "message": "{error_msg}"}}')
                        continue

                # Build dynamic SQL for resource updates
                set_clause = ', '.join([f"{k} = %s" for k in resource_updates.keys()])
                params = list(resource_updates.values()) + [user_id, resource_id, tenant_id]
                update_query = f"""
                    UPDATE public.capacity_resource
                    SET {set_clause}, updated_by_id = %s, updated_on = CURRENT_TIMESTAMP
                    WHERE id = %s AND tenant_id = %s;
                """
                
                print("\n\n---deubg resource_update_query------", update_query)
                
                db_instance.executeSQLQuery(update_query, params)
                print(f"Updated resource ID {resource_id}: {resource_updates}")

            
            # Emit success event via SocketIO
            print("--debug updating resource id", resource_id, resource_name)
            # sender.sendSteps(key=f"Updating Resource {resource_name}", val=True)
            responses.append(f"✅ {resource_name}'s details updated successfully.\n\n")
            socketio.emit('potential_agent',{"event": "info_updated","resource_id":resource_id},room=client_id)

        print("\n--debug update_details responses------", responses)
        return responses

    except Exception as e:
        error_msg = f"Error updating resources: {str(e)}"
        sender.sendError(key=error_msg, function="update_resource_details_fn")
        appLogger.error({"event": "Resource update/insert failed", "error": str(e), "traceback": traceback.format_exc()})
        return "Something went off, please retry!"
    
    
    
####First version Saphal without LLM:
        # # Resolve targets to resource IDs
        # valid_ids = []
        # clarification_needed = []    
    
    
# if target.startswith("ID:"):
            #     try:
            #         rid = int(target.split(":")[1])
            #         check_query = f"SELECT id FROM public.capacity_resource WHERE id = {rid} AND tenant_id = {tenant_id};"
            #         if db_instance.retrieveSQLQueryOld(check_query):
            #             valid_ids.append((rid, target))
            #     except ValueError:
            #         continue
            # else:
            #     # Assume name (use stricter query from August 20, 2025)
            #     check_query = f"""
            #         SELECT DISTINCT id, first_name, last_name
            #         FROM public.capacity_resource
            #         WHERE (first_name ILIKE '{target}%' OR (first_name || ' ' || last_name) ILIKE '{target} %')
            #         AND tenant_id = {tenant_id};
            #     """
            #     matched = db_instance.retrieveSQLQueryOld(check_query)
                
            #     if len(matched) > 1:
            #         # Collect matches for clarification
            #         clarification_needed.extend([{"id": row['id'], "name": f"{row['first_name']} {row['last_name']}", "updates": extracted_updates} for row in matched])
            #     elif matched:
            #         valid_ids.append((matched[0]['id'], target))

        # # If clarification is needed for any target, send all matches
        # if clarification_needed:
        #     clarification_msg = {
        #         "error": "Multiple resources matched",
        #         "options": clarification_needed,
        #         "message": f"Multiple resources found for targets: {', '.join([t['name'] for t in clarification_needed])} Please specify which to update."
        #     }
        #     print(f"Multiple matches found: {clarification_needed}")
        #     TangoDao.insertTangoState(
        #         tenant_id=tenant_id,
        #         user_id=user_id,
        #         key=f"clarification_{session_id}",
        #         value=json.dumps(clarification_needed),
        #         session_id=session_id
        #     )
        #     print("--debug message-----", clarification_msg["message"])
        #     return None, clarification_msg["message"]

        # print("\n\n---debug valid_ids---------", [vid[0] for vid in valid_ids])
        
        # if not valid_ids:
        #     error_msg = f"No matching resources found for targets: {resource_targets}"
        #     return None, error_msg

        # # Build resource_data with validated IDs, names, and updates
        # resource_data = [{"id": rid, "name": target, **extracted_updates} for rid, target in valid_ids]
        # print("--debug resource_data--------", resource_data)
        # return resource_data, None


##More strict filtering sql
# ultiple matches found: [{'id': 628, 'name': 'Ram Smith', 'updates': {'Ram': {'role': 'AI engineer'}, 'Shyam': {'location': 'China'}}}, 
# {'id': 632, 'name': 'Benjamin Ramirez', 'updates': {'Ram': {'role': 'AI engineer'}, 'Shyam': {'location': 'China'}}},
# {'id': 630, 'name': 'Ram\n Johnson', 'updates': {'Ram': {'role': 'AI engineer'}, 'Shyam': {'location': 'China'}}}, {'id': 947, 'name': 'Benjamin Ramirez', 'updates': {'Ram': {'role': 'AI engineer'}, 'Shyam': {'location': 'China'}}}, {'id': 1045, 'name': 'Ethan Ramirez', 'updates': {'Ram': {'role': 'AI engineer'}, 'Shyam': {'location': 'China'}}}, {'id': 730, 'name': 'Ethan Ramirez', 'updates': {'Ram': {'role': 'AI engineer'}, 'Shyam': {'location': 'China'}}}]
# Tango state created successfully  clarification_0ab6c5aa-7332-4c0a-9141-0c8152fd9a96
    
# # Validate and process timeline updates
            # if len(timeline_updates.keys())>1:
            #     # Validate timeline-specific fields (e.g., dates)
            #     if 'start_date' in timeline_updates or 'end_date' in timeline_updates:
            #         try:
            #             start_date = timeline_updates.get('start_date')
            #             end_date = timeline_updates.get('end_date')
            #             if start_date:
            #                 datetime.strptime(start_date, "%Y-%m-%d")
            #             if end_date:
            #                 datetime.strptime(end_date, "%Y-%m-%d")
            #             if start_date and end_date and datetime.strptime(end_date, "%Y-%m-%d") < datetime.strptime(start_date, "%Y-%m-%d"):
            #                 error_msg = f"end_date must be after start_date for resource_id {resource_id}"
            #                 if sender:
            #                     sender.sendError(key=error_msg, function="update_resource_details_fn")
            #                 appLogger.error({"event": "Timeline update failed", "error": error_msg})
            #                 responses.append(f'{{"resource_id": {resource_id}, "status": "error", "message": "{error_msg}"}}')
            #                 continue
            #         except ValueError as ve:
            #             error_msg = f"Invalid date format for resource_id {resource_id}: start_date={start_date}, end_date={end_date}"
            #             if sender:
            #                 sender.sendError(key=error_msg, function="update_resource_details_fn")
            #             appLogger.error({"event": "Timeline update failed", "error": error_msg})
            #             responses.append(f'{{"resource_id": {resource_id}, "status": "error", "message": "{error_msg}"}}')
            #             continue

            #     # Check if a timeline record exists for this resource
            #     check_query = """
            #         SELECT id FROM public.capacity_resource_timeline
            #         WHERE resource_id = %s AND tenant_id = %s AND project_name = %s;
            #     """
            #     project_name = timeline_updates.get('project_name')
            #     params = (resource_id, tenant_id, project_name) if project_name else (resource_id, tenant_id, None)
            #     existing_timeline = db_instance.retrieveSQLQueryOld(check_query, params)

            #     if existing_timeline:
            #         # Update existing timeline
            #         set_clause = ', '.join([f"{k} = %s" for k in timeline_updates.keys()])
            #         params = list(timeline_updates.values()) + [user_id, existing_timeline[0][0], tenant_id]
            #         update_timeline_query = f"""
            #             UPDATE public.capacity_resource_timeline
            #             SET {set_clause}, updated_by_id = %s, updated_on = CURRENT_TIMESTAMP
            #             WHERE id = %s AND tenant_id = %s;
            #         """
            #         db_instance.executeSQLQuery(update_timeline_query, params)
            #         print(f"Updated timeline for resource ID {resource_id}: {timeline_updates}")
            #     else:
            #         # Insert new timeline record
            #         fields = ['resource_id', 'tenant_id', 'created_by_id', 'created_on'] + list(timeline_updates.keys())
            #         placeholders = ', '.join(['%s'] * len(fields))
            #         field_names = ', '.join(fields)
            #         params = [resource_id, tenant_id, user_id, 'CURRENT_TIMESTAMP'] + list(timeline_updates.values())
            #         insert_timeline_query = f"""
            #             INSERT INTO public.capacity_resource_timeline ({field_names})
            #             VALUES ({placeholders});
            #         """
            #         print("--debug timeline query-----", insert_timeline_query)
                    
            #         db_instance.executeSQLQuery(insert_timeline_query, params)
            #         print(f"Inserted new timeline for resource ID {resource_id}: {timeline_updates}")
