import json
import datetime
import traceback
from datetime import timedelta
from rapidfuzz import process, fuzz
from src.trmeric_database.Database import db_instance
from src.trmeric_database.dao import TangoDao,TenantDaoV2
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_services.agents.functions.potential_agent.utils import register_action, find_best_resource_match
from src.trmeric_services.agents.functions.potential_agent.prompts import  unassign_resources_prompt


"""
    user will say to remove or unassign projects / roadmaps which they're already allocated to.
    it willl check here if it exists and then delete from db.
    you need to prepare a nice mapping of resource_ids and the roadmaps/projects they will be removed to as per the user query    
"""
@register_action("unassign_demand_or_project")
def unassign_resources(
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
    Unassign or remove resources to demands/projects/roadmaps based on user query.
    Demands = Roadmap entries (future planned work).
    Uses the same pattern as allocate_resources but targets roadmap_roadmap table
    and inserts into capacity_resource_timeline with trmeric_roadmap_id.
    """
    user_id = userID
    tenant_id = tenantID
    sender = kwargs.get("step_sender")
    model_opts = kwargs.get("model_opts2")
    conversation = kwargs.get("conversation", []) or []
    # print("\n\n----debug conversation in unassign_resources -----", conversation)

    resources =kwargs.get("resources_info") or []
    projects =kwargs.get("projects_info") or []
    roadmaps =kwargs.get("roadmap_info") or []

    print("--debug in unassign_resources ---", projects[:5],"\n roadmaps: ", roadmaps[:4])

    try:
        formatted_conversation = conversation
        full_context = context_string or ""
        unassign_params = plan.get('unassign_params',[]) or []
        print("--debug unassign params--------", unassign_params)

        resource_data = TenantDaoV2.fetchResourceDataWithProjectionAttrs(
            tenant_id=tenant_id,
            projection_attrs=["id","first_name","last_name",
                "current_allocation","past_projects","current_projects","future_projects","all_roadmaps",
                "org_team","portfolio",
            ]
        )

        #  Lookup maps
        project_id_to_title = {int(p["project_id"]): p["project_title"] for p in projects}
        roadmap_id_to_title = {int(r["roadmap_id"]): r["roadmap_title"] for r in roadmaps}
        # print("\n\n--dbug roadmap_id_to_title-------", roadmap_id_to_title)

        resources_in_context = []
        for data in unassign_params:
            target_name = data.get("resource_name", "").strip()
            rmatch = find_best_resource_match(target_name, resource_data)
            print("--debug match------", target_name, "→", rmatch)
            if rmatch:
                resources_in_context.append(rmatch)


        print("\n\n--debug resources_in_context-------", resources_in_context,"\nLength: ",len(resources_in_context))
        context_string += f"""
            These are all the details of the resources on whom unassignment action is to be performed.
            ----------------------
            Resources data: {json.dumps(resources_in_context,indent=2)}
        """
        full_context = context_string or ""
        # print("\n\n--debug full_context---------", full_context)
        
        # Prompt to extract demand assignments
        prompt = unassign_resources_prompt(   
            user_query=user_query,
            conversation=formatted_conversation,
            context_string=full_context
        )

        response = llm.run(prompt, model_opts, "agent::potential::unassignments",
            {"tenant_id": tenant_id, "user_id": user_id},socketio=socketio, client_id=client_id
        )

        extract_output = extract_json_after_llm(response, step_sender=sender)
        print("\n\n--debug allocate_demands LLM output---", extract_output)

        clarifying = extract_output.get("clarifying_info", "")
        if clarifying:
            print("--debug clairgiygind----", clarifying)
            return clarifying

        unassignments = extract_output.get("unassignments", [])
        if not unassignments:
            return "No valid unassignment request found."
        
        # return
        responses = []
        total_removed = 0

        for item in unassignments:
            # print("--debug item------", item)
            resource_id = item["resource_id"]
            resource_name = item["resource_name"]
            want_project_ids = set(item.get("target_project_ids", []))
            want_roadmap_ids = set(item.get("target_roadmap_ids", []))

            # === Step 1: Fetch ALL current assignments for this resource ===
            all_assignments_query = f"""
                SELECT trmeric_project_id, trmeric_roadmap_id
                FROM capacity_resource_timeline
                WHERE resource_id = {resource_id} 
                AND tenant_id = {tenant_id}
                AND (trmeric_project_id IS NOT NULL OR trmeric_roadmap_id IS NOT NULL)
            """
            current = db_instance.retrieveSQLQueryOld(all_assignments_query)
            # print("\n--debug current existing------", current)

            current_projects = {row["trmeric_project_id"] for row in current if row["trmeric_project_id"]}
            current_roadmaps = {row["trmeric_roadmap_id"] for row in current if row["trmeric_roadmap_id"]}
            print("--debug current raodampsf _ projects --------", current_projects, "\n", current_roadmaps)
            # === Step 2: Find what actually exists and should be removed ===
            remove_projects = want_project_ids & current_projects
            remove_roadmaps = want_roadmap_ids & current_roadmaps

            remove_projects_title = [project_id_to_title.get(p) for p in remove_projects]
            remove_roadmaps_title = [roadmap_id_to_title.get(p) for p in remove_roadmaps]

            print("--debug to remove---------", remove_projects,"\n roamdaps------", remove_roadmaps)
            print("\n--debug tiltle remvoe------", remove_projects_title, "\n roadmaf psfstiltel----", remove_roadmaps_title)

            removed_from = []

            if remove_projects:
                db_instance.executeSQLQuery("""
                    DELETE FROM capacity_resource_timeline
                    WHERE resource_id = %s AND tenant_id = %s
                    AND trmeric_project_id = ANY(%s)
                """, (resource_id, tenant_id, list(remove_projects)))
                # removed_from.extend([f"project '{project_id_to_title.get(pid)}'" for pid in remove_projects])
                removed_from.extend(remove_projects_title)
                total_removed += len(remove_projects)

            if remove_roadmaps:
                db_instance.executeSQLQuery("""
                    DELETE FROM capacity_resource_timeline
                    WHERE resource_id = %s AND tenant_id = %s
                    AND trmeric_roadmap_id = ANY(%s)
                """, (resource_id, tenant_id, list(remove_roadmaps)))
                # removed_from.extend([f"roadmap '{roadmap_id_to_title.get(rid)}'" for rid in remove_roadmaps])
                removed_from.extend(remove_roadmaps_title)

                total_removed += len(remove_roadmaps)

            # === Final message ===
            print("--debug removed_from all titles----------", removed_from)
            if removed_from:
                responses.append(f"✅ Removed {resource_name} from {', '.join(removed_from)}.\n")
            else:
                responses.append(f"No active assignments found for {resource_name} to remove.")

            # Real-time update
            socketio.emit('potential_agent', 
                {"event": "info_updated","resource_id": resource_id,"unassigned_count": total_removed}, 
                room=client_id
            )

        final_msg = "\n\n".join(responses)
        return final_msg


    except Exception as e:
        appLogger.error({"event": "unassign_failed", "error": str(e), "traceback": traceback.format_exc()})
        return "Failed to unassign. Please try again."




# def unassign_resources(
#     tenant_id: int,
#     user_id: int,
#     llm=None,
#     plan=None,
#     user_query=None,
#     socketio=None,
#     client_id=None,
#     session_id=None,
#     context_string=None,
#     **kwargs
# ):
#     sender = kwargs.get("step_sender")
#     model_opts = kwargs.get("model_opts2")
#     conversation = kwargs.get("conversation", []) or []

#     try:
#         # === Parse context ===
#         import json
#         try:
#             resources = json.loads(context_string.split("active :")[1].split("All the projects")[0].strip())
#             projects = json.loads(context_string.split("active :")[1].split("All available roadmaps")[0].split("All the projects")[1].strip())
#             roadmaps = json.loads(context_string.split("All available roadmaps of this tenant:")[1].strip())
#         except:
#             resources = projects = roadmaps = []

#         # Lookup maps
#         project_id_to_title = {p["project_id"]: p["project_title"] for p in projects}
#         roadmap_id_to_title = {r["roadmap_id"]: r["roadmap_title"] for r in roadmaps}

#         prompt = unassign_resources_prompt(user_query, "\n".join(conversation[-10:]), context_string)
#         response = llm.run(prompt, model_opts, "agent::potential::unassign", {"tenant_id": tenant_id, "user_id": user_id},
#                            socketio=socketio, client_id=client_id)

#         extract = extract_json_after_llm(response, step_sender=sender)
#         print("--debug unassign extract:", extract)

#         clarifying = extract.get("clarifying_info", "")
#         if clarifying:
#             return clarifying

#         unassignments = extract.get("unassignments", [])
#         if not unassignments:
#             return "No unassignment request found."

#         responses = []
#         total_removed = 0

#         for item in unassignments:
#             resource_id = item["resource_id"]
#             resource_name = item["resource_name"]
#             want_project_ids = set(item.get("target_project_ids", []))
#             want_roadmap_ids = set(item.get("target_roadmap_ids", []))

#             # === Step 1: Fetch ALL current assignments for this resource ===
#             current = db_instance.retrieveSQLQueryOld("""
#                 SELECT trmeric_project_id, trmeric_roadmap_id
#                 FROM capacity_resource_timeline
#                 WHERE resource_id = %s AND tenant_id = %s
#                   AND (trmeric_project_id IS NOT NULL OR trmeric_roadmap_id IS NOT NULL)
#             """, (resource_id, tenant_id))

#             current_projects = {row["trmeric_project_id"] for row in current if row["trmeric_project_id"]}
#             current_roadmaps = {row["trmeric_roadmap_id"] for row in current if row["trmeric_roadmap_id"]}

#             # === Step 2: Find what actually exists and should be removed ===
#             remove_projects = want_project_ids & current_projects
#             remove_roadmaps = want_roadmap_ids & current_roadmaps

#             removed_from = []

#             if remove_projects:
#                 db_instance.executeSQLQuery("""
#                     DELETE FROM capacity_resource_timeline
#                     WHERE resource_id = %s AND tenant_id = %s
#                       AND trmeric_project_id = ANY(%s)
#                 """, (resource_id, tenant_id, list(remove_projects)))
#                 removed_from.extend([f"project '{project_id_to_title.get(pid)}'" for pid in remove_projects])
#                 total_removed += len(remove_projects)

#             if remove_roadmaps:
#                 db_instance.executeSQLQuery("""
#                     DELETE FROM capacity_resource_timeline
#                     WHERE resource_id = %s AND tenant_id = %s
#                       AND trmeric_roadmap_id = ANY(%s)
#                 """, (resource_id, tenant_id, list(remove_roadmaps)))
#                 removed_from.extend([f"roadmap '{roadmap_id_to_title.get(rid)}'" for rid in remove_roadmaps])
#                 total_removed += len(remove_roadmaps)

#             # === Final message ===
#             if removed_from:
#                 responses.append(f"Removed {resource_name} from {', '.join(removed_from)}.")
#             else:
#                 responses.append(f"No active assignments found for {resource_name} to remove.")

#             # Real-time update
#             socketio.emit('potential_agent', {
#                 "event": "info_updated",
#                 "resource_id": resource_id,
#                 "unassigned_count": total_removed
#             }, room=client_id)

#         final_msg = "\n".join(responses)
#         return final_msg if len(responses) > 1 else responses[0]

#     except Exception as e:
#         appLogger.error({"event": "unassign_failed", "error": str(e), "traceback": traceback.format_exc()})
#         return "Failed to unassign. Please try again."
# # def unassign_resources(
# #     tenant_id: int,
# #     user_id: int,
# #     llm=None,
# #     plan=None,
# #     user_query=None,
# #     socketio=None,
#     client_id=None,
#     session_id=None,
#     context_string=None,
#     **kwargs
# ):
#     sender = kwargs.get("step_sender")
#     model_opts = kwargs.get("model_opts2")

#     try:
#         # Parse context (you already built it perfectly)
#         import json
#         try:
#             resources = json.loads(context_string.split("active :")[1].split("All the projects")[0].strip())
#             projects = json.loads(context_string.split("active :")[1].split("All available roadmaps")[0].split("All the projects")[1].strip())
#             roadmaps = json.loads(context_string.split("All available roadmaps of this tenant:")[1].strip())
#         except:
#             resources = projects = roadmaps = []

#         # Build lookup maps
#         resource_name_to_id = {r["resource_name"].lower(): r["resource_id"] for r in resources}
#         project_title_to_id = {p["project_title"].lower(): p["project_id"] for p in projects}
#         roadmap_title_to_id = {r["roadmap_title"].lower(): r["roadmap_id"] for r in roadmaps}

#         prompt = unassign_resources_prompt(user_query, "\n".join(kwargs.get("conversation", [])[-10:]), context_string)
#         response = llm.run(prompt, model_opts, "agent::potential::unassign", {"tenant_id": tenant_id, "user_id": user_id},
#                            socketio=socketio, client_id=client_id)

#         extract = extract_json_after_llm(response, step_sender=sender)
#         print("--debug unassign extract:", extract)

#         clarifying = extract.get("clarifying_info", "")
#         if clarifying:
#             return clarifying

#         unassignments = extract.get("unassignments", [])
#         if not unassignments:
#             return "No valid unassignment request found."

#         responses = []

#         for item in unassignments:
#             resource_id = item["resource_id"]
#             target_type = item["target_type"]  # "project" or "roadmap"
#             target_id = item["target_id"]
#             target_title = item["target_title"]
#             resource_name = item["resource_name"]

#             # Validate IDs exist in context
#             if resource_id not in [r["resource_id"] for r in resources]:
#                 responses.append(f"Resource '{resource_name}' not found.")
#                 continue
#             if target_type == "project" and target_id not in [p["project_id"] for p in projects]:
#                 responses.append(f"Project '{target_title}' not found.")
#                 continue
#             if target_type == "roadmap" and target_id not in [r["roadmap_id"] for r in roadmaps]:
#                 responses.append(f"Roadmap '{target_title}' not found.")
#                 continue

#             # Build delete condition
#             if target_type == "project":
#                 condition = "trmeric_project_id = %s"
#                 params = (target_id,)
#             else:  # roadmap
#                 condition = "trmeric_roadmap_id = %s"
#                 params = (target_id,)

#             # Check if assignment exists
#             check_query = f"""
#                 SELECT id FROM capacity_resource_timeline
#                 WHERE resource_id = %s AND {condition} AND tenant_id = %s
#             """
#             existing = db_instance.retrieveSQLQueryOld(check_query, (resource_id, target_id, tenant_id))

#             if not existing:
#                 responses.append(f"{resource_name} is not assigned to {target_title}.")
#                 continue

#             # DELETE
#             delete_query = f"""
#                 DELETE FROM capacity_resource_timeline
#                 WHERE resource_id = %s AND {condition} AND tenant_id = %s
#             """
#             db_instance.executeSQLQuery(delete_query, (resource_id, target_id, tenant_id))

#             responses.append(f"Removed {resource_name} from {target_title} ({target_type}).")
#             socketio.emit('potential_agent', {
#                 "event": "info_updated",
#                 "resource_id": resource_id
#             }, room=client_id)

#         final_msg = "\n".join(responses)
#         return final_msg if len(responses) > 1 else responses[0]

#     except Exception as e:
#         appLogger.error({"event": "unassign_failed", "error": str(e), "traceback": traceback.format_exc()})
#         return "Failed to unassign. Please try again."
















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
#     print("--debug match---------", match)
#     if not match:
#         # Try to find exact or close match
#         print("--debug fallback--------------")
#         for r in resource_data:
#             full_name = f"{r.get('first_name','')} {r.get('last_name','')}".strip().lower()
#             if target_name in full_name or full_name in target_name:
#                 valid_resources.append(r)
#         return valid_resources

#     best_name = match[0]
#     idx = choices.index(best_name)

#     return valid_resources[idx]

