from typing import Dict, Any, Generator, List
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes, AgentReturnTypes
from src.trmeric_database.dao import TangoDao, IntegrationDao
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.models.OpenAIClient import ModelOptions
import json
import requests
from .jira_template import JIRA_MANAGEMENT_METHODS
from .prompts import *
import traceback
import re  # Added for issue key validation
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.trmeric_services.agents.functions.onboarding.creation_tools.AutonomousCreateProject import AutomousProjectAgent
from src.trmeric_services.project.projectService import ProjectService
from src.trmeric_services.integration.IntegrationService import IntegrationService


def emit_to_client(socketio, client_id, message: str):
    """
    Emit messages to the client via socketio.
    """
    socketio.emit("tango_chat_assistant", message, room=client_id)
    socketio.emit("tango_chat_assistant", "<end>", room=client_id)
    socketio.emit("tango_chat_assistant", "<<end>>", room=client_id)


def sendAgentUISocket(socketio, client_id, item="", metadata={}):
    # "ui_type": "<textbox|textarea|dropdown|date_picker|table>",
    # "options": ["<option1>", "<option2>"],
    # "placeholder": "<helpful_placeholder_text>",
    # "field_name": "<name_of_the_field>",
    if item == "resource":
        field_name = "Resource"
        ui_type = "dropdown"
        placeholder = "Select Resource"
        options = metadata.get("options") or []
    _json = {
        "ui_instructions": [
            {
                "field_name": field_name,
                "ui_type": ui_type,
                "placeholder": placeholder,
                "additional_metadata": {
                    "json_options": options,
                },
            }
        ]
    }
    socketio.emit("agent_controlled_ui", _json, room=client_id)


def createButtonForUITrigger(socketio, client_id, label, attrbutes):
    data_json = {
        "show_integration_modal_open_button": [
            {
                "label": label,
                "action": label,
                "attributes": attrbutes
            }
        ]
    }
    socketio.emit("agent_controlled_ui", data_json, room=client_id)


def integration_agent(
    tenantID: int,
    userID: int,
    llm=None,
    model_opts: ModelOptions = None,
    socketio=None,
    client_id: str = None,
    logInfo: Dict = None,
    last_user_message: str = None,
    sessionID: str = None,
    **kwargs
) -> Generator[str, None, None]:
    """
    Guides users to select Jira entities for Trmeric project creation using a conversational LLM.
    Yields only message strings.
    """
    tango_dao = TangoDao

    # Store user message if provided
    if last_user_message:
        tango_dao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key="jira_integration_conv",
            value=f"User Message: {last_user_message}",
            session_id=sessionID
        )

    # Fetch conversation history
    conv_ = tango_dao.fetchTangoStatesForSessionIdAndUserAndKeyAll(
        session_id=sessionID, user_id=userID, key="jira_integration_conv"
    )
    conversation = [c.get("value", "") for c in conv_]
    conversation = conversation[::-1]

    # Generate or update session state using LLM
    state_prompt = create_session_state_prompt(
        conversation, last_user_message)
    state_response = llm.run(state_prompt, model_opts,
                             'agent::integration::state_prompt', logInfo)
    session_state = extract_json_after_llm(state_response)

    print("debug --- ", state_response, session_state)

    def emit_and_store(message: str, end: bool = False):
        """Emit messages, store conversation state, and yield message string."""
        emit_to_client(socketio, client_id, message)
        tango_dao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key="jira_integration_conv",
            value=f"Session State: {json.dumps(session_state)}",
            session_id=sessionID
        )
        tango_dao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key="jira_integration_conv",
            value=f"Agent Response: {message}",
            session_id=sessionID
        )
        return message

    def only_store(message):
        """Store session state without emitting."""
        tango_dao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key="jira_integration_conv",
            value=f"Session State: {json.dumps(session_state)}",
            session_id=sessionID
        )
        tango_dao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key="jira_integration_conv",
            value=f"Agent Response: {message}",
            session_id=sessionID
        )
        return message

    def store_project_draft(project_details: Dict):
        """Store project details in trmeric_project_draft."""
        tango_dao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key="trmeric_project_draft",
            value=project_details,
            session_id=sessionID
        )

    def fetch_project_draft() -> Dict:
        """Fetch the latest project draft."""
        latest_draft = tango_dao.fetchTangoStatesForTenantAndKey(
            tenant_id=tenantID,
            key="trmeric_project_draft",
        )
        return latest_draft

    def fetch_headers():
        """Fetch Jira API headers from IntegrationDao."""
        try:
            integration_details = IntegrationDao.fetchActiveIntegrationForUserV2(
                userID, "jira")
            if not integration_details or not integration_details.get("metadata", {}).get("access_token"):
                return {"error_message": "Please connect Jira via OAuth2. Need help?"}
            access_token = integration_details.get(
                "metadata").get("access_token")
            return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        except Exception as e:
            print(f"Error in fetch_headers: {e}\n{traceback.format_exc()}")
            return {"error_message": f"Error accessing Jira integration: {str(e)}. Please try again."}

    def call_jira_api(endpoint: str, method: str = "GET", params: Dict = None) -> Dict:
        """Call Jira API with error handling."""
        url = f"https://api.atlassian.com/ex/jira/{session_state['cloud_id']}/rest/api/3{endpoint}"
        try:
            print("call jira api -- ", endpoint, method, params)
            response = requests.request(
                method, url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"Jira API error: {e}\n{traceback.format_exc()}")
            return {"error_message": f"Jira error: {str(e)}. Check permissions?"}

    # Add this helper function within integration_agent or in a shared utility

    def fetch_field_mapping(cloud_id: str, headers: Dict) -> Dict:
        """
        Fetch Jira field mappings to map custom field IDs to names.
        Returns a dict with custom field IDs as keys and field names as values.
        """
        try:
            url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/field"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            fields = response.json()
            custom_field_map = {}
            for field in fields:
                if field['id'].startswith('customfield_'):
                    custom_field_map[field['id']] = field['name']
            return custom_field_map
        except Exception as e:
            print(
                f"Error fetching field mapping: {e}\n{traceback.format_exc()}")
            return {}

    headers = fetch_headers()
    if not headers:
        yield emit_and_store("Some error occurred")
        return

    if headers.get("error_message"):
        yield emit_and_store(headers.get("error_message"))
        return

    # Step 1: Initialize and authenticate
    resources = []
    if session_state["step"] == "init":
        try:
            resources = requests.get(
                "https://api.atlassian.com/oauth/token/accessible-resources", headers=headers
            ).json()
        except requests.exceptions.RequestException as e:
            yield emit_and_store(f"Error accessing Jira resources: {str(e)}. Check your connection?")
            return
        if not resources:
            yield emit_and_store("No Jira resources found. Check your token?", end=True)
            return

        print("resources -- ", resources)
        # Check if resources is a list
        if not isinstance(resources, list):
            yield emit_and_store("Error: Jira resources response is not an array. Contact support or check API response.")
            return

        session_state["resources"] = [
            {"id": r["id"], "name": r["name"]} for r in resources]
        session_state["step"] = "select_resource"
        resource_names = [r["name"] for r in resources]
        if len(resource_names) > 1:
            answer = f"""Hi! I'm here to help you create Trmeric projects from your Jira setup.\n We have found multiple Jira instances.\n Please select from the dropdown?"""
            sendAgentUISocket(socketio, client_id, "resource",
                              {"options": resources})
        else:
            answer = f"""Hi! I'm here to help you create Trmeric projects from your Jira setup.\n  This is the instance I was able to find: **{', '.join(resource_names)}**. Would you like to proceed with this? \n ```json
      {{"cta_buttons":[
        {{
          "label": "Confirm",
          "key": "confirm"
        }}
      ]}}
      ```"""

        yield emit_and_store(answer)
        return

    # Step 2: Select resource (if multiple)
    if session_state["step"] == "select_resource":
        selected_resource = next(
            (r for r in session_state["resources"] if last_user_message.lower(
            ) in r["name"].lower()), None
        )

        print("selected resource ... ", selected_resource)
        if not selected_resource:
            yield emit_and_store(f"Sorry, couldn't find that instance. Please choose from: {', '.join([r['name'] for r in session_state['resources']])}.")
            return
        session_state["cloud_id"] = selected_resource["id"]
        session_state["selectd_resource_name"] = selected_resource["name"]
        session_state["step"] = "integrate"
        answer = f"""Would you like to create Trmeric projects from entire Jira projects, specific epics, or individual issues within the '{selected_resource['name']}' instance?"""
        yield emit_and_store(answer)
        return

    # Step 3: Integrate (conversational entity, project, and item selection)
    if session_state["step"] == "integrate":
        # Fetch minimal API data for context
        api_data = {}

        # Run LLM to determine entity, projects, items, and UI trigger
        prompt = create_integration_prompt(
            conversation, last_user_message, api_data)
        print("integration prompt ", prompt.formatAsString())
        llm_response = llm.run(
            prompt, model_opts, 'agent::integration::entity_selection', logInfo
        )
        print("integration response ", llm_response)
        integration_data = extract_json_after_llm(llm_response)

        # Update session state
        session_state["entity"] = integration_data["entity"]
        session_state["resources"] = []
        session_state["template_id"] = integration_data["template_id"]
        session_state["selected_projects"] = integration_data["selected_projects"]
        session_state.setdefault("intermediate", {}).update({
            "integration_data": integration_data,
            "selected_items": integration_data["selected_items"],
            # "ui_trigger": integration_data["ui_trigger"],
        })

        if integration_data.get("ui_trigger") in ["project_list", "issue_list", "epic_list"]:
            createButtonForUITrigger(socketio, client_id, label=integration_data.get("ui_trigger"), attrbutes={
                "selectd_resource_name": session_state.get("selectd_resource_name"),
                "selected_projects": session_state.get("selected_projects")
            })

        # Validate project keys if provided
        if integration_data["selected_projects"]:
            invalid_projects = []
            valid_projects = []
            for project_key in integration_data["selected_projects"]:
                project_check = call_jira_api(f"/project/{project_key}")
                if project_check and "error_message" not in project_check:
                    valid_projects.append(project_key)
                else:
                    invalid_projects.append(project_key)
            if invalid_projects:
                answer = f"Sorry, the following project keys don’t exist: {', '.join(invalid_projects)}. Please provide valid project keys (e.g., IP, DEV)."
                session_state["intermediate"]["ui_trigger"] = "project_list"
                yield emit_and_store(answer)
                return
            # Update session state with validated project keys
            session_state["selected_projects"] = valid_projects

        # Emit playback and question, stay in integrate if needed
        if integration_data["playback_and_question"]:
            yield emit_and_store(integration_data["playback_and_question"])
            return

        # Handle entity and project selection
        entity = integration_data["entity"]
        project_keys = integration_data["selected_projects"]

        # Prompt for project keys if needed
        if entity in ["epics", "issues"] and not project_keys:
            answer = f"Which Jira project(s) contain the {entity} you want to use? For example, IP, DEV."
            session_state["intermediate"]["ui_trigger"] = "project_list"
            yield emit_and_store(answer)
            return

        # Trigger item selection UI after project confirmation
        if entity in ["epics", "issues"] and project_keys and not integration_data["selected_items"]:
            item_type = entity[:-1]
            answer = f"Confirmed! You want to create Trmeric projects from {entity} in project(s) {', '.join(project_keys)}. Please select the {item_type}(s)."
            session_state["intermediate"]["ui_trigger"] = "issue_list" if entity == "issues" else "epic_list"

            yield emit_and_store(answer)
            return

        # If entity is projects and no items selected, trigger project selection UI
        if entity == "projects" and not integration_data["selected_items"]:
            answer = "Please select the Jira project(s) you want to create as Trmeric projects."
            session_state["intermediate"]["ui_trigger"] = "project_list"
            yield emit_and_store(answer)
            return

        # Validate selected items via Jira API
        if integration_data["selected_items"]:
            valid_items = []
            invalid_items = []
            for item in integration_data["selected_items"]:
                item_key = item["key"].upper()
                valid = False
                item_name = item_key

                if entity == "projects":
                    project_check = call_jira_api(f"/project/{item_key}")
                    if project_check and "error_message" not in project_check:
                        valid = True
                        item_name = project_check.get("name", item_key)
                elif entity in ["epics", "issues"]:
                    jql = f"key = {item_key}"
                    if entity == "epics":
                        jql += " AND issuetype = Epic"
                    if project_keys:
                        jql = f"({' OR '.join(f'project = {key}' for key in project_keys)}) AND {jql}"
                    item_response = call_jira_api(
                        "/search", params={"jql": jql, "fields": "summary,key", "maxResults": 1})
                    if item_response and "error_message" not in item_response and item_response.get("issues"):
                        valid = True
                        item_name = item_response["issues"][0]["fields"].get(
                            "summary", item_key)

                if valid:
                    valid_items.append({"key": item_key, "name": item_name})
                else:
                    invalid868_items.append(item_key)

            if invalid_items:
                project_str = f" in project(s) {', '.join(project_keys)}" if project_keys else ""
                item_type = entity[:-1]
                answer = f"Sorry, I couldn’t find the following {item_type} keys{project_str}: {', '.join(invalid_items)}. Please select valid {item_type} keys."
                if entity == "issues" and project_keys:
                    jql = " OR ".join(
                        f"project = {key}" for key in project_keys)
                    issues = call_jira_api(
                        "/search", params={"jql": jql, "fields": "summary,key", "maxResults": 5})
                    if issues and "error_message" not in issues:
                        issue_list = [
                            f"{i['key']} ({i['fields']['summary']})" for i in issues.get("issues", [])]
                        if issue_list:
                            answer += f"\nHere are some issues: {', '.join(issue_list)}."
                elif entity == "epics" and project_keys:
                    jql = " OR ".join(
                        f"project = {key} AND issuetype=Epic" for key in project_keys)
                    epics = call_jira_api(
                        "/search", params={"jql": jql, "fields": "summary,key", "maxResults": 5})
                    if epics and "error_message" not in epics:
                        epic_list = [
                            f"{i['key']} ({i['fields']['summary']})" for i in epics.get("issues", [])]
                        if epic_list:
                            answer += f"\nHere are some epics: {', '.join(epic_list)}."
                session_state["intermediate"]["ui_trigger"] = "issue_list" if entity == "issues" else "epic_list"
                yield emit_and_store(answer)
                return

            # Items validated, move to create_project
            session_state["intermediate"]["selected_items"] = valid_items
            # session_state["step"] = "create_project"
            # session_state["intermediate"]["sub_step"] = "generate_project"
            item_type = entity[:-1]
            item_str = ", ".join(
                f"{item['key']} ({item['name']})" for item in valid_items)
            answer = f"Found {item_type}(s): {item_str}. Ready to create Trmeric project(s) from these {item_type}(s). Proceed? Say 'yes' to create them."
            yield emit_and_store(answer)
            return

    # # Step 5: Create project
    if session_state["step"] == "create_project":
        entity = session_state["entity"]
        selected_items = session_state["intermediate"].get(
            "selected_items", []
        )
        item_type = entity[:-1]  # e.g., "epic" from "epics"

        print("debug --- create_project ", entity, selected_items,
              session_state["intermediate"].get("sub_step"))

        # Initialize intermediate if not set
        session_state.setdefault("intermediate", {}).setdefault(
            "sub_step", "generate_project")
        session_state["intermediate"].setdefault("project_drafts", [])
        # session_state["intermediate"].setdefault("current_project_index", 0)
        session_state["intermediate"].setdefault("user_changes", "")
        session_state["intermediate"].setdefault("streamed_drafts", "")

        # Sub-step: Generate and stream project drafts for all selected items
        if session_state["intermediate"]["sub_step"] == "generate_project" or session_state["intermediate"]["sub_step"] == "create_project" or session_state["intermediate"]["sub_step"] == "create_project_final":
            entity_data_list = []
            field_mapping = fetch_field_mapping(
                session_state["cloud_id"], headers)
            print("field mapping ---- ", field_mapping)
            for selected_item in selected_items:
                entity_data = {}
                if entity == "projects":
                    project_data = call_jira_api(
                        f"/project/{selected_item['key']}")
                    entity_data = project_data
                elif entity in ["epics", "issues"]:
                    jql = f"key = {selected_item['key']}"
                    if entity == "epics":
                        jql += " AND issuetype = Epic"
                    if session_state["selected_projects"]:
                        jql = f"({' OR '.join(f'project = {key}' for key in session_state['selected_projects'])}) AND {jql}"

                    fields = [
                        "summary", "description", "status", "assignee", "created",
                        "updated", "priority", "issuetype", "labels", "components",
                        "fixVersions", "duedate", "environment"
                    ]
                    # Find custom field IDs for "Key Results" and "Business Impact"
                    key_results_field = None
                    business_impact_field = None
                    for field_id, field_name in field_mapping.items():
                        # if field_name.lower() == "key results":
                        #     key_results_field = field_id
                        if field_name.lower() == "business impact":
                            business_impact_field = field_id

                    if key_results_field:
                        fields.append(key_results_field)
                    if business_impact_field:
                        fields.append(business_impact_field)

                    item_data = call_jira_api(
                        "/search",
                        params={
                            "jql": jql,
                            "fields": ",".join(fields),
                            "maxResults": 1
                        }
                    )
                    if item_data and "error_message" not in item_data and item_data.get("issues"):
                        entity_data = item_data["issues"][0]
                        # Explicitly add key
                        entity_data["key"] = selected_item["key"]
                        entity_data["additional_fields_mapping"] = {
                            "business_impact_field": business_impact_field}
                if entity_data:
                    entity_data_list.append(entity_data)
                else:
                    print(
                        f"debug --- Failed to fetch data for {item_type} {selected_item['key']}")

            if not entity_data_list:
                answer = f"Failed to fetch details for {item_type}(s) {', '.join(item['key'] for item in selected_items)}. Would you like to try again or select different {item_type}(s)?"
                yield emit_and_store(answer)
                return

            # Create LLM prompt to generate and stream Trmeric project drafts
            llm_prompt = ChatCompletion(
                system=f"""
                    You are an assistant tasked with creating Trmeric projects based on Jira entity data.
                    Your goal is to generate detailed project descriptions for multiple entities, streaming them as rich text for user review, and prompting for confirmation with a CTA button.

                    # Input
                    - Entity Type: {entity}
                    - Entity Data: {json.dumps(entity_data_list, indent=2)}
                    - User Changes (if any): {session_state['intermediate'].get('user_changes', '')}

                    # Task
                    - The Entity Data is an array of objects, each representing a Jira entity (project, epic, or issue).
                    - Each entity object contains a 'key' field (e.g., 'IP-123' for issues/epics, or 'IP' for projects) and other fields like name, summary, description, etc.
                    - For each entity in the Entity Data array, generate one Trmeric project draft with:
                    - title: A concise name (max 50 characters, based on name/summary).
                    - description: A detailed narrative (150–500 words) summarizing the entity's purpose, scope, and context.
                    - objectives: A list of 3–5 clear, actionable goals derived from the entity's scope.
                    - tech_stack: A list of technologies (infer from components, labels, description, or environment; use generic tech like ['Java', 'REST API'] if unclear).
                    - business_impact: (only if provided in Entity Data) sumarize the business impact of this project.
                    - Tailor the output based on entity type:
                    - Projects: Focus on overall goals, team, and scope.
                    - Epics: Emphasize the epic’s role, objectives, and deliverables.
                    - Issues: Highlight the task’s purpose, impact, technical requirements, and context within the project.
                    - If user_changes are provided, incorporate them to refine all drafts (e.g., apply a common tech_stack addition if specified).
                    - If data is missing, infer reasonable values (e.g., generic tech_stack for software issues).
                    - Ensure professional, clear, and actionable output.
                    - Output each draft as rich text, formatted for readability, with a clear header for each project using the entity's 'key' (e.g., 'Project Draft for IP-123').
                    - Separate drafts with a clear delimiter (e.g., '---').
                    - At the end of the output, append a confirmation prompt with a CTA button to confirm the drafts, formatted as:
                    ```
                        **Confirm Drafts**: Please review all drafts. You can:
                        - Confirm to proceed with project creation.
                        - Suggest modifications (e.g., 'add Python to all tech_stacks').
                        - Cancel to select different entities.

                        ```json
                        {{"cta_buttons": [{{"label": "Confirm", "key": "confirm"}}]}}
                        ```
                    ```
                    - Do not output JSON yet; the output will be parsed into JSON later if the user confirms or modifies the drafts.

                    # Output Format (Rich Text)

                """,
                prev=[],
                user="Generate and stream Trmeric project drafts as rich text based on the provided Jira entity data."
            )

            # Stream the LLM response and collect it
            llm_response = ""
            for chunk in llm.runWithStreaming(
                llm_prompt, model_opts, 'agent::integration::create_project_description', logInfo
            ):
                llm_response += chunk
                socketio.emit("tango_chat_assistant", chunk, room=client_id)
                yield chunk

            print("prompt debug --- ", llm_prompt.formatAsString())

            # Store the streamed text
            # session_state["intermediate"]["streamed_drafts"] = llm_response
            session_state["intermediate"]["sub_step"] = "modify_drafts"
            store_project_draft(llm_response)
            # Prompt user to review or modify all drafts
            # temp = f"\nAll {len(selected_items)} {item_type} drafts generated:\n\n"
            # temp = f"\n Please review all drafts. You can:\n- Say 'confirm' or 'looks good' to create all projects.\n- Suggest modifications for all drafts (e.g., 'add Python to all tech_stacks', 'prefix all titles with Feature').\n- Say 'cancel' to select different {item_type}(s)."

            # llm_response += temp
            # socketio.emit("tango_chat_assistant", temp, room=client_id)
            only_store(llm_response)
            socketio.emit("tango_chat_assistant", "<end>", room=client_id)
            socketio.emit("tango_chat_assistant", "<<end>>", room=client_id)
            # yield emit_and_store(llm_response)
            return

        # Sub-step: Modify or confirm all drafts
        if session_state["intermediate"]["sub_step"] == "modify_drafts" or session_state["intermediate"]["sub_step"] == "looks_good":
            streamed_drafts = fetch_project_draft()

            # LLM prompt to parse user intent for modifying or confirming drafts
            llm_prompt = ChatCompletion(
                system=f"""
                    You are an assistant tasked with interpreting user input for reviewing or modifying multiple Trmeric project drafts.
                    The user has received streamed drafts for {len(selected_items)} {item_type}(s).

                    # Input
                    - Conversation History: {json.dumps(conversation)}
                    - Latest User Message: {last_user_message or 'None'}
                    - Streamed Drafts(rich text): {streamed_drafts}

                    # Task
                    - Determine the user's intent based on the latest message:
                    - Confirm: User wants to create all projects(e.g., 'confirm', 'looks good', 'proceed').
                    - Modify: User suggests changes to all drafts(e.g., 'add Python to all tech_stacks', 'prefix all titles with Feature').
                    - Cancel: User wants to cancel(e.g., 'cancel', 'stop').
                    - Ambiguous: User input is unclear, ask for clarification.
                    - For modify intent, specify the changes as a string(e.g., 'Add Python to all tech_stacks; prefix all titles with Feature').
                    - Return a JSON object with:
                    - intent: 'confirm', 'modify', 'cancel', or 'ambiguous'
                    - modifications: String describing changes(empty if not modifying)
                    - next_question: Question to ask if intent is ambiguous or cancellation
                    - confidence: Float(0.0–1.0) for intent detection
                    - context: Notes for future interactions

                    # Output Format
                    ```json
                    {{
                        "intent": "<confirm|modify|cancel|ambiguous>",
                        "modifications": "<string>",
                        "next_question": "<string>",
                        "confidence": < float >,
                        "context": "<string>"
                    }}
                    ```
                """,
                prev=[],
                user="Interpret the user's intent for the streamed project drafts. Return the output in JSON format."
            )

            llm_response = llm.run(
                llm_prompt, model_opts, 'agent::integration::modify_drafts_intent', logInfo)
            user_intent = extract_json_after_llm(llm_response) or {
                "intent": "ambiguous",
                "modifications": "",
                "next_question": f"Please clarify: say 'confirm' to create all projects, suggest modifications (e.g., 'add Python to all tech_stacks'), or 'cancel' to select different {item_type}(s).",
                "confidence": 0.0,
                "context": "Failed to parse user intent"
            }

            if user_intent["intent"] == "confirm" or user_intent["intent"] == "modify":
                # Parse streamed drafts into JSON
                llm_prompt = ChatCompletion(
                    system=f"""
                        You are an assistant tasked with parsing rich text project drafts into JSON format for Trmeric projects.

                        ### Input
                        - Entity Type: {entity}
                        - Streamed Drafts (rich text): {streamed_drafts}
                        - Selected Item Keys: {json.dumps([item['key'] for item in selected_items])}

                        ### Task
                        - Parse the rich text drafts into a JSON dictionary where each key is an entity key (e.g., 'IP-123') and the value is a project draft.
                        - Each draft must have:
                        - title: exact from data.
                        - description: A detailed narrative (150–500 words) without the status of project.
                        - objectives: A list of 3–5 actionable goals.
                        - tech_stack: A list of technologies sensible and suited for this description.
                        - Ensure drafts exist for all provided Selected Item Keys.
                        - If parsing fails or drafts are missing, return an empty dictionary and note the error in context.

                        ### Output Proper Format
                        ```json
                        [
                            {{
                                "<entity_key>": {{
                                "title": "<string>",
                                "description": "<string>",
                                "objectives": ["<string>", ...],
                                "tech_stack": ["<string>", ...],
                                "business_impact: "<as provided in Streamed Drafts>"
                            }},
                            ...
                            }}
                        ]
                        ```
                    """,
                    prev=[],
                    user="Parse the streamed project drafts into proper JSON format."
                )

                llm_response = llm.runV2(
                    llm_prompt,
                    ModelOptions(
                        model="gpt-4o",
                        max_tokens=16000,
                        temperature=0.3
                    ), 'agent::integration::parse_drafts', logInfo)
                project_drafts = extract_json_after_llm(llm_response) or []

                print("debug 0----- ", llm_response)
                # Create projects concurrently using threading

                def create_project(input_data, tenantID, userID, llm, draft_key):
                    res = ProjectService().createProjectV2(
                        tenant_id=tenantID,
                        project_name=input_data.get("title", "") or "",
                        project_description=input_data,
                        is_provider=False,
                        log_input=logInfo
                    )
                    print("res for old enhance ", res)
                    mapping_data = AutomousProjectAgent().only_request_creation(
                        request_data=res,
                        tenantId=tenantID,
                        userId=userID
                    )
                    # create integration data
                    if mapping_data:
                        user_config_id = IntegrationDao.fetchIntegrationUserConfigId(
                            user_id=userID, integration='jira')
                        IntegrationDao.insertEntryToIntegrationProjectMapping(
                            tenant_id=tenantID,
                            user_id=userID,
                            user_config_id=user_config_id,
                            integration_project_identifier=draft_key,
                            integration_type='jira',
                            trmeric_project_id=mapping_data.get("project_id"),
                            metadata=json.dumps({
                                "key": draft_key,
                                "name": "",
                                "module": "v2" if session_state.get("entity") == "issues" else "v1",
                                "resource": session_state.get("selectd_resource_name"),
                            })
                        )
                        latest_mapping_id = IntegrationDao.fetchLatestIntegrationMappingOfUser(
                            user_id=userID, integration='jira')
                        # IntegrationService().updateIntegrationDataV2(
                        #     project_id=mapping_data.get("project_id"),
                        #     tenant_id=tenantID,
                        #     user_id=userID,
                        #     integration_mapping_id=latest_mapping_id
                        # )
                        threading.Thread(target=IntegrationService().updateIntegrationDataV2, args=(
                            mapping_data.get("project_id"),
                            tenantID,
                            userID,
                            latest_mapping_id
                        )).start()
                    return "", ""

                results = []
                with ThreadPoolExecutor(max_workers=min(len(project_drafts), 5)) as executor:
                    future_to_key = {
                        executor.submit(
                            create_project,
                            tenantID=tenantID,
                            userID=userID,
                            input_data=draft_data,
                            llm=llm,
                            draft_key=draft_key
                        ): draft_key
                        for draft in project_drafts
                        for draft_key, draft_data in draft.items()
                    }
                    for future in as_completed(future_to_key):
                        key = future_to_key[future]
                        try:
                            request_data, ret_val = future.result()
                            results.append(
                                f"Project created for {item_type} {key}.")
                        except Exception as e:
                            print(
                                f"debug --- Failed to create project for {key}: {e}")
                            results.append(
                                f"Failed to create project for {item_type} {key}: {str(e)}.")

                # Clear intermediate state
                session_state["intermediate"]["sub_step"] = "complete"
                session_state["intermediate"].pop("selected_items", None)
                session_state["intermediate"].pop("project_drafts", None)
                # session_state["intermediate"].pop(
                #     "current_project_index", None)
                session_state["intermediate"].pop("user_changes", None)
                session_state["intermediate"].pop("streamed_drafts", None)
                session_state["step"] = "select_items"

                answer = "\n".join(
                    results) + f"\nAll {len(selected_items)} {item_type}(s) processed. Please provide more {item_type} keys or say 'done' to finish."
                socketio.emit("tango_chat_assistant", answer, room=client_id)
                yield emit_and_store(answer)
                return

            elif user_intent["intent"] == "cancel":
                session_state["intermediate"]["sub_step"] = "complete"
                session_state["intermediate"].pop("selected_items", None)
                session_state["intermediate"].pop("project_drafts", None)
                # session_state["intermediate"].pop(
                #     "current_project_index", None)
                session_state["intermediate"].pop("user_changes", None)
                session_state["intermediate"].pop("streamed_drafts", None)
                session_state["step"] = "select_items"
                answer = f"Cancelled project creation for all {item_type}(s). Please provide different {item_type} keys or say 'done' to finish."
                socketio.emit("tango_chat_assistant", answer, room=client_id)
                yield emit_and_store(answer)
                return

            else:  # ambiguous
                answer = user_intent["next_question"]
                socketio.emit("tango_chat_assistant", answer, room=client_id)
                yield emit_and_store(answer)
                return


INTEGRATION_AGENT = AgentFunction(
    name="integration_agent_fn",
    description="Guides users to select Jira entities for Trmeric project creation using a conversational LLM.",
    args=[],
    return_description="Yields message strings to guide the user through Jira entity selection and Trmeric project creation.",
    function=integration_agent,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name,
    return_type=AgentReturnTypes.YIELD.name
)
