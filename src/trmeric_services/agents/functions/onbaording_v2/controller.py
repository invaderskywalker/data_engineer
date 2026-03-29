
from src.trmeric_database.dao import OnboardingDao, TangoDao, FileDao
from src.trmeric_api.logging.AppLogger import appLogger
import traceback
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_ml.llm.Types import ModelOptions
from .prompts import *
from .steps import ONBOARDING_STEPS, NEW_ONBOARDING_STEP
import uuid
from collections import OrderedDict
from src.trmeric_services.tango.functions.integrations.internal.UploadedFiles import UploadedFiles
from src.trmeric_s3.s3 import S3Service
from src.trmeric_database.Database import db_instance, TrmericDatabase
import json
from datetime import datetime
from .utils import SocketStepsSender
from src.trmeric_services.agents.core.agent_functions import AgentFunction,AgentFnTypes


class OnboardingV2Controller:
    def __init__(
        self,
        tenantID: int,
        userID: int,
        llm=None,
        model_opts=None,
        socketio=None,
        client_id=None,
        logInfo=None,
        data=None,
        initiate=False,
        click_mode=False,
        force_no_action=False,
        file_fetch=False,
        **kwargs
    ):
        print("in -- OnboardingV2Controller ", data, socketio)
        self.tenant_id = tenantID
        self.user_id = userID
        self.llm = llm
        self.model_opts = ModelOptions(
            model="gpt-4o",
            max_tokens=4096,
            temperature=0.4
        )
        self.socketio = socketio
        self.client_id = client_id
        self.log_info = logInfo

        self.onboarding_steps = []
        self.active_step = None
        self.session_id = None
        self.user_step = None
        self.user_sub_step = None
        self.last_user_message = None

        self.force_no_action = force_no_action
        self.file_fetch = file_fetch

        if data:
            self.user_step = data.get("user_step")
            self.user_sub_step = data.get("user_sub_step")
            self.last_user_message = data.get("message")

        print("debug ***1", self.user_step,
              self.active_step, self.force_no_action)
        self.fetchOrSaveLatestUserStep()
        print("debug ***2", self.user_step, self.active_step)

        if click_mode:
            self.update_steps_state_in_client(False, True)
        else:
            self.update_steps_state_in_client()

        if not self.force_no_action:
            if not self.file_fetch:
                print("debug ***3", self.user_step, self.active_step)
                if self.user_step == None and self.active_step:
                    self.user_step = self.active_step.get("step") or None

                self._set_session_id()

                if not self.chats_exist_in_session(self.session_id):
                    if not force_no_action:
                        self.chat()

    def chats_exist_in_session(self, session_id):
        conv = TangoDao.fetchCollaborativeChatAndFormat(
            session_id, self.tenant_id)
        # print("debug -- conv ", conv)
        return True if len(conv) > 0 else False

    def fetchOrSaveLatestUserStep(self):
        key = "latest_user_step_onboarding_v2"
        print("debug fetchOrSaveLatestUserStep ",
              self.user_step, self.user_sub_step)

        # Fetch latest step/substep if not already set
        if not self.user_step or not self.user_sub_step:
            item = TangoDao.fetchTangoStatesForTenantAndKey(
                tenant_id=self.tenant_id, key=key)
            if item:
                try:
                    # Assume item is a JSON string; parse it
                    data = json.loads(item) if isinstance(item, str) else item
                    self.user_step = data.get("step")
                    self.user_sub_step = data.get("sub_step")
                except Exception as e:
                    appLogger.error(
                        f"Error parsing latest user step: {str(e)}")

        print("debug 11**", self.user_step, self.user_sub_step)
        # Save step/substep if both are set
        if self.user_step and self.user_sub_step:
            try:
                # Validate that step/substep exist in ONBOARDING_STEPS
                if not any(
                    step_info["step"] == self.user_step and step_info["sub_step"] == self.user_sub_step
                    for step_info in ONBOARDING_STEPS
                ):
                    appLogger.warning(
                        f"Invalid step/substep: {self.user_step}/{self.user_sub_step}")
                    return

                first_sub_step = None
                for step_info in ONBOARDING_STEPS:
                    if step_info["step"] == self.user_step:
                        first_sub_step = step_info["sub_step"]
                        break

                data = {
                    "step": self.user_step,
                    "sub_step": first_sub_step,
                    # "timestamp": datetime.now().isoformat()
                }
                TangoDao.insertTangoState(
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    key=key,
                    value=json.dumps(data),
                    session_id=self.session_id or ""  # Use actual session_id if available
                )
            except Exception as e:
                appLogger.error(f"Error saving user step: {str(e)}")

    def _set_session_id(self):
        if self.user_step:
            # Use the first substep from ONBOARDING_STEPS
            first_sub_step = None
            for step_info in ONBOARDING_STEPS:
                if step_info["step"] == self.user_step:
                    first_sub_step = step_info["sub_step"]
                    break

            if first_sub_step:
                # Find session_id for this step and first substep
                for step in self.onboarding_steps:
                    if (step.get("step") == self.user_step and
                            step.get("sub_step") == first_sub_step):
                        self.session_id = step.get("session_id")
                        # Ensure user_sub_step is set to first substep
                        self.user_sub_step = first_sub_step
                        appLogger.info(
                            f"Using first substep {self.user_sub_step} for step {self.user_step}")
                        break
                else:
                    appLogger.warning(
                        f"No session_id found for step/substep: {self.user_step}/{first_sub_step}"
                    )
                    raise Exception(
                        f"No session_id found for step/substep: {self.user_step}/{first_sub_step}"
                    )
            else:
                appLogger.warning(
                    f"No substeps found for user_step: {self.user_step}")
                raise Exception(
                    f"No substeps found for user_step: {self.user_step}")
        else:
            # Default to the first step/substep from onboarding_steps
            if self.onboarding_steps:
                first_step = self.onboarding_steps[0]
                self.session_id = first_step.get("session_id")
                # Optionally set user_step and user_sub_step if needed
                # self.user_step = first_step.get("step")
                # self.user_sub_step = first_step.get("sub_step")
                appLogger.info(
                    f"No user step provided; defaulting to {self.user_step}/{self.user_sub_step}"
                )
            else:
                appLogger.error("No onboarding steps detected in database")
                raise Exception("No onboarding steps detected")

    def fetch_onboarding_v2_info(self, skip=False, clicked=False):
        appLogger.info(f"Fetching onboarding info, skip={skip}")
        # Fetch or create onboarding info entry
        onboarding_info = OnboardingDao.getOnboardingV2EntryOfTenant(
            self.tenant_id)
        if not onboarding_info:  # Check if empty instead of len == 0
            onboarding_data = "{}"  # Default empty JSON
            OnboardingDao.insertEntryToOnboardingV2Info(
                self.tenant_id, self.user_id, onboarding_data)
            onboarding_info = OnboardingDao.getOnboardingV2EntryOfTenant(
                self.tenant_id)

        onboarding_id = onboarding_info[0].get("id")
        steps_from_db = OnboardingDao.getOnboardingV2Steps(onboarding_id)

        # Convert DB steps to a set of (step, sub_step) tuples for comparison
        db_step_set = {(step.get("step"), step.get("sub_step"))
                       for step in steps_from_db}

        # Group steps by step name and maintain session IDs
        step_groups = {}
        for step_info in steps_from_db:
            step_name = step_info.get("step")
            if step_name not in step_groups:
                step_groups[step_name] = step_info.get("session_id")

        STEPS = ONBOARDING_STEPS + NEW_ONBOARDING_STEP
        # Check and add missing steps from ONBOARDING_STEPS
        for step_info in STEPS:
            step_name = step_info.get("step")
            sub_step = step_info.get("sub_step")

            if (step_name, sub_step) not in db_step_set:
                # If this step group doesn't have a session ID yet, create one
                if step_name not in step_groups:
                    step_groups[step_name] = str(uuid.uuid4())

                # Insert the missing step with the group's session ID
                self.insert_step_info_in_db(
                    onboarding_id,
                    step_name,
                    sub_step,
                    step_groups[step_name]
                )

        # Refresh steps from DB after potential insertions
        steps_from_db = OnboardingDao.getOnboardingV2Steps(onboarding_id)

        # Sort steps to match ONBOARDING_STEPS order
        step_order = {f"{step['step']}/{step['sub_step']}": idx for idx,
                      step in enumerate(ONBOARDING_STEPS)}
        self.onboarding_steps = sorted(
            steps_from_db,
            key=lambda x: step_order.get(
                f"{x.get('step')}/{x.get('sub_step')}", len(step_order))
        )
        # appLogger.info(f"Sorted onboarding_steps: {[f'{s['step']}/{s['sub_step']}' for s in self.onboarding_steps]}")

        # Set active step if not skipping
        if not skip:
            self.active_step = None
            appLogger.info(
                f"Setting active_step: user_step={self.user_step}, user_sub_step={self.user_sub_step}")

            # Try to set active_step to user-selected step/sub-step if pending
            if self.user_step and self.user_sub_step:
                found = False
                for step in self.onboarding_steps:
                    # print("step ---- step --- ", step.get("step"), step.get("sub_step"), step.get("state"))
                    if clicked:
                        if (
                            step.get("step") == self.user_step and
                            step.get("sub_step") == self.user_sub_step
                            # and step.get("state") == "pending"
                        ):
                            self.active_step = step
                            appLogger.info(
                                f"Set active_step to user-selected: {self.user_step}/{self.user_sub_step}")
                            break
                    else:
                        found = False

                        def key_match(step): return (
                            step.get("step") == self.user_step and
                            step.get("sub_step") == self.user_sub_step
                        )

                        for step in self.onboarding_steps:
                            # print("step ---- step --- ", step.get("step"), step.get("sub_step"), step.get("state"))
                            if key_match(step):
                                found = True
                                appLogger.info(
                                    f"Found user step to user-selected: {self.user_step}/{self.user_sub_step}")
                            elif found and step.get("state") == "pending":
                                self.active_step = step
                                appLogger.info(
                                    f"Selected active step to user-selected: {self.user_step}/{self.user_sub_step}")
                                break

            # Fallback to first pending step if no valid user selection
            if not self.active_step:
                for step in self.onboarding_steps:
                    if step.get("state") == "pending":
                        self.active_step = step
                        appLogger.info(
                            f"Set active_step to first pending: {step.get('step')}/{step.get('sub_step')}")
                        break

            if not self.active_step:
                appLogger.warning(
                    "No pending steps found; active_step remains None")

            # self.socketio.emit("onboarding_v2_agent", {
            #     "event": "active_step",
            #     "data": self.active_step
            # }, room=self.client_id)

    def insert_step_info_in_db(self, onboarding_id, step, sub_step, session_id):
        OnboardingDao.insertEntryOnboardingV2Step(
            onboarding_id, step, sub_step, session_id)

    def update_step_info_in_db(self, onboarding_id, step, sub_step, state):
        OnboardingDao.updateEntryOnboardingV2Step(
            onboarding_id, step, sub_step, state)

    def update_steps_state_in_client(self, skip=False, clicked=False):
        self.fetch_onboarding_v2_info(skip=skip, clicked=clicked)

        transformed_data = self._transform_onboarding_steps(
            self.onboarding_steps)

        if self.socketio and not self.force_no_action:
            if not self.file_fetch:
                self.socketio.emit("onboarding_v2_agent", {
                    "event": "refresh_steps_info",
                    "data": transformed_data
                }, room=self.client_id)

                self.socketio.emit("onboarding_v2_agent", {
                    "event": "active_step",
                    "data": self.active_step
                }, room=self.client_id)

        if self.force_no_action:
            if not self.file_fetch:
                found_step = {}
                for step in self.onboarding_steps:
                    if (step.get("step") == "general_section"):
                        self.session_id = step.get("session_id")
                        found_step = step
                        appLogger.info(
                            f"Found session id for general section")
                        break
                if self.socketio:
                    self.socketio.emit("onboarding_v2_agent", {
                        "event": "initiate_onboarding_checklist",
                        "data": found_step
                    }, room=self.client_id)

    def _transform_onboarding_steps(self, onboarding_steps):
        # Helper function to capitalize first letter of each word
        def capitalize_words(text):
            return " ".join(word.capitalize() for word in text.split("_"))

        # print("onboarding_steps", onboarding_steps)
        grouped_steps = OrderedDict()
        for step_data in onboarding_steps:
            step = step_data.get("step")
            if step not in grouped_steps:
                grouped_steps[step] = []
            grouped_steps[step].append(step_data)

        # Transform into the desired structure
        transformed_data = []
        for step, sub_steps in grouped_steps.items():
            # Create the step object
            step_obj = {
                "title": capitalize_words(step),
                "key": step,  # Use step directly as key
                # Random placeholder (e.g., "icon_cus")
                "icon": "icon_" + step,
                "activeIcon": "icon_" + step + "_active",  # Random active placeholder
                "items": []
            }

            # Add items for each sub_step
            for sub_step_data in sub_steps:
                sub_step = sub_step_data.get("sub_step")
                state = sub_step_data.get("state")
                item = {
                    "id": sub_step_data.get("id") or 0,
                    "name": capitalize_words(sub_step),
                    "key": sub_step.upper(),  # Uppercase sub_step as key (e.g., "LOCATION_AND_CURRENCY")
                    "files_required": "PDF",  # Default placeholder, can be customized later
                    "completed": state == "done",  # True if "done", False if "pending"
                    "saved": sub_step_data.get("saved")
                }
                step_obj["items"].append(item)

            step_obj["items"] = sorted(
                step_obj["items"], key=lambda x: x["id"])
            transformed_data.append(step_obj)

        # print("transformed_data", transformed_data)
        transformed_data = sorted(transformed_data, key=lambda x: min(
            item["id"] for item in x["items"]))

        return transformed_data

    def deleteEntryOnboardingV2Step(self):
        onboarding_id = OnboardingDao.getOnboardingV2EntryOfTenant(self.tenant_id)[
            0].get("id")
        OnboardingDao.deleteEntryOnboardingV2Step(onboarding_id)

    def saveOnboardingV2StepProgress(self):
        onboarding_id = OnboardingDao.getOnboardingV2EntryOfTenant(self.tenant_id)[
            0].get("id")
        steps = OnboardingDao.getOnboardingV2Steps(onboarding_id)

        for step in steps:
            if step.get("state") == "done":
                query = """
                    UPDATE tango_onboardingv2step 
                    SET saved = %s, updated_at = NOW()
                    WHERE onboarding_id = %s 
                    AND step = %s 
                    AND sub_step = %s
                """
                params = (True, onboarding_id, step.get(
                    "step"), step.get("sub_step"))
                db_instance.executeSQLQuery(query, params)

        # Update the client with the latest state
        # self.update_steps_state_in_client(True)

    def get_uploaded_files_by_substep(self):
        """
        Returns a dictionary of uploaded files organized by step and sub-step for all onboarding steps,
        including those without uploaded files.
        """
        try:
            # Fetch onboarding info
            onboarding_info = OnboardingDao.getOnboardingV2EntryOfTenant(
                self.tenant_id)
            if not onboarding_info:
                # If no onboarding info exists, create it to ensure steps are populated
                onboarding_data = "{}"
                OnboardingDao.insertEntryToOnboardingV2Info(
                    self.tenant_id, self.user_id, onboarding_data)
                onboarding_info = OnboardingDao.getOnboardingV2EntryOfTenant(
                    self.tenant_id)

            onboarding_id = onboarding_info[0].get("id")
            steps_from_db = OnboardingDao.getOnboardingV2Steps(onboarding_id)

            # Ensure all steps from ONBOARDING_STEPS are in the database
            db_step_set = {(step.get("step"), step.get("sub_step"))
                           for step in steps_from_db}
            step_groups = {}
            for step_info in steps_from_db:
                step_name = step_info.get("step")
                if step_name not in step_groups:
                    step_groups[step_name] = step_info.get("session_id")

            STEPS = ONBOARDING_STEPS + NEW_ONBOARDING_STEP
            for step_info in STEPS:
                step_name = step_info.get("step")
                sub_step = step_info.get("sub_step")
                if (step_name, sub_step) not in db_step_set:
                    if step_name not in step_groups:
                        step_groups[step_name] = str(uuid.uuid4())
                    self.insert_step_info_in_db(
                        onboarding_id,
                        step_name,
                        sub_step,
                        step_groups[step_name]
                    )

            # Refresh steps from DB after potential insertions
            steps_from_db = OnboardingDao.getOnboardingV2Steps(onboarding_id)
            # print("stepppp ", steps_from_db)
            # Build a mapping of session_id to step/substep info
            session_to_steps = {}
            for step in steps_from_db:
                session_id = step.get("session_id")
                step_name = step.get("step")
                sub_step = step.get("sub_step")
                if session_id not in session_to_steps:
                    session_to_steps[session_id] = []
                session_to_steps[session_id].append({
                    "step": step_name,
                    "sub_step": sub_step,
                    "file_key": f"ONBOARDING_V2_file_upload_{step_name}_{sub_step}"
                })

            # print("stedebug pppp ", session_to_steps)

            # Fetch files for each session_id and organize them
            session_files = {}
            for session_id, steps_info in session_to_steps.items():
                files = FileDao.FilesUploadedInS3ForSession(
                    sessionID=session_id) or []
                # print("stepppp ", session_id, steps_info, files)
                session_files[session_id] = {}

                for step_info in steps_info:
                    step_name = step_info["step"]
                    sub_step = step_info["sub_step"]
                    file_key = step_info["file_key"]

                    # print("stedebug ooo ", step_name, sub_step, file_key)

                    if step_name not in session_files[session_id]:
                        session_files[session_id][step_name] = {}
                    matching_files = [
                        f for f in files
                        if isinstance(f, dict) and f.get("file_type", "").lower().startswith(file_key.lower())
                    ]
                    # print("stedebug ooo ", matching_files)
                    session_files[session_id][step_name][sub_step] = matching_files

            # Build the result with all steps/substeps from ONBOARDING_STEPS
            result = {}
            for step_info in STEPS:
                step_name = step_info["step"]
                sub_step = step_info["sub_step"]
                if step_name not in result:
                    result[step_name] = {}

                # Find the session_id for this step/substep
                session_id = next(
                    (s.get("session_id") for s in steps_from_db
                     if s.get("step") == step_name and s.get("sub_step") == sub_step),
                    None
                )

                # Get files if they exist, otherwise empty list
                files = []
                if session_id and session_id in session_files and step_name in session_files[session_id]:
                    files = session_files[session_id][step_name].get(
                        sub_step, [])

                for f in files:
                    f["url"] = S3Service().generate_presigned_url(f["s3_key"])

                result[step_name][sub_step] = files

            print("knowledge data --- ", result)
            # return {
            #     "status": "success",
            #     "data": result
            # }
            return result

        except Exception as e:
            appLogger.error(
                f"Error in get_uploaded_files_by_substep: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "data": {},
                "traceback": traceback.format_exc()
            }

    def chat(self):
        files = FileDao.FilesUploadedInS3ForSession(sessionID=self.session_id)
        print("file uploaded .. ", files)
        chat_key = "onboarding_v2_chat"
        session_id = self.session_id

        steps_sender_class = SocketStepsSender(
            agent_name="onboarding_v2_agent", socketio=self.socketio, client_id=self.client_id)

        file_content = None
        # if files:
        #     first_file = files[0]  # Take the first file for this example
        #     file_id = first_file.get("s3_key")
        #     file_id = "0041fbda-5160-446a-ae23-e2ab7eb3b89b"
        #     try:
        #         file_content = S3Service().download_file_as_pd(file_id)
        #         print(f"Downloaded file content for file_id {file_id}: {file_content[:100]}...")  # Print first 100 chars
        #     except Exception as e:
        #         print(f"Error downloading file with file_id {file_id}: {str(e)}")

        if self.last_user_message:
            step_number = 1
            params = (
                self.tenant_id,
                self.user_id,
                self.last_user_message,
                session_id,
                step_number
            )
            TangoDao.insertToCollaborativeChat(params)

        self.socketio.emit(
            "onboarding_v2_agent",
            {
                "event": "show_timeline"
            },
            room=self.client_id
        )
        steps_sender_class.sendSteps("Analysing", False)

        conv = TangoDao.fetchCollaborativeChatAndFormat(
            session_id, self.tenant_id)
        files_uploaded_in_this_conv_by_user = f"""
        ------------FILE UPLOADED IN THIS CHAT-------------
        {files}
        ------------------------------------
        """
        prompt = generic_step_prompt(
            self.user_step, conv, extra=files_uploaded_in_this_conv_by_user)
        response = self.llm.run(prompt, self.model_opts,
                                'agent::onboarding_v2::thought', self.log_info)
        print("prompt and response ========",  response)

        steps_sender_class.sendSteps("Analysing", True)

        step_number = 2
        params = (
            self.tenant_id,
            self.user_id,
            response,
            session_id,
            step_number
        )
        TangoDao.insertToCollaborativeChat(params)

        # Parse LLM response
        try:
            response_json = extract_json_after_llm(response)
            active_sub_step = response_json.get("active_sub_step")
            sub_steps_status = response_json.get("sub_steps_status")

            user_intent = response_json.get(
                "user_intent")  # Extract user_intent here

            onboarding_id = OnboardingDao.getOnboardingV2EntryOfTenant(self.tenant_id)[
                0].get("id")

            # Update database based on sub_steps_status
            if sub_steps_status and self.last_user_message:
                for sub_step, status in sub_steps_status.items():
                    print("debug ---- *** ", sub_step, status)
                    if status == "done":
                        self.update_step_info_in_db(
                            onboarding_id, self.user_step, sub_step, "done")

            self.update_steps_state_in_client(True)
        except Exception as e:
            print("error", e)

        steps_sender_class.sendSteps("Generating Output", False)
        response_json = extract_json_after_llm(response)
        newPrompt = final_output_prompt(response_json, conv, self.user_step)
        # print("prompt final_output_prompt --- ", newPrompt.formatAsString())
        stringData = ""

        self.socketio.emit(
            "onboarding_v2_agent",
            {
                "event": "stop_show_timeline"
            },
            room=self.client_id
        )

        for chunk in self.llm.runWithStreaming(newPrompt, self.model_opts, 'agent::onboarding_v2::response', self.log_info):
            stringData += chunk
            self.socketio.emit("onboarding_v2_response",
                               chunk, room=self.client_id)

        self.socketio.emit("onboarding_v2_response",
                           "<end>", room=self.client_id)
        self.socketio.emit("onboarding_v2_response",
                           "<<end>>", room=self.client_id)

        # steps_sender_class.sendSteps("Generating Output", True)

        # self.socketio.emit(
        #     "onboarding_v2_agent",
        #     {
        #         "event": "stop_show_timeline"
        #     },
        #     room=self.client_id
        # )

        print("response ===final=====", stringData)

        step_number = 3
        params = (
            self.tenant_id,
            self.user_id,
            stringData,
            session_id,
            step_number
        )
        TangoDao.insertToCollaborativeChat(params)
        self.update_steps_state_in_client(True)


class OnboardingV3Controller:
    def __init__(
        self,
        tenantID: int,
        userID: int,
        llm=None,
        model_opts=None,
        socketio=None,
        client_id=None,
        logInfo=None,
        data=None,
        **kwargs
    ):
        print("in -- OnboardingV3Controller ", data, socketio)
        self.tenant_id = tenantID
        self.user_id = userID
        self.llm = llm
        self.model_opts = ModelOptions(
            model="gpt-4o",
            max_tokens=4096,
            temperature=0.4
        )
        self.socketio = socketio
        self.client_id = client_id
        self.log_info = logInfo

        self.onboarding_steps = []
        self.active_step = None
        self.session_id = None
        self.user_step = None
        self.user_sub_step = None
        self.last_user_message = None

        if data:
            self.user_step = data.get("user_step")
            self.user_sub_step = data.get("user_sub_step")
            self.last_user_message = data.get("message")

        self.controller_v2 = OnboardingV2Controller(
            tenantID=tenantID,
            userID=userID,
            llm=llm,
            model_opt=model_opts,
            logInfo=logInfo,
            socketio=socketio,
            client_id=client_id,
            data=data,
            force_no_action=True
        )

        for step in self.controller_v2.onboarding_steps:
            if (step.get("step") == "general_section"):
                self.session_id = step.get("session_id")
                appLogger.info(
                    f"Found session id for general section")
                break

        conv = TangoDao.fetchCollaborativeChatAndFormat(
            self.session_id, self.tenant_id)

        if len(conv) == 0:
            step_number = 3
            messages = [
                f"""Welcome to trmeric onboarding ! I am Tango, your AI assistant and I will help you through onboarding process.
                First, let's understand a bit about your organization so we can tailor the experience to you.
                
You can Skip the step-by-step process by uploading all your files at once. 
Your files will be used to build your knowledge base.
```json
{{
    "cta_buttons": [
        {{
            "label": "Lets go step-by-step",
            "key": "old_flow"
        }}
    ],
    "showDropper": true
}}
```
"""
            ]
            for msg in messages:
                params = (
                    self.tenant_id,
                    self.user_id,
                    msg,
                    self.session_id,
                    step_number
                )
                TangoDao.insertToCollaborativeChat(params)

        self.controller_v2.update_steps_state_in_client()

    def chat(self):
        files = FileDao.FilesUploadedInS3ForSession(sessionID=self.session_id)
        print("file uploaded .. ", files)
        chat_key = "onboarding_v2_chat"
        session_id = self.session_id

        steps_sender_class = SocketStepsSender(
            agent_name="onboarding_v2_agent", socketio=self.socketio, client_id=self.client_id)

        file_content = None

        if self.last_user_message:
            step_number = 1
            params = (
                self.tenant_id,
                self.user_id,
                self.last_user_message,
                session_id,
                step_number
            )
            TangoDao.insertToCollaborativeChat(params)

        self.socketio.emit(
            "onboarding_v2_agent",
            {
                "event": "show_timeline"
            },
            room=self.client_id
        )
        steps_sender_class.sendSteps("Analysing", False)

        conv = TangoDao.fetchCollaborativeChatAndFormat(
            session_id, self.tenant_id)
        files_uploaded_in_this_conv_by_user = f"""
        ------------FILE UPLOADED IN THIS CHAT-------------
        {files}
        ------------------------------------
        """

        steps_sender_class.sendSteps("Analysing", True)
        steps_sender_class.sendSteps("Generating Output", False)
        newPrompt = final_output_prompt_generic(
            conv, files_uploaded_in_this_conv_by_user)
        stringData = ""

        print("debug ... ", newPrompt.formatAsString())

        self.socketio.emit(
            "onboarding_v2_agent",
            {
                "event": "stop_show_timeline"
            },
            room=self.client_id
        )

        for chunk in self.llm.runWithStreaming(newPrompt, self.model_opts, 'agent::onboarding_v2::response', self.log_info):
            stringData += chunk
            self.socketio.emit("onboarding_v2_response",
                               chunk, room=self.client_id)

        chunk += f"""
```json
{{
    "cta_buttons": [
        {{
            "label": "Lets go step-by-step",
            "key": "old_flow"
        }}
    ],
    "showDropper": true
}}
```
"""
        stringData += chunk
        self.socketio.emit("onboarding_v2_response",
                           chunk, room=self.client_id)

        self.socketio.emit("onboarding_v2_response",
                           "<end>", room=self.client_id)
        self.socketio.emit("onboarding_v2_response",
                           "<<end>>", room=self.client_id)

        # print("response ===final=====", stringData)

        step_number = 3
        params = (
            self.tenant_id,
            self.user_id,
            stringData,
            session_id,
            step_number
        )
        TangoDao.insertToCollaborativeChat(params)
        # self.update_steps_state_in_client(True)


def onboarding_controller(
    tenantID: int,
    userID: int,
    llm=None,
    model_opts=None,
    socketio=None,
    client_id=None,
    logInfo=None,
    data=None,
    initiate=False,
    sessionID = None,
    **kwargs
):
    print("onboarding_controller", model_opts, data)
    try:
        controller = OnboardingV2Controller(
            tenantID=tenantID,
            userID=userID,
            llm=llm,
            model_opt=model_opts,
            logInfo=logInfo,
            socketio=socketio,
            client_id=client_id,
            data=data,
            initiate=initiate
        )
        controller.chat()
    except Exception as e:
        print("error in onboarding_controller ", e, traceback.format_exc())


def onboarding_controller_v3(
    tenantID: int,
    userID: int,
    llm=None,
    model_opts=None,
    socketio=None,
    client_id=None,
    logInfo=None,
    data=None,
    initiate=False,
    sessionID = None,
    **kwargs
):
    print("onboarding_controller_v3", model_opts, data)
    try:
        controllerV3 = OnboardingV3Controller(
            tenantID=tenantID,
            userID=userID,
            llm=llm,
            model_opt=model_opts,
            logInfo=logInfo,
            socketio=socketio,
            client_id=client_id,
            data=data
        )
        controllerV3.chat()
    except Exception as e:
        print("error in onboarding_controller_v3 ", e, traceback.format_exc())


def fetch_states_v3(
    tenantID: int,
    userID: int,
    llm=None,
    model_opts=None,
    socketio=None,
    client_id=None,
    logInfo=None,
    data=None,
    initiate=False,
    sessionID = None,
    **kwargs
):
    print("fetch_states_v3", model_opts, data)
    try:
        controllerV3 = OnboardingV3Controller(
            tenantID=tenantID,
            userID=userID,
            llm=llm,
            model_opt=model_opts,
            logInfo=logInfo,
            socketio=socketio,
            client_id=client_id,
            data=data
        )
    except Exception as e:
        print("error in onboarding_controller_v3 ", e, traceback.format_exc())


def fetch_states(
    tenantID: int,
    userID: int,
    llm=None,
    model_opts=None,
    socketio=None,
    client_id=None,
    logInfo=None,
    data=None,
    initiate=False,
    sessionID = None,
    **kwargs
):
    print("fetch_states", model_opts, data)
    try:
        controller = OnboardingV2Controller(
            tenantID=tenantID,
            userID=userID,
            llm=llm,
            model_opt=model_opts,
            logInfo=logInfo,
            socketio=socketio,
            client_id=client_id,
            data=data,
            initiate=initiate,
            click_mode=True
        )
        controller.update_steps_state_in_client(False, True)
    except Exception as e:
        print("error in onboarding_controller ", e, traceback.format_exc())


def discrad_progress(
    tenantID: int,
    userID: int,
    llm=None,
    model_opts=None,
    socketio=None,
    client_id=None,
    logInfo=None,
    data=None,
    initiate=False,
    sessionID = None,
    **kwargs
):
    print("discard_states", model_opts, data)
    try:
        controller = OnboardingV2Controller(
            tenantID=tenantID,
            userID=userID,
            llm=llm,
            model_opt=model_opts,
            logInfo=logInfo,
            socketio=socketio,
            client_id=client_id,
            data=data,
            initiate=initiate
        )
        controller.deleteEntryOnboardingV2Step()
        fetch_states(
            tenantID=tenantID,
            userID=userID,
            llm=llm,
            model_opts=model_opts,
            logInfo=logInfo,
            socketio=socketio,
            client_id=client_id,
            data=data,
            initiate=initiate
        )
    except Exception as e:
        print("error in onboarding_controller discrad_progress ",
              e, traceback.format_exc())


def save_progress(
    tenantID: int,
    userID: int,
    llm=None,
    model_opts=None,
    socketio=None,
    client_id=None,
    logInfo=None,
    data=None,
    initiate=False,
    sessionID = None,
    **kwargs
):
    print("save_progress", model_opts, data)
    try:
        controller = OnboardingV2Controller(
            tenantID=tenantID,
            userID=userID,
            llm=llm,
            model_opt=model_opts,
            logInfo=logInfo,
            socketio=socketio,
            client_id=client_id,
            data=data,
            initiate=initiate
        )
        controller.saveOnboardingV2StepProgress()
        fetch_states(
            tenantID=tenantID,
            userID=userID,
            llm=llm,
            model_opts=model_opts,
            logInfo=logInfo,
            socketio=socketio,
            client_id=client_id,
            data=data,
            initiate=initiate
        )
    except Exception as e:
        print("error in onboarding_controller save_progress ",
              e, traceback.format_exc())


def fetch_uploaded_file(tenant_id: int, user_id: int):
    # print("fetch_uploaded_file")
    try:
        controller = OnboardingV2Controller(
            tenantID=tenant_id,
            userID=user_id,
            force_no_action=True,
            file_fetch=True
        )
        return controller.get_uploaded_files_by_substep()
    except Exception as e:
        print("error in onboarding_controller save_progress ",
              e, traceback.format_exc())







FETCH_STATES_V3 = AgentFunction(
    name="fetch_states_v3",
    description="""
        This function fetches version 3 states for a given process or system.
    """,
    args=[],
    return_description="",
    function=fetch_states_v3,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

ONBOARDING_CONTROLLER = AgentFunction(
    name="onboarding_controller",
    description="""
        This function handles the onboarding process for a user or system.
    """,
    args=[],
    return_description="",
    function=onboarding_controller,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

ONBOARDING_CONTROLLER_V3 = AgentFunction(
    name="onboarding_controller_v3",
    description="""
        This function handles version 3 of the onboarding process for a user or system.
    """,
    args=[],
    return_description="",
    function=onboarding_controller_v3,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

FETCH_STATES = AgentFunction(
    name="fetch_states",
    description="""
        This function fetches states for a given process or system.
    """,
    args=[],
    return_description="",
    function=fetch_states,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

DISCARD_PROGRESS = AgentFunction(
    name="discard_progress",
    description="""
        This function discards the current progress of a process or system.
    """,
    args=[],
    return_description="",
    function=discrad_progress,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)

SAVE_PROGRESS = AgentFunction(
    name="save_progress",
    description="""
        This function saves the current progress of a process or system.
    """,
    args=[],
    return_description="",
    function=save_progress,
    type_of_func=AgentFnTypes.ACTION_TAKER_UI.name
)