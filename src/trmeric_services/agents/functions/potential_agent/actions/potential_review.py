import re
import json
import traceback
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_services.agents.functions.potential_agent.utils import *
from src.trmeric_services.tango.functions.integrations.internal.resource import get_capacity_data
from src.trmeric_services.agents.functions.potential_agent.prompts import potential_review_prompt,potential_review_prompt_v2
from src.trmeric_database.dao import TenantDaoV2

@register_action("analyze_potential")
def potential_review(
    tenantID: int,
    userID: int,
    llm =None,
    plan=None,
    user_query=None,
    socketio=None,
    client_id=None,
    **kwargs
):
    
    """Handle general user queries about resource data and provide tailored responses."""
    try:
        step_sender = kwargs.get("step_sender")
        model_opts = kwargs.get("model_opts2")
        clarification = plan.get("thought_process","") or ""
        conversation = kwargs.get("conversation",[])[-7:] or []
        
        params = plan.get("selected_analyze_potential_attributes",[])
        # print("--debug selected_analyze_potential_attributes--", params, "\n\nConv: ", conversation)

        # Extract all filters
        projection_attrs = params.get("selected_projection_attrs") or ["id", "full_name", "role", "primary_skill", "current_allocation","country"]
        resource_ids = params.get("resource_ids")
        name = params.get("name")

        primary_skill = params.get("primary_skill")
        skill_keyword = params.get("skill_keyword")
        role = params.get("role")
        is_external = params.get("is_external")
        external_company_name = params.get("external_company_name")
        org_team_name = params.get("org_team_name")
        org_team_id = params.get("org_team_id")
        min_allocation = params.get("min_allocation")
        max_allocation = params.get("max_allocation")
        available_only = params.get("available_only", False)

        portfolio_ids = []
        normalize = lambda s: re.sub(r'\s+', ' ', re.sub(r'[&/-]', ' ', s or "").strip().lower().replace("portfolio", ""))
        portfolio_name = (params.get("portfolio_name", "") or "").strip().lower() or None
        if portfolio_name:
            all_portfolios = RoadmapDao.fetchAllPortfolioOfTenant(tenant_id=tenantID)
            # print("--debug portfolio info----------", all_portfolios)
            portfolio_rev_map = {p.get('title','').strip().lower(): p['id'] for p in all_portfolios}
            print("--debug portfolio_rev_map-------", portfolio_rev_map)

            normalized_name = normalize(portfolio_name)
            if normalized_name in portfolio_rev_map:
                portfolio_id = portfolio_rev_map[normalized_name]
            
                if portfolio_id:  # ensure it's not None or empty
                    portfolio_ids.append(int(portfolio_id))  # ensure it's int

        print("--debug portfolio_ids------", portfolio_ids)


        # Fetch data from DAO
        resource_data = TenantDaoV2.fetchResourceDataWithProjectionAttrs(
            tenant_id=tenantID,
            projection_attrs=projection_attrs,
            resource_ids=resource_ids,
            # name=name,
            primary_skill=primary_skill,
            skill_keyword=skill_keyword,
            role=role,
            is_external=is_external,
            external_company_name=external_company_name,
            org_team_name=org_team_name,
            org_team_id=org_team_id,
            min_allocation=min_allocation,
            max_allocation=max_allocation,
            available_only=available_only,
            portfolio_ids=portfolio_ids
        )
        if name:
            name_list = name if isinstance(name, list) else [name]
            search_terms = [n.lower().strip() for n in name_list if n and n.strip()]

            if search_terms:
                def name_matches(resource):
                    full_name = " ".join([
                        resource.get('first_name', '') or '',
                        resource.get('last_name', '') or ''
                    ]).lower()
                    return any(term in full_name for term in search_terms)

                resource_data = [r for r in resource_data if name_matches(r)]
        # print("\n--debug fetched resource_data----1", resource_data[:15])

        cleaned_resources = clean_resources_for_llm(resource_data)
        print("\n\n--debug fetched resource_data----2", cleaned_resources[:5])
        # return

        # step_sender.sendSteps(key="Analyzing Intent", val=True)
        # # Fetch and group capacity data
        # capacity_data = get_capacity_data(
        #     tenantID=tenantID,
        #     userID=userID,
        #     start_date=None,
        #     end_date=None,
        #     resource_name=None,
        #     eligibleProjects=[]
        # )
        # resource_data = capacity_data.get("resource_data",[])
        # print("--deubg resource_data----", type(resource_data),len(resource_data))
        # grouped_potential_data = group_resources_by_skills(resource_data)

        # step_sender.sendSteps(key="Generating Response", val=False)
        prompt = potential_review_prompt_v2(
            user_query = user_query,
            potential_data = json.dumps(cleaned_resources),
            clarification = conversation
        )

        response = llm.run(prompt,model_opts,"potential::review",{"tenant_id": tenantID, "user_id": userID},socketio,client_id)
        res = extract_json_after_llm(response)
        answer = res.get("analysis") or ""
        clarification = res.get("clarifying_info") or ""
      
        print("\n---debug potential_review res--------", answer ,"\nClarification: ", clarification)
        # step_sender.sendSteps(key="Generating Response", val=True)
        
        if clarification:
            yield clarification
            return
        
        # yield answer
        for chunk in re.finditer(r'.{1,35}[^\s]*\s+', answer + ' '):
            yield chunk.group()


    
    except Exception as e:
        appLogger.error({"event": "Potential review failed","error": str(e),"traceback": traceback.format_exc()})
        yield json.dumps({"error": str(e)})
        step_sender.sendError(key="Potential review failed", function="potential_review")
            

def stream_text(text: str):
    if not text:
        return
    
    # First, try to split by sentences (preserves meaning & flow)
    # This regex handles most punctuation: .!? followed by space/capital
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    
    for sentence in sentences:
        if not sentence.strip():
            continue
            
        # If sentence is short → yield all at once (feels snappy)
        if len(sentence.split()) <= 6:
            yield sentence + " "
            continue
        
        # For longer sentences: yield word-by-word with small chunks
        words = sentence.split()
        for i in range(0, len(words), 2):  # 2 words at a time = smooth & natural
            chunk = " ".join(words[i:i+2])
            if i + 2 < len(words):
                chunk += " "   # only add space if not last in sentence
            yield chunk
        
        # Add a tiny pause after full sentence (feels human)
        yield "  "  # or just " " — two spaces trigger newline in many UIs



def clean_resource_for_llm(obj):


    try:
        if not isinstance(obj, dict):
            return obj
        
        cleaned = {}

        # === 1. Name (always include if exists) ===
        first = (obj.get("first_name") or "").strip()
        last = (obj.get("last_name") or "").strip()
        full_name = " ".join([p for p in [first, last] if p])
        if full_name:
            cleaned["name"] = full_name

        location = obj.get("country")
        if location and str(location).strip() and str(location).lower() not in ["none", "null", ""]:
            cleaned["location"] = str(location).strip()

        # === 2. Role (keep even if slightly generic, but skip if truly None/empty) ===
        role = obj.get("role")
        if role and str(role).strip() and str(role).lower() not in ["none", "null", ""]:
            cleaned["role"] = str(role).strip()

        # === 3. Skills (very important) ===
        primary = obj.get("primary_skill")
        if primary and str(primary).strip():
            cleaned["primary_skill"] = str(primary).strip()

        skills = obj.get("skills")
        if skills and str(skills).strip():
            cleaned["skills"] = str(skills).strip()

        # === 4. Experience (only if meaningful) ===
        exp = obj.get("experience_years")
        if exp not in (None, "", 0, "0"):
            try:
                exp_val = int(exp)
                if exp_val > 0:
                    cleaned["experience_years"] = exp_val
            except (ValueError, TypeError):
                pass

        # === 5. Current Allocation (CRITICAL — keep even if >100%) ===
        alloc = obj.get("current_allocation")
        if alloc not in (None, "", 0):
            try:
                alloc_val = int(alloc)
                if alloc_val > 0:
                    cleaned["allocation%"] = alloc_val
            except (ValueError, TypeError):
                pass

        # === 6. Projects — extract only project names (most useful for LLM) ===
        def extract_project_names(projects):
            if not projects or not isinstance(projects, list):
                return None
            names = []
            for p in projects:
                if isinstance(p, dict):
                    name = p.get("project_name") or p.get("title") or p.get("name")
                    timeline = f"""Timeline: from {p.get('start_date')} to {p.get('end_date')}"""
                    if name and str(name).strip():
                        names.append({"name":str(name).strip(),"timeline": timeline})
                elif isinstance(p, str) and p.strip():
                    names.append(p.strip())
            return names if names else None

        past = extract_project_names(obj.get("past_projects"))
        current = extract_project_names(obj.get("current_projects"))
        future = extract_project_names(obj.get("future_projects"))

        if past:
            cleaned["past_projects"] = past
        if current:
            cleaned["current_projects"] = current
        if future:
            cleaned["planned_projects"] = future

        # === 7. Org Team ===
        org_team = obj.get("org_team")
        if org_team and isinstance(org_team, list):
            team_names = []
            for t in org_team:
                if isinstance(t, dict):
                    name = t.get("org_team") or t.get("name") or t.get("title")
                    if name and str(name).strip():
                        team_names.append(str(name).strip())
                elif isinstance(t, str) and t.strip():
                    team_names.append(t.strip())
            if team_names:
                cleaned["org_teams"] = team_names

        # === 8. External Info ===
        if obj.get("is_external"):
            cleaned["is_external"] = True
            company = obj.get("external_company_name")
            if company and str(company).strip():
                cleaned["company"] = str(company).strip()

        # === Final: only return if has meaningful content ===
        return cleaned if cleaned else obj
    except Exception as e:
        return obj


def clean_resources_for_llm(resources):
    if not resources:
        return []
    cleaned_list = []
    for r in resources:
        cleaned = clean_resource_for_llm(r)
        cleaned_list.append(cleaned)
    return cleaned_list






# def anonymize_name_for_search(name: str):
#     if not name:
#         return None, None, None

#     if name:
#         parts = name.strip().split()
#         first_name_raw = parts[0]
#         last_name_raw = " ".join(parts[1:]) if len(parts) > 1 else None

#         encrypted_fn = db_instance.encrypt_text_to_base64(first_name_raw)
#         encrypted_ln = db_instance.encrypt_text_to_base64(last_name_raw) if last_name_raw else None
#     else:
#         encrypted_fn = encrypted_ln = None
#     return encrypted_fn,encrypted_ln
# ARGUMENTS = [
#     {
#         "name": "primary_skill_group",
#         "type": "str",
#         "description": "The primary skill group selected for potential review"
#     },
#     {
#         "name": "resource_ids",
#         "type": "int[]",
#         "description": "List or resource ids on which the user queries on"
#     },
#     {
#         "name": "start_date",
#         "type": "str",
#         "description": "The start date user selected"
#     },
#     {
#         "name": "end_date",
#         "type": "str",
#         "description": "The end date user selected"
#     },
# ]

# POTENTIAL_REVIEW = AgentFunction(
#     name="potential_review",
#     description="""It will be used to get the details of the resource belonging to a particular primary skill group
#         Workflow:
#         1. User will be presented the list of Primary skills to choose from
#         2. on selection the list of resource will appear in it
#         3. User can select the resources inside them or can tell an overview or summary
#         4. The same info will be processed & sent through socket 
    
#     """,
#     args=ARGUMENTS,
#     return_description="",
#     function=potential_review,
#     type_of_func=AgentFnTypes.ACTION_TAKER_UI.name,
# )




