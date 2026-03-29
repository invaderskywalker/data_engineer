import os
import json
import datetime
from datetime import timedelta
import traceback
from src.trmeric_database.dao import TangoDao,TenantDaoV2
from src.trmeric_database.Database import db_instance
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_services.agents.functions.potential_agent.prompts import  allocate_demands_prompt_v1
from src.trmeric_services.agents.functions.potential_agent.utils import restrict_check,find_best_resource_match,register_action
# from rapidfuzz import process, fuzz


"""
    Roadmap and demand are synonymous here. they refer to future planned projects.
    Analysing the user query and the conversation user may say I wish to assign demand/project to a resource.then the first understanding llm
    similar to update_details_prompt will ask clarifying info like which resource we are talking about and tell me the demands(s).
    
    Then user will say the name of the roadmaps and resources and accordingly it should get all those in assign_data  List[Dict[str, Any]] (like resource_data)
    if resource has mentioned a demand/roadmap name then you will get the roadmap ids from roadmap_roadmap table in trmeric db.
    query: select id,title from roadmap_roadmap where title ilike '%{roadmap_name}%'
    If multiple roadmaps are matching then ask user which ones to go with
    
  
    you need to prepare a nice mapping of resource_ids and the roadmaps they will be assigned to as per the user query    
"""
@register_action("assign_to_demand")
def allocate_demands(
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
    Assign resources to demands/roadmaps based on user query.
    Demands = Roadmap entries (future planned work).
    Uses the same pattern as allocate_resources but targets roadmap_roadmap table
    and inserts into capacity_resource_timeline with trmeric_roadmap_id.
    """
    user_id = userID
    tenant_id = tenantID
    sender = kwargs.get("step_sender")
    model_opts = kwargs.get("model_opts2")
    conversation = kwargs.get("conversation", []) or []
    print("\n\n----debug conversation in allocate_demands -----", conversation)

    print("--debug in allocate_demands ---", user_query, session_id, user_id, tenant_id)

    try:
        formatted_conversation = conversation
        # full_context = context_string or ""
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
            # name = data.get('name', '').strip().lower()
            
            # # Try to find exact or close match
            # for r in resource_data:
            #     full_name = f"{r.get('first_name','')} {r.get('last_name','')}".strip().lower()
            #     if name in full_name or full_name in name:
            #         resources_in_context.append(r)

            target_name = data.get("resource_name", "").strip()
            rmatch = find_best_resource_match(target_name, resource_data)
            print("--debug match------", target_name, "→", rmatch)
            if rmatch:
                resources_in_context.append(rmatch)


        print("\n\n--debug resources_in_context-------", resources_in_context,"\nLength: ",len(resources_in_context))
        context_string += f"""
            These are all the details of the resources to whom projects is to be allocated.
            ----------------------
            Resources data: {json.dumps(resources_in_context,indent=2)}
        """
        full_context = context_string or ""
        # print("\n\n--debug full_context---------", full_context)


        # Prompt to extract demand assignments
        prompt = allocate_demands_prompt_v1(   # You'll create this similar to allocate_resources_prompt_v2
            user_query=user_query,
            conversation=formatted_conversation,
            context_string=full_context
        )

        response = llm.run(prompt, model_opts, "agent::potential::extract_demand_assignments",
            {"tenant_id": tenant_id, "user_id": user_id},socketio=socketio, client_id=client_id
        )

        extract_output = extract_json_after_llm(response, step_sender=sender)
        print("\n\n--debug allocate_demands LLM output---", extract_output)

        clarifying_info = extract_output.get("clarifying_info", "")
        assign_demand_to_resource = extract_output.get("assign_demand_to_resources") or []

        # Handle clarification
        if clarifying_info:
            print(f"Clarification needed: {clarifying_info}")
            TangoDao.insertTangoState(
                tenant_id=tenant_id,
                user_id=user_id,
                key=f"clarification_{session_id}",
                value=json.dumps({"conversation": user_query, "clarification": clarifying_info}),
                session_id=session_id
            )
            return clarifying_info

        if not assign_demand_to_resource:
            return "⚠️ No valid demand assignments were identified in your request."

        assign_data = []
        roadmap_clarification_needed = []

        #Assigning a demand to resoruce from today's date to next 1 week
        for item in assign_demand_to_resource:
            resource_name = item.get("resource_name")
            resource_id = item.get("resource_id")
            # roadmap_title = item.get("roadmap_title") or item.get("demand_name") or item.get("roadmap_name")
            roadmap_id = item.get("roadmap_id")
            allocation = item.get("allocation", 0) or 0

            if not resource_id or not roadmap_id:
                return f"⚠️ Missing resource or roadmap in assignment. Please provide both values to proceed."

            # Resolve roadmap_title → roadmap_id (fuzzy match)
            roadmap_query = f"""
                SELECT id, title FROM roadmap_roadmap 
                WHERE id = {roadmap_id} AND tenant_id = {tenant_id}
            """
            roadmap_res = db_instance.retrieveSQLQueryOld(roadmap_query)
            print("--debug roamdap_res---------", roadmap_res)
            roadmap_title = roadmap_res[0].get("title","") or None
            # roadmap_start = roadmap_res[0].get("start_date",None) or None
            # roadmap_end = roadmap_res[0].get("end_date",None) or None

            # Validate allocation
            try:
                alloc = int(allocation)
                if not 0 <= alloc <= 100:
                    return f"⚠️ Invalid allocation {alloc}% for resource {resource_name}. Allocation must be between 0 and 100."

            except (ValueError, TypeError):
                return f"Invalid allocation format: {allocation}"

            assign_entry = {
                "id": resource_id,
                "name": resource_name,
                "roadmap_id": roadmap_id,
                "roadmap_title": roadmap_title,
                "start_date": datetime.datetime.today().date().isoformat(),
                "end_date":   (datetime.datetime.today().date() + timedelta(days=7)).isoformat(),
                "allocation": alloc
            }
            assign_data.append(assign_entry)

        # Clarification if multiple or zero matches
        if roadmap_clarification_needed:
            unique_titles = list(set(roadmap_clarification_needed))
            return (
                f"I found multiple or no matching roadmaps for: {', '.join(unique_titles)}. ""Please specify the exact roadmap title(s) you want to assign.")

        # Restrict check (same as project version)
        responses = []
        assign_data = restrict_check(user_id=user_id,tenant_id=tenant_id,resource_data=assign_data,responses=responses)
        print("\n-------debug assigna data demand-------", assign_data)

        # Insert/Update into capacity_resource_timeline using trmeric_roadmap_id
       
       
        for data in assign_data:
            # print("--debug data-------", data)
            resource_id = data["id"]
            resource_name = data["name"]
            roadmap_id = data["roadmap_id"]
            roadmap_title = data["roadmap_title"]
            allocation = data.get("allocation", 0) or 0
            start_date = data.get("start_date")
            end_date = data.get("end_date")

            # Check if assignment already exists
            check_query = f"""
                SELECT id FROM public.capacity_resource_timeline
                WHERE resource_id = {resource_id} AND trmeric_roadmap_id = {roadmap_id}
            """
            existing = db_instance.retrieveSQLQueryOld(check_query)

            fields = ["resource_id", "trmeric_roadmap_id","roadmap_name", "tenant_id", "created_by_id","created_on"]
            values = [resource_id, roadmap_id,roadmap_title, tenant_id, user_id, datetime.datetime.now()]
            placeholders = ["%s"] * len(fields)

            optional_fields = ["start_date", "end_date", "allocation"]
            for key in optional_fields:
                val = data.get(key)
                if val is not None:
                    fields.append(key)
                    values.append(val)
                    placeholders.append("%s")

            msg = ''
            if existing:
                # Update
                update_query = f"""
                    UPDATE public.capacity_resource_timeline
                    SET {', '.join(f"{f} = %s" for f in fields[1:])}
                    WHERE id = %s
                """
                db_instance.executeSQLQuery(update_query, values[1:] + [existing[0]["id"]])
                msg = f"✅ {resource_name} information has been updated in demand '{roadmap_title}'.\n\n"

            else:
                # Insert
                insert_query = f"""
                    INSERT INTO public.capacity_resource_timeline ({', '.join(fields)})
                    VALUES ({', '.join(placeholders)})
                    RETURNING id;
                """
                db_instance.executeSQLQuery(insert_query, values)
                msg = f"✅ {resource_name} has been successfully assigned to demand '{roadmap_title}'.\n\n"

            responses.append(msg)
            socketio.emit('potential_agent', {"event": "info_updated","resource_id": resource_id}, room=client_id)

        return responses

    except Exception as e:
        appLogger.error({"event": "Demand assignment failed","error": str(e),"traceback": traceback.format_exc()})
        return "Something went wrong while assigning demands. Please try again."




# def find_best_resource_match(target_name: str, resource_data: list, cutoff: int = 80):
#     """
#     Safely fuzzy-match a human name against resource_data.
#     Returns the best matching resource dict or None.
#     """

#     if not target_name:
#         return None

#     target_name = target_name.strip()

#     # Build clean name list + parallel resource index
#     choices = []
#     valid_resources = []

#     for r in resource_data:
#         fn = (r.get("first_name") or "").strip()
#         ln = (r.get("last_name") or "").strip()
#         full = f"{fn} {ln}".strip()

#         if full:  # skip empty / None
#             choices.append(full)
#             valid_resources.append(r)

#     if not choices:
#         return None

#     # Fuzzy match (list-based → never crashes)
#     match = process.extractOne(target_name, choices, scorer=fuzz.WRatio, score_cutoff=cutoff)

#     if not match:
#         return None

#     best_name = match[0]
#     idx = choices.index(best_name)

#     return valid_resources[idx]






###fuzz approach for name matching
# import re
# from thefuzz import fuzz, process  # pip install thefuzz[speedup]  (or use rapidfuzz)

# def find_best_resource_matches(target_name: str, resource_data: list, threshold: int = 85):
#     """
#     Accurately match a name from user input to the actual resource.
#     Returns list of matches sorted by confidence (usually 0 or 1 result)
#     """
#     if not target_name or not resource_data:
#         return []

#     target = target_name.strip().lower()

#     # Pre-process once: create list of (resource, searchable_strings)
#     candidates = []
#     for r in resource_data:
#         first = (r.get('first_name') or '').strip()
#         last = (r.get('last_name') or '').strip()
#         full = f"{first} {last}".strip()
#         full_rev = f"{last} {first}".strip()
#         email = (r.get('email') or '').split('@')[0].replace('.', ' ').lower()

#         candidates.append({
#             'resource': r,
#             'searchable': [
#                 full.lower(),
#                 full_rev.lower(),
#                 first.lower(),
#                 last.lower(),
#                 email,
#                 f"{first.lower()}{last.lower()}",  # mohithguijula
#                 f"{last.lower()}{first.lower()}",
#             ]
#         })

#     # 1. Try exact match first
#     for cand in candidates:
#         if target in cand['searchable'] or any(target == s for s in cand['searchable']):
#             return [cand['resource']]

#     # 2. Fuzzy match with high threshold
#     choices = [(c['resource'], c['searchable'][0]) for c in candidates]  # use full name as primary key
#     best_matches = process.extract(target, dict(choices), scorer=fuzz.token_set_ratio, limit=10)

#     # Filter only very good matches
#     strong_matches = [resource for resource, score, _ in best_matches if score >= threshold]

#     if strong_matches:
#         # Sort by score descending
#         strong_matches.sort(
#             key=lambda r: max(
#                 fuzz.token_set_ratio(target, s) for s in next(c['searchable'] for c in candidates if c['resource'] == r)
#             ),
#             reverse=True
#         )
#         return strong_matches

#     # 3. Fallback: partial token match with strict rules
#     target_tokens = set(re.split(r'\W+', target))
#     if len(target_tokens) > 1:
#         for cand in candidates:
#             for searchable in cand['searchable']:
#                 cand_tokens = set(re.split(r'\W+', searchable))
#                 if target_tokens.issubset(cand_tokens) or cand_tokens.issubset(target_tokens):
#                     return [cand['resource']]

#     return []  # no confident match