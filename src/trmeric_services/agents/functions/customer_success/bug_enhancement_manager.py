from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes, AgentReturnTypes
from src.trmeric_database.dao import TangoDao, TenantDao, BugEnhancementDao
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.models.OpenAIClient import ModelOptions
import json
from uuid import UUID
import datetime
from tabulate import tabulate  # Add this dependency for table formatting
from src.trmeric_api.logging.AppLogger import appLogger
import traceback


def detect_intent(conv, last_user_message, llm, model_opts, logInfo, userID, users_json):
    prompt = ChatCompletion(
        system="""
            You are a Customer Success Agent tasked with determining the user's intent regarding bugs/enhancements based on their conversation.
            The user may want to:
            - **Create**: Start creating a new bug or enhancement, typically requiring a UI form.
            - **Update**: Start updating an existing bug or enhancement.
            - **View**: List bugs or enhancements, possibly with filters.
            - **Submit_create**: Submit data for creating a new bug/enhancement, either via UI or directly from a typed message.
            - **Submit_update**: Submit data for updating an existing bug/enhancement with at least one field besides Bug ID.
            - **Unclear**: Intent is not clear.

            ### Input
            - Conversation history: {conv}
            - Latest user message: {last_user_message}
            - Current user ID: {userID} (represents 'me')
            - Tenant users: {users_json} (list of users with 'id' and 'username')

            ### Task
            Analyze the conversation and latest message to determine the user's intent.
            - For **submit_create**:
                - Detect if the user intends to create a bug/enhancement directly via text (e.g., "create a bug: <description>", "create an enhancement: <description>", "create a bug in <context>: <description>").
                - Extract fields:
                    - **Type**: 'bug' or 'enhancement' (infer from keywords "bug" or "enhancement" in the message).
                    - **Title**: Generate a concise title summarizing the description (e.g., for "customer success agent UI shows up...", title might be "Unexpected UI Display in Bug Creation").
                    - **Description**: Use the text after the colon or the full relevant description (e.g., "customer success agent UI shows up even when i write description of bug").
                    - **Priority**: Infer from keywords (e.g., "urgent" → "high", "critical" → "critical", "important" → "high") or default to 'medium'.
                    - **Assigned To**: Map user references (e.g., 'me', 'John') to user IDs from the tenant users list, if mentioned; default to null.
                - Required fields: Type, Title, Description.
                - Optional fields: Priority (default 'medium'), Assigned To (default null).
                - If Type, Title, and Description are extracted, classify as 'submit_create' and include all extracted fields in submitted_data.
                - If any required field is missing or unclear, classify as 'create' to trigger UI rendering or clarifying questions.
            - For **submit_update**:
                - Detect if the user is submitting update data (e.g., "Submit" after selecting a Bug ID, or "update bug 13 with status resolved").
                - Extract fields: Bug ID (required), Type, Title, Description, Priority, Status, Resolution Description, Comments, Assigned To, Resolved By.
                - Require at least one field besides Bug ID (from message, conversation, or UI).
                - If the message is "Submit", check conversation history for a recent Bug ID selection and expect UI-submitted fields.
                - If no fields besides Bug ID, classify as 'update' to prompt for details.
                - Map user references to numeric user IDs for Assigned To or Resolved By.
            - For **view**, extract filters and map user references to user IDs.
            - For **update**, include Bug ID or Title in submitted_data if provided.
            - If intent is unclear, return 'unclear'.

            ### Output Format
            ```json
            {
                "intent": "<create|update|view|submit_create|submit_update|unclear>",
                "filters": { "<filter_name>": "<value>" },  # For 'view', optional
                "submitted_data": { "<field_name>": "<value>" }  # For 'submit_create', 'submit_update', or 'update'
            }
            ```
            Map user references to numeric user IDs. If a user reference cannot be resolved, set the field to null and note it in 'your_thought'.
        """,
        prev=[],
        user=f"""
            Conversation: {conv}
            Latest message: {last_user_message}
            Current user ID: {userID}
            Tenant users: {users_json}
            Determine the intent, any filters for 'view', or submitted data for 'submit_create'/'submit_update'/'update'.
            For 'submit_create', check for direct creation requests (e.g., "create a bug: <description>", "create a bug in <context>: <description>"). Extract Type, Title, Description (required), Priority ('medium' default), Assigned To (null default).
            For 'submit_update', ensure at least one field besides Bug ID is provided; if only "Submit", check context for Bug ID and classify as 'update' if no fields.
            Use numeric user IDs for Assigned To and Resolved By, matching usernames case-insensitively with partial matches if unambiguous.
        """
    )
    response = llm.run(prompt, model_opts, 'agent::detect_intent', logInfo)
    return extract_json_after_llm(response)


def serialize_uuids(item):
    """
    Recursively convert UUID objects to strings for JSON serialization.
    :param item: Input item (dict, list, UUID, or other)
    :return: Item with UUIDs converted to strings
    """
    if isinstance(item, dict):
        return {k: serialize_uuids(v) for k, v in item.items()}
    elif isinstance(item, list):
        return [serialize_uuids(i) for i in item]
    elif isinstance(item, UUID):
        return str(item)
    return item


def emit_to_client(socketio, client_id, message, end=False, final_end=False):
    """
    Helper function to emit messages to the client via socketio.
    """
    socketio.emit("tango_chat_assistant", message, room=client_id)
    if end:
        socketio.emit("tango_chat_assistant", "<end>", room=client_id)
    if final_end:
        socketio.emit("tango_chat_assistant", "<<end>>", room=client_id)


def enter_agent_response(tenantID, userID, sessionID, data_string):
    TangoDao.insertTangoState(
        tenant_id=tenantID,
        user_id=userID,
        key="bug_enhancement_conv",
        value=data_string,
        session_id=sessionID
    )


def manage_bug_enhancement(
    tenantID: int,
    userID: int,
    llm=None,
    model_opts=None,
    socketio=None,
    client_id=None,
    logInfo=None,
    last_user_message=None,
    sessionID=None,
    **kwargs
):
    """
    Agent function to manage bug/enhancement tasks (create, update, view) conversationally.
    Enhanced to support bug search by title and return tables for view intent.
    """
    print("debug -- manage_bug_enhancement", tenantID,
          userID, last_user_message, sessionID)

    # Store the latest user message
    if last_user_message:
        TangoDao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key="bug_enhancement_conv",
            value=f"User Message: {last_user_message}",
            session_id=sessionID
        )

    # Fetch conversation history
    conv_ = TangoDao.fetchTangoStatesForSessionIdAndUserAndKeyAll(
        session_id=sessionID,
        user_id=userID,
        key="bug_enhancement_conv"
    )
    conv = []
    for c in conv_:
        conv.append(c.get("value", ""))

    print("--- conv ", conv)

    # Fetch users for the tenant
    user_list = TenantDao.FetchUsersOfTenant(tenant_id=tenantID)
    users_json = json.dumps([
        {"id": user["user_id"], "username": user.get("username", "")}
        for user in user_list
    ])

    # Detect user intent
    # intent_response = detect_intent(
    #     conv, last_user_message, llm, model_opts, logInfo)
    intent_response = detect_intent(
        conv, last_user_message, llm, model_opts, logInfo, userID, users_json
    )
    intent = intent_response.get("intent", "unclear")
    filters = intent_response.get("filters", {}) if intent == "view" else {}
    submitted_data = intent_response.get("submitted_data", {}) if intent in [
        "submit_create", "submit_update", "update"] else {}
    print("--- intent ", intent, "filters ",
          filters, "submitted_data ", submitted_data)

    TangoDao.insertTangoState(
        tenant_id=tenantID,
        user_id=userID,
        key="bug_enhancement_conv",
        value=f"Agent Understanding of the query and conv: {intent_response}",
        session_id=sessionID
    )
    # If intent is unclear, ask for clarification
    if intent == "unclear":
        answer = """
Hi there! 👋 I'm your Customer Success Assistant. Here's what I can help you with today: \n
🐞 Create a new bug or enhancement \n
🔍 Check status of an existing bug or enhancement \n
🛠️ Assign, update, or resolve bugs and enhancements \n

Just let me know what you'd like to do!
        """
        emit_to_client(socketio, client_id, answer, end=True, final_end=True)
        yield answer
        enter_agent_response(tenantID, userID, sessionID,
                             f"Agent answer: {answer}")
        return

    # Handle 'submit_create' intent
    if intent == "submit_create":
        try:
            bug_id = BugEnhancementDao.create_bug_enhancement(
                tenant_id=tenantID,
                type=submitted_data.get("Type"),
                title=submitted_data.get("Title"),
                description=submitted_data.get("Description"),
                priority=submitted_data.get("Priority"),
                created_by_id=userID,
                assigned_to_id=submitted_data.get("Assigned To")
            )
            answer = f"Enhancement created successfully! Bug ID: {bug_id}"
            emit_to_client(socketio, client_id, answer,
                           end=True, final_end=True)
            yield answer
            enter_agent_response(tenantID, userID, sessionID,
                                 f"Agent answer: {answer}")
            return
        except Exception as e:
            answer = f"Error creating enhancement: {str(e)}. Please try again."
            emit_to_client(socketio, client_id, answer,
                           end=True, final_end=True)
            yield answer
            enter_agent_response(tenantID, userID, sessionID,
                                 f"Agent answer: {answer}")
            appLogger.error({"error": str(e), "traceback": traceback.format_exc(
            ), "event": "BugEnhancementDao.create_bug_enhancement"})
            return

    if intent == "submit_update":
        try:
            bug_id = submitted_data.get("Bug ID")
            if not bug_id:
                answer = "No Bug ID provided. Please select a bug to update."
                emit_to_client(socketio, client_id, answer, end=True, final_end=True)
                yield answer
                enter_agent_response(tenantID, userID, sessionID, f"Agent answer: {answer}")
                return

            existing_bug = BugEnhancementDao.fetch_bug_enhancement_by_id(
                tenant_id=tenantID, bug_id=bug_id)
            if not existing_bug:
                answer = f"Bug/Enhancement {bug_id} not found. Please select a valid bug ID."
                emit_to_client(socketio, client_id, answer, end=True, final_end=True)
                yield answer
                enter_agent_response(tenantID, userID, sessionID, f"Agent answer: {answer}")
                return

            updates = {}
            # Validate and compare fields
            if "Type" in submitted_data and submitted_data["Type"] != existing_bug.get("type"):
                updates["type"] = submitted_data["Type"]
            if "Title" in submitted_data and submitted_data["Title"] != existing_bug.get("title"):
                updates["title"] = submitted_data["Title"]
            if "Description" in submitted_data and submitted_data["Description"] != existing_bug.get("description"):
                updates["description"] = submitted_data["Description"]
            if "Priority" in submitted_data and submitted_data["Priority"] != existing_bug.get("priority"):
                updates["priority"] = submitted_data["Priority"]
            if "Status" in submitted_data and submitted_data["Status"] != existing_bug.get("status"):
                updates["status"] = submitted_data["Status"]
            if "Resolution Description" in submitted_data and submitted_data["Resolution Description"] != existing_bug.get("resolution_description"):
                updates["resolution_description"] = submitted_data["Resolution Description"]
            if "Comments" in submitted_data and submitted_data["Comments"] != existing_bug.get("comments"):
                updates["comments"] = submitted_data["Comments"]
            if "Assigned To" in submitted_data:
                assigned_to = submitted_data["Assigned To"]
                # Convert empty string or invalid values to None, ensure integer if provided
                if assigned_to == "" or not isinstance(assigned_to, (int, str)) or (isinstance(assigned_to, str) and not assigned_to.isdigit()):
                    assigned_to = None
                else:
                    assigned_to = int(assigned_to) if isinstance(assigned_to, str) else assigned_to
                if assigned_to != existing_bug.get("assigned_to_id"):
                    updates["assigned_to_id"] = assigned_to
            if "Resolved By" in submitted_data:
                resolved_by = submitted_data["Resolved By"]
                # Convert empty string or invalid values to None, ensure integer if provided
                if resolved_by == "" or not isinstance(resolved_by, (int, str)) or (isinstance(resolved_by, str) and not resolved_by.isdigit()):
                    resolved_by = None
                else:
                    resolved_by = int(resolved_by) if isinstance(resolved_by, str) else resolved_by
                if resolved_by != existing_bug.get("resolved_by_id"):
                    updates["resolved_by_id"] = resolved_by
            # Handle resolved_by_id for resolved status
            if updates.get("status") == "resolved" or (submitted_data.get("Status") == "resolved" and existing_bug.get("status") != "resolved"):
                resolved_by = submitted_data.get("Resolved By")
                # Validate Resolved By
                if resolved_by == "" or not isinstance(resolved_by, (int, str)) or (isinstance(resolved_by, str) and not resolved_by.isdigit()):
                    resolved_by = userID  # Default to current user
                else:
                    resolved_by = int(resolved_by) if isinstance(resolved_by, str) else resolved_by
                updates["resolved_by_id"] = resolved_by

            if not updates:
                answer = f"No changes detected for Bug/Enhancement {bug_id}. Please provide different values to update."
                serialized_bug = serialize_uuids(existing_bug)
                prompt = create_bug_enhancement_prompt(conv, users_json, tenantID, "update", serialized_bug)
                response = llm.run(prompt, model_opts, 'agent::manage_bug_enhancement', logInfo)
                response = extract_json_after_llm(response)
                socketio.emit("agent_controlled_ui", response, room=client_id)
                emit_to_client(socketio, client_id, answer, end=True, final_end=True)
                yield answer
                enter_agent_response(tenantID, userID, sessionID, f"Agent answer: {answer}")
                return

            BugEnhancementDao.update_bug_enhancement(
                tenant_id=tenantID,
                bug_id=bug_id,
                updates=updates,
                updated_by_id=userID
            )
            answer = f"Bug/Enhancement {bug_id} updated successfully!"
            emit_to_client(socketio, client_id, answer, end=True, final_end=True)
            yield answer
            enter_agent_response(tenantID, userID, sessionID, f"Agent answer: {answer}")
            return
        except Exception as e:
            answer = f"Error updating bug/enhancement: {str(e)}. Please try again."
            emit_to_client(socketio, client_id, answer, end=True, final_end=True)
            yield answer
            enter_agent_response(tenantID, userID, sessionID, f"Agent answer: {answer}")
            appLogger.error({"error": str(e), "traceback": traceback.format_exc(),
                            "event": "BugEnhancementDao.update_bug_enhancement"})
            return

    # Handle 'view' intent: Return a table of bugs
    if intent == "view":
        bugs = BugEnhancementDao.fetch_bugs_by_filters(
            tenant_id=tenantID, filters=filters)
        serialized_bugs = serialize_uuids(bugs)

        # Generate table using tabulate
        if not serialized_bugs:
            answer = "No bugs or enhancements found. Would you like to create a new one?"
            emit_to_client(socketio, client_id, answer,
                           end=True, final_end=True)
            yield answer
            enter_agent_response(tenantID, userID, sessionID,
                                 f"Agent answer: {answer}")
            return

        # Create table headers and rows
        headers = ["Bug ID", "Type", "Title", "Description", "Status",
                   "Priority", "Created By", "Assigned To", "Resolved By"]
        rows = []
        user_map = {user["id"]: user["username"]
                    for user in json.loads(users_json)}

        col_widths = {
            "Bug ID": 36,  # UUIDs are 36 characters
            "Type": 12,
            "Title": 20,
            "Description": 30,
            "Status": 12,
            "Priority": 10,
            "Created By": 15,
            "Assigned To": 15,
            "Resolved By": 15
        }

        header_row = "| " + \
            " | ".join(f"{h:<{col_widths[h]}}" for h in headers) + " |"
        separator_row = "| " + \
            " | ".join("-" * col_widths[h] for h in headers) + " |"

        # Data rows
        rows = []
        for bug in serialized_bugs:
            description = str(bug.get("description", "") or "")
            truncated_desc = description[:50] + \
                ("..." if len(description) > 50 else "")
            row = [
                str(bug.get("id", "") or ""),
                str(bug.get("type", "") or ""),
                str(bug.get("title", "") or ""),
                truncated_desc,
                str(bug.get("status", "") or ""),
                str(bug.get("priority", "") or ""),
                user_map.get(bug.get("created_by_id"), ""),
                user_map.get(bug.get("assigned_to_id"), ""),
                user_map.get(bug.get("resolved_by_id"), "")
            ]
            # Format each cell to fit column width, left-aligned
            formatted_row = "| " + \
                " | ".join(
                    f"{cell:<{col_widths[headers[i]]}}" for i, cell in enumerate(row)) + " |"
            rows.append(formatted_row)

        # Combine table parts
        table = "\n".join([header_row, separator_row] + rows)
        answer = f"Here are the bugs/enhancements for your tenant:\n\n{table}\n"

        # Stream the table
        emit_to_client(socketio, client_id, answer, end=True, final_end=True)
        yield answer
        enter_agent_response(tenantID, userID, sessionID,
                             f"Agent answer: {answer}")
        return

    # Handle 'create' intent
    if intent == "create":
        prompt = create_bug_enhancement_prompt(
            conv, users_json, tenantID, intent)
        response = llm.run(prompt, model_opts,
                           'agent::manage_bug_enhancement', logInfo)
        response = extract_json_after_llm(response)
        print("manage_bug_enhancement ========", response)

        # TangoDao.insertTangoState(
        #     tenant_id=tenantID,
        #     user_id=userID,
        #     key="bug_enhancement_conv",
        #     value=str(response),
        #     session_id=sessionID
        # )
        socketio.emit("agent_controlled_ui", response, room=client_id)

        final_prompt = final_output_prompt(
            conv, response, users_json, tenantID)
        answer = ''
        for chunk in llm.runWithStreaming(
            final_prompt,
            ModelOptions(model="gpt-4o", max_tokens=14000, temperature=0.3),
            'tango::master::bug_enhancement_output',
            None
        ):
            emit_to_client(socketio, client_id, chunk)
            answer += chunk
        emit_to_client(socketio, client_id, "", end=True, final_end=True)
        yield answer
        enter_agent_response(tenantID, userID, sessionID,
                             f"Agent answer: {answer}")
        return

    # Handle 'update' intent
    if intent == "update":
        bug_id = submitted_data.get("Bug ID")
        bug_title = submitted_data.get("Title")

        if not bug_id and bug_title:
            # Search for bugs by title
            bugs = BugEnhancementDao.fetch_bugs_by_filters(
                tenant_id=tenantID, filters={"title": bug_title})
            if not bugs:
                answer = f"No bugs/enhancements found with title '{bug_title}'. Please try another title or list all bugs."
                emit_to_client(socketio, client_id, answer,
                               end=True, final_end=True)
                yield answer
                enter_agent_response(
                    tenantID, userID, sessionID, f"Agent answer: {answer}")
                return
            elif len(bugs) > 1:
                # Multiple bugs found, show a table consistent with 'view' intent
                serialized_bugs = serialize_uuids(bugs)
                user_map = {user["id"]: user["username"]
                            for user in json.loads(users_json)}

                # Define headers and column widths (same as 'view')
                headers = ["Bug ID", "Type", "Title", "Description", "Status",
                           "Priority", "Created By", "Assigned To", "Resolved By"]
                col_widths = {
                    "Bug ID": 36,
                    "Type": 12,
                    "Title": 20,
                    "Description": 30,
                    "Status": 12,
                    "Priority": 10,
                    "Created By": 15,
                    "Assigned To": 15,
                    "Resolved By": 15
                }

                # Build table
                header_row = "| " + \
                    " | ".join(f"{h:<{col_widths[h]}}" for h in headers) + " |"
                separator_row = "| " + \
                    " | ".join("-" * col_widths[h] for h in headers) + " |"
                rows = []
                for bug in serialized_bugs:
                    description = str(bug.get("description", "") or "")
                    truncated_desc = description[:50] + \
                        ("..." if len(description) > 50 else "")
                    row = [
                        str(bug.get("id", "") or ""),
                        str(bug.get("type", "") or ""),
                        str(bug.get("title", "") or ""),
                        truncated_desc,
                        str(bug.get("status", "") or ""),
                        str(bug.get("priority", "") or ""),
                        user_map.get(bug.get("created_by_id"), ""),
                        user_map.get(bug.get("assigned_to_id"), ""),
                        user_map.get(bug.get("resolved_by_id"), "")
                    ]
                    formatted_row = "| " + " | ".join(
                        f"{cell:<{col_widths[headers[i]]}}" for i, cell in enumerate(row)) + " |"
                    rows.append(formatted_row)

                # Combine table parts
                table = "\n".join([header_row, separator_row] + rows)
                answer = f"Multiple bugs found with title '{bug_title}':\n\n{table}\nPlease select a Bug ID to update."
                emit_to_client(socketio, client_id, answer,
                               end=True, final_end=True)
                yield answer
                enter_agent_response(
                    tenantID, userID, sessionID, f"Agent answer: {answer}")
                return
            else:
                # Single bug found, set bug_id
                bug_id = str(bugs[0]["id"])

        if not bug_id:
            # Show list of bugs
            bugs = BugEnhancementDao.fetch_bugs_by_filters(
                tenant_id=tenantID, filters={})
            serialized_bugs = serialize_uuids(bugs)

            # Generate table (same as 'view')
            if not serialized_bugs:
                answer = "No bugs or enhancements found. Would you like to create a new one?"
                emit_to_client(socketio, client_id, answer,
                               end=True, final_end=True)
                yield answer
                enter_agent_response(
                    tenantID, userID, sessionID, f"Agent answer: {answer}")
                return

            user_map = {user["id"]: user["username"]
                        for user in json.loads(users_json)}
            headers = ["Bug ID", "Type", "Title", "Description", "Status",
                       "Priority", "Created By", "Assigned To", "Resolved By"]
            col_widths = {
                "Bug ID": 36,
                "Type": 12,
                "Title": 20,
                "Description": 30,
                "Status": 12,
                "Priority": 10,
                "Created By": 15,
                "Assigned To": 15,
                "Resolved By": 15
            }

            header_row = "| " + \
                " | ".join(f"{h:<{col_widths[h]}}" for h in headers) + " |"
            separator_row = "| " + \
                " | ".join("-" * col_widths[h] for h in headers) + " |"
            rows = []
            for bug in serialized_bugs:
                description = str(bug.get("description", "") or "")
                truncated_desc = description[:50] + \
                    ("..." if len(description) > 50 else "")
                row = [
                    str(bug.get("id", "") or ""),
                    str(bug.get("type", "") or ""),
                    str(bug.get("title", "") or ""),
                    truncated_desc,
                    str(bug.get("status", "") or ""),
                    str(bug.get("priority", "") or ""),
                    user_map.get(bug.get("created_by_id"), ""),
                    user_map.get(bug.get("assigned_to_id"), ""),
                    user_map.get(bug.get("resolved_by_id"), "")
                ]
                formatted_row = "| " + " | ".join(
                    f"{cell:<{col_widths[headers[i]]}}" for i, cell in enumerate(row)) + " |"
                rows.append(formatted_row)

            table = "\n".join([header_row, separator_row] + rows)
            answer = f"Please select a Bug ID to update:\n\n{table}"

            emit_to_client(socketio, client_id, answer)

            # Render Bug ID selection UI
            prompt = create_bug_enhancement_prompt(
                conv, users_json, tenantID, intent)
            response = llm.run(prompt, model_opts,
                               'agent::manage_bug_enhancement', logInfo)
            response = extract_json_after_llm(response)
            print("manage_bug_enhancement ========", response)

            socketio.emit("agent_controlled_ui", response, room=client_id)
            emit_to_client(socketio, client_id, "", end=True, final_end=True)
            yield answer
            enter_agent_response(tenantID, userID, sessionID,
                                 f"Agent answer: {answer}")
            return
        else:
            # Fetch bug and render update UI (unchanged)
            existing_bug = BugEnhancementDao.fetch_bug_enhancement_by_id(
                tenant_id=tenantID, bug_id=bug_id)
            if not existing_bug:
                answer = f"Bug/Enhancement {bug_id} not found. Please select a valid bug ID."
                emit_to_client(socketio, client_id, answer,
                               end=True, final_end=True)
                yield answer
                enter_agent_response(
                    tenantID, userID, sessionID, f"Agent answer: {answer}")
                return

            serialized_bug = serialize_uuids(existing_bug)
            prompt = create_bug_enhancement_prompt(
                conv, users_json, tenantID, intent, serialized_bug)
            response = llm.run(prompt, model_opts,
                               'agent::manage_bug_enhancement', logInfo)
            response = extract_json_after_llm(response)
            print("manage_bug_enhancement ========", response)

            socketio.emit("agent_controlled_ui", response, room=client_id)

            final_prompt = final_output_prompt(
                conv, response, users_json, tenantID)
            answer = ''
            for chunk in llm.runWithStreaming(
                final_prompt,
                ModelOptions(model="gpt-4o", max_tokens=14000,
                             temperature=0.3),
                'tango::master::bug_enhancement_output',
                None
            ):
                emit_to_client(socketio, client_id, chunk)
                answer += chunk
            emit_to_client(socketio, client_id, "", end=True, final_end=True)
            yield answer
            enter_agent_response(tenantID, userID, sessionID,
                                 f"Agent answer: {answer}")
            return


RETURN_DESCRIPTION = """
    This function manages bugs/enhancements conversationally, prompting for intent (create, update, view) if unclear.
    Handles submissions for create/update, renders UI for create/update, and streams results for view.
    For update, first shows a list of bugs/enhancements, then allows selection and renders a form with all attributes.
"""

ARGUMENTS = []

MANAGE_BUG_ENHANCEMENT = AgentFunction(
    name="manage_bug_enhancement",
    description="""
        This function manages bugs/enhancements conversationally, detecting user intent (create, update, view, submit_create, submit_update) via LLM.
        If intent is unclear, it prompts the user. For 'view', it streams filtered results without UI; for 'create', it renders UI; for 'update', it shows a list first, then renders a full update form; for submissions, it persists data.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=manage_bug_enhancement,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name,
    return_type=AgentReturnTypes.YIELD.name
)


def create_bug_enhancement_prompt(conv, users_json, tenantID, intent, existing_bug=None):
    """
    Create a prompt for the LLM to decide which UI components to render for bug/enhancement tasks.
    :param conv: Conversation history
    :param users_json: JSON string of users in the tenant
    :param tenantID: Tenant ID
    :param intent: Detected intent ('create' or 'update')
    :param existing_bug: Existing bug data for prefilled update form (optional, UUIDs pre-serialized)
    :return: ChatCompletion object with system and user prompts
    """
    current_date = datetime.datetime.now().date().isoformat()

    # Fetch bugs/enhancements for the tenant (for update intent)
    bugs = BugEnhancementDao.fetch_bugs_by_tenant(tenant_id=tenantID)
    bugs_json = json.dumps([
        {"id": str(bug["id"]), "title": bug["title"]}  # Convert UUID to string
        for bug in bugs
    ])

    system_prompt = f"""
        You are a Customer Success Agent responsible for rendering UI components to facilitate tasks related to bugs and enhancements.
        The user's intent is: {intent}.
        Supported tasks:
        1. **Create** a new bug/enhancement.
        2. **Update** an existing bug/enhancement.

        ### Fields for Bugs/Enhancements
        - **Create**:
            - Type: 'bug' or 'enhancement' (dropdown)
            - Title: Short title (textbox)
            - Description: Detailed description (textarea)
            - Priority: 'low', 'medium', 'high', 'critical' (dropdown)
            - Assigned To: User ID from tenant (dropdown, optional)
        - **Update**:
            - Bug ID: UUID of the bug/enhancement (dropdown, populated from existing bugs)
            - Type: 'bug' or 'enhancement' (dropdown)
            - Title: Short title (textbox)
            - Description: Detailed description (textarea)
            - Priority: 'low', 'medium', 'high', 'critical' (dropdown)
            - Status: 'open', 'in_progress', 'resolved', 'closed' (dropdown)
            - Resolution Description: Text for resolved bugs (textarea, required if status='resolved')
            - Comments: Additional comments (textarea, optional)
            - Assigned To: User ID from tenant (dropdown, optional)
            - Resolved By: User ID from tenant (dropdown, required if status='resolved')

        ### Users in Tenant
        Available users: {users_json}

        ### Bugs/Enhancements in Tenant
        Available bugs/enhancements: {bugs_json}

        ### Existing Bug Data
        Existing bug (if provided): {json.dumps(existing_bug) if existing_bug else 'None'}

        ### Logic
        - For **Create**:
            - Render all fields (Type, Title, Description, Priority, Assigned To) in a single UI form.
            - If the conversation history contains submitted data (e.g., Type, Title), prefill those fields and ask for confirmation.
            - Example: If the user said "create a bug with high priority," prefill Priority with "high."
        - For **Update**:
            - If no Bug ID is provided in the conversation history or submitted data, render a dropdown of bug IDs using the provided bugs/enhancements list.
            - If a Bug ID is provided (e.g., user submitted "Bug ID": "123" or existing_bug is provided), render all fields (Type, Title, Description, Priority, Status, Resolution Description, Comments, Assigned To, Resolved By) prefilled with the existing bug's values.
            - Always include the Resolved By dropdown in the update form, but mark it as required only if Status is 'resolved' or set to 'resolved' in submitted data.
            - Prefill fields with existing bug data if provided, or use conversation history for partial updates (e.g., Status, Comments).
            - Ensure the bug ID dropdown includes both the ID and title for user clarity (e.g., "123 - Login Failure").

        ### Current Date
        {current_date}

        ### Output Format
        Return your output in this JSON-like format:
        ```json
        {{
            "your_thought": "<Your reasoning for choosing the UI>",
            "message_for_user": "<Message to display to the user>",
            "ui_instructions": [
                {{
                    "field_name": "<name_of_the_field>",
                    "ui_type": "<textbox|textarea|dropdown|date_picker|table>",
                    "placeholder": "<helpful_placeholder_text>",
                    "additional_metadata": {{
                        "options": ["<option1>", "<option2>"],           # For dropdown
                        "users": [{{"id": "", "username": ""}}],         # For user dropdowns
                        "bugs": [{{"id": "", "title": ""}}],             # For bug ID dropdown (update)
                        "required": <true|false>                         # Indicate if field is required
                    }},
                    "prefilled_value": "<value>"                         # Optional, for prefilled fields
                }}
            ]
        }}
        ```
        Based on the conversation history, intent, and existing bug data, decide which UI fields to render next. Return the output strictly in the JSON format defined above.
    """

    user_prompt = f"""
        Ongoing Conversation:
        <conv>
        {conv}
        <conv>

        User Intent: {intent}
        Existing Bug: {json.dumps(existing_bug) if existing_bug else 'None'}
        Decide wisely which UI should be rendered for creating or updating bugs/enhancements.
        For the update intent, render a Bug ID dropdown if no Bug ID is provided; otherwise, render a full update form with all fields prefilled from the existing bug data, including Resolved By.
    """

    return ChatCompletion(
        system=system_prompt,
        prev=[],
        user=user_prompt
    )


def final_output_prompt(conv, ui_response, users_json, tenantID):
    """
    Create a prompt for the LLM to generate a streamed, user-friendly text output summarizing the bug/enhancement action.
    """
    current_date = datetime.datetime.now().date().isoformat()
    system_prompt = f"""
        You are a Customer Success Agent tasked with generating a beautifully formatted, user-friendly text output to summarize the user's action related to bugs and enhancements.
        The user is either creating or updating a bug/enhancement.

        ### Context
        - **Conversation History**: {conv}
        - **UI Response**: {json.dumps(ui_response)}
        - **Users in Tenant**: {users_json}
        - **Current Date**: {current_date}

        ### Task
        Based on the UI response and conversation history, generate a concise, natural, and engaging text summary of the action being performed.
        The output should:
        - Reflect the task (create or update) inferred from the ui_instructions and conversation.
        - Highlight key details (e.g., bug title, status, assigned user, or resolved by user).
        - Be conversational and friendly, suitable for streaming to the user in real-time.
        - Avoid repeating the UI instructions verbatim; summarize the action in a narrative style.

        ### Output
        Return rich text that can be streamed to the user. Keep it concise (1-3 sentences) and engaging.
        Example:
        "You're creating a new bug! Please fill out the title, description, and priority."
        "You've selected a bug to update. Please update its status, comments, or other details, including who resolved it if applicable."
    """

    user_prompt = f"""
        Summarize the user's action based on the conversation history and UI response.
        Conversation: {conv}
        UI Response: {json.dumps(ui_response)}
        Generate a friendly, concise text summary for streaming.
    """

    return ChatCompletion(
        system=system_prompt,
        prev=[],
        user=user_prompt
    )


def final_output_prompt_for_view(conv, bugs, users_json, tenantID):
    """
    Create a prompt for the LLM to generate a user-friendly message for empty results or update flow.
    Table generation is handled in manage_bug_enhancement for consistency.
    """
    current_date = datetime.datetime.now().date().isoformat()
    serialized_bugs = serialize_uuids(bugs)

    system_prompt = f"""
        You are a Customer Success Agent tasked with generating a user-friendly text output for viewing bugs/enhancements.
        
        ### Context
        - **Conversation History**: {conv}
        - **Bugs/Enhancements**: {json.dumps(serialized_bugs)}
        - **Users in Tenant**: {users_json}
        - **Current Date**: {current_date}

        ### Task
        Generate a concise, natural, and engaging text message:
        - If no bugs are found, return a friendly message indicating no results match the filters.
        - If bugs are found and the user is in the update flow, prompt them to select a Bug ID after the table (table is generated elsewhere).
        - Do NOT generate the table here; it is handled in Python code.

        ### Output
        Return rich text that can be streamed to the user. Keep it concise.
        Examples:
        "No bugs or enhancements found. Would you like to create a new one?"
        "Please select a Bug ID to update."
    """

    user_prompt = f"""
        Generate a message based on the conversation history and retrieved data.
        Conversation: {conv}
        If the user is in the update flow, prompt them to select a Bug ID.
        Bugs: {json.dumps(serialized_bugs)}
        Generate a friendly, concise text message for streaming.
    """

    return ChatCompletion(
        system=system_prompt,
        prev=[],
        user=user_prompt
    )
