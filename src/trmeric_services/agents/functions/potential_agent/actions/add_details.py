import json
import traceback
from datetime import datetime
from typing import List, Dict, Any
from src.trmeric_database.dao import TenantDao,TangoDao,PortfolioDao
from src.trmeric_database.Database import db_instance
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_services.agents.functions.potential_agent.prompts import  add_potential_prompt_v2
from src.trmeric_services.agents.functions.potential_agent.utils import register_action


"""
 things : 
1. add a new resource
2. add an org team
3. add an existing resouce to org team

"""
@register_action("add_potential")
def add_details(
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
    Add new resource(s) and/or org team(s)
    """
    user_id = userID
    tenant_id = tenantID
    sender = kwargs.get("step_sender")
    model_opts = kwargs.get("model_opts2")
    conversation = kwargs.get("conversation", []) or []

    resources_list =kwargs.get("resources_info") or []
    portfolios_list =kwargs.get("portfolio_info") or []
    teams_list =kwargs.get("team_info") or []

    # print("---debug list-------\n", teams_list, "\n portfolios--", portfolios_list, "resources\n: ", resources_list)
    # return
    try:
        # Build lookup maps directly — NO json.loads()!
        resource_map = {(r.get('resource_name','') or "").lower(): r["resource_id"] for r in resources_list}
        resource_map_rev = {v:k for k,v in resource_map.items()}

        team_name_to_id = {(t.get("orgteam_name",'') or "").lower(): t["orgteam_id"] for t in teams_list}
        team_map_rev = {v:k for k,v in team_name_to_id.items()}

        portfolio_id_list = [p["id"] for p in portfolios_list]
        portfolio_title_to_id = {(p.get("title") or "").lower(): p["id"] for p in portfolios_list}
        portfolio_map_rev = {v:k for k,v in portfolio_title_to_id.items()}

        print("--debug mappings------",team_name_to_id,"\nportsof--", portfolio_title_to_id)
        # print("--debug resverse map-------", portfolio_map_rev)

        prompt = add_potential_prompt_v2(
            user_query=user_query,
            conversation= conversation, 
            context_string=context_string
        )

        response = llm.run(prompt, model_opts, "agent::potential::add_potential",
            {"tenant_id": tenant_id, "user_id": user_id},socketio=socketio, client_id=client_id
        )

        extract = extract_json_after_llm(response, step_sender=sender)
        print("--debug add_potential extract--", extract)

        clarifying = extract.get("clarifying_info", "")
        if clarifying:
            return clarifying
            

        action_type = extract.get("action_type")
        new_resources = extract.get("new_resources", []) or []
        resources_to_assign = extract.get("resources_to_assign", []) or []
        teams_to_create = extract.get("org_teams_to_create", []) or []
        print("\n\n--debug action_type--------", action_type,"\nThought process: ", extract.get('thought_process',''))

        print("--debug new_resources------", new_resources)
        print("\n--debug teams_tocreate------", teams_to_create, "\nresources to assign: ", resources_to_assign)

        if not new_resources and not teams_to_create and not resources_to_assign:
            return "⚠️ No valid resource or team found to add. Please provide details and try again."

            
        responses = []
        # === 1. Create Org Teams ===
        team_id_map = team_name_to_id.copy()  # existing
        for team in teams_to_create:
            print("--debug crerate orgteam-------", team)
            name = team["name"].strip()
            portfolio_id = team.get("portfolio_id",None) or None
            lname = name.lower()
            if lname in team_id_map:
                responses.append(f"Team '{name}' already exists.\n\n")
                continue

            # primary_skill = team["primary_skill"] not mandatory
            new_team_query = """
                INSERT INTO capacity_resource_group (name, tenant_id)
                VALUES (%s, %s) 
                RETURNING id
            """
            new_team_res = db_instance.executeSQLQuery(new_team_query, (name, tenant_id),fetch='one')
            new_team_id = new_team_res[0]
            print("---debug new org team id----", new_team_id)

            if portfolio_id: #insert into capacity_resource_group_portfolio_mapping
                new_tp_mapping_query = """
                    INSERT INTO capacity_resource_group_portfolio_mapping (portfolio_id,tenant_id,resource_group_id)
                    VALUES (%s, %s, %s) 
                    ON CONFLICT (portfolio_id,tenant_id,resource_group_id) DO NOTHING
                """
                db_instance.executeSQLQuery(new_tp_mapping_query,(portfolio_id,tenant_id,new_team_id))
                print("--done portfolio mapping------", portfolio_id)
                
            team_id_map[lname] = new_team_id
            responses.append(f"✅ Created new org team: {name}.\n\n")
            socketio.emit('potential_agent', {"event": "info_updated", "orgteam_id": new_team_id}, room=client_id)

        print("--debug team_id_map-----------", team_id_map)

        # === 2. Add New Resources ===
        for res in new_resources:
            full_name = res["full_name"].strip()
            email = res["email"].strip().lower()
            portfolio_id = res.get("portfolio_id",None) or None
            org_team_name = res.get("org_team_name", "").strip()

            # Validate portfolio exists
            if portfolio_id and portfolio_id not in portfolio_id_list:
                #add portfolio name
                responses.append(
                    f"⚠️ Invalid portfolio ID {portfolio_id}.Please choose from the available portfolios: {', '.join(portfolio_id_list)}.\n\n"
                )
                

            # Encrypt name
            parts = full_name.split()
            first = parts[0]
            last = " ".join(parts[1:]) if len(parts) > 1 else ""
            enc_first = db_instance.encrypt_text_to_base64(first)
            enc_last = db_instance.encrypt_text_to_base64(last)
            enc_email = db_instance.encrypt_text_to_base64(email)

            print("--debug inserting resource-----", parts, enc_email," Portfolio: ", portfolio_id)
            # Insert resource
            new_res_query = """
                INSERT INTO capacity_resource (
                    first_name, last_name, email, role, primary_skill, country,
                    experience_years, allocation, is_active, is_external,
                    created_on, created_by_id, tenant_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 0, TRUE, %s, NOW(), %s, %s)
                RETURNING id
            """
            new_res = db_instance.executeSQLQuery(
                new_res_query, (
                enc_first, enc_last, enc_email,
                res.get("role", "Engineer"),
                res.get("primary_skill", '') or '',
                res.get("country", "India"),
                res.get("experience_years", 0),
                res.get("is_external", False),
                user_id, tenant_id
            ), fetch='one')
            new_res_id = new_res[0]
            print("--debug new_res_id-----", new_res_id)

            # Assign to portfolio (mandatory)
            if portfolio_id:
                db_instance.executeSQLQuery("""
                    INSERT INTO capacity_resource_portfolio (portfolio_id, resource_id, tenant_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (tenant_id, resource_id, portfolio_id) DO NOTHING
                """, 
                (portfolio_id, new_res_id, tenant_id)
                )
            # Assign to team if specified
            if org_team_name:
                team_id = team_id_map.get(org_team_name.lower())
                if team_id:
                    db_instance.executeSQLQuery("""
                        INSERT INTO capacity_resource_group_mapping (resource_id, group_id)
                        VALUES (%s, %s) ON CONFLICT DO NOTHING
                        """, 
                        (new_res_id, team_id),fetch='one'
                    )

            responses.append(f"✅ {full_name} has been added to the potential successfully.\n\n")
            socketio.emit('potential_agent', {"event": "info_updated", "resource_id": new_res_id}, room=client_id)

        # === 3. Assign Existing Resource to Team ===
        for assign in resources_to_assign:
            rid = assign["resource_id"]
            tid = assign["orgteam_id"]

            db_instance.executeSQLQuery("""
                INSERT INTO capacity_resource_group_mapping (resource_id, group_id,tenant_id)
                VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
                """, 
                (rid, tid, tenant_id)
            )

            # rname = next((r["resource_name"] for r in resources if r["resource_id"] == rid), "Resource")
            # tname = next((t["orgteam_name"] for t in teams if t["orgteam_id"] == tid), "Team")
            rname = resource_map_rev.get(rid)
            tname = team_map_rev.get(tid)

            responses.append(f"✅ Added {rname} to org team {tname} successfully.\n\n")
            socketio.emit('potential_agent', {"event": "info_updated", "resource_id": rid, "orgteam_id": tid}, room=client_id)

        final_msg = "\n".join(responses)
        return final_msg

    except Exception as e:
        appLogger.error({"event": "add_potential_failed", "error": str(e), "traceback": traceback.format_exc()})
        return "Sorry, something failed while adding. Please try again."














    
        # responses = []

        # # === 1. Create Org Teams First (if needed) ===
        # team_id_map = {}  # name → id
        # for team in teams_to_create:
        #     name = team["name"].strip()
        #     primary_skill = team.get("primary_skill") or "Engineering"

        #     # Check if exists
        #     existing = db_instance.retrieveSQLQueryOld(f"""
        #         SELECT id FROM capacity_resource_group 
        #         WHERE tenant_id = {tenant_id} AND LOWER(name) ilike '%{name}%'
        #     """)

        #     if existing:
        #         team_id_map[name] = existing[0]["id"]
        #         responses.append(f"Org Team '{name}' already exists. Would you like to assign here?")
        #     else:
        #         new_id = db_instance.executeSQLQuery("""
        #             INSERT INTO capacity_resource_group (name, tenant_id, primary_skill, leader_id)
        #             VALUES (%s, %s, %s, NULL)
        #             RETURNING id
        #         """, (name, tenant_id, primary_skill))[0]["id"]
        #         team_id_map[name] = new_id
        #         responses.append(f"Created new team: {name}")

        # # === 2. Add Resources ===
        # for res in resources:
        #     full_name = res.get("resource_name")
        #     email = res.get("email").strip().lower()
        #     role = res.get("role", None) or None
        #     primary_skill = res.get("primary_skill",None) or None
        #     country = res.get("country", None) or None
        #     experience_years = res.get("experience_years", 0) or 0
        #     rate = res.get("rate", 0.0) or 0.0
        #     is_external = res.get("is_external", False)
        #     team_name = res.get("org_team_name",None) or None

        #     ##for adding existing resource to an org team
        #     orgteam_id = res.get("org_team_id",None) or None
        #     resource_id = res.get("resource_id",None) or None
        #     portfolio_id = res.get("portfolio_id",None) or None
        #     portfolio_name = [p.get('title') for p in user_portfolios if p.get('id') == portfolio_id]
            
        #     # Encrypt names
        #     parts = full_name.strip().split()
        #     first_name = parts[0]
        #     last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
        #     enc_first = db_instance.encrypt_text_to_base64(first_name)
        #     enc_last = db_instance.encrypt_text_to_base64(last_name)

        #     # Insert resource
        #     new_resource_query = """
        #         INSERT INTO capacity_resource (
        #             first_name, last_name, email, role, primary_skill,
        #             country, experience_years, allocation, is_active, is_external,
        #             created_on, created_by_id, tenant_id, rate
        #         ) 
        #         VALUES (%s, %s, %s, %s, %s, %s, %s, 0, TRUE, %s,NOW(), %s, %s, %s) 
        #         RETURNING id
        #     """
        #     new_resource_params = (
        #         enc_first, enc_last, email, role, primary_skill,
        #         country, experience_years, is_external,
        #         user_id, tenant_id, rate
        #     )
        #     new_resource_id = db_instance.executeSQLQuery(query=new_resource_query,params=new_resource_params,fetch='one')
        #     print("--debug new_resource_id-----", new_resource_id)


        #     if portfolio_id and action_type == "add_resource":
        #         ###add resource to the portfolio
        #         check_query = f"""
        #             select * from capacity_resource_portfolio 
        #             where 1=1 and resource_id = {resource_id}
        #             and portfolio_id = {portfolio_id}
        #         """
        #         check_query_res = db_instance.retrieveSQLQueryOld(check_query)
        #         if check_query_res:
        #             responses.append(f"{full_name} is already assigned in portfolio {portfolio_name}.")
        #         else:
        #             insert_portfolio_query = """
        #                 insert into capacity_resource_portfolio (portfolio_id,resource_id,tenant_id)
        #                 values (%s,%s,%s)
        #             """
        #             insert_portfolio_query_params = (portfolio_id,resource_id,tenant_id)
        #             db_instance.executeSQLQuery(query=insert_portfolio_query,params=insert_portfolio_query_params,fetch='one')
        #             responses.append(f"Assigned {full_name} in portfolio {portfolio_name}.")


        #     # Assign to team
        #     team_id = team_id_map.get(team_name)
        #     if action_type == "add_resource_to_orgteam" and team_id:
        #         db_instance.executeSQLQuery("""
        #             INSERT INTO capacity_resource_group_mapping (resource_id, group_id)
        #             VALUES (%s, %s)
        #             ON CONFLICT DO NOTHING
        #         """, (new_resource_id, team_id))

        #     msg = f"Added {full_name} as {role} in team '{team_name}'"
        #     responses.append(msg)

        #     socketio.emit('potential_agent', {"event": "info_updated","resource_id": new_resource_id}, room=client_id)

        # return responses

    except Exception as e:
        error_msg = "Failed to add resource/team. Please try again."
        appLogger.error({"event": "add_potential_failed", "error": str(e), "trace": traceback.format_exc()})
        return error_msg


