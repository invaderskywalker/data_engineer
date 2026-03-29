from typing import Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_utils.enums import AgentFnTypes, AgentReturnTypes
from src.trmeric_database.dao import TangoDao
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.models.OpenAIClient import ModelOptions
from src.trmeric_services.project.projectService import ProjectService
import json
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.agents.functions.onboarding.creation_tools.AutonomousCreateProject import AutomousProjectAgent
import traceback

class ProjectCreationAgent:
    """Agent for creating multiple projects from plain text project descriptions in conversation."""

    def __init__(self, llm: Any):
        """Initialize with an LLM instance."""
        self.llm = llm
        self.model_opts = ModelOptions(model="gpt-4.1", max_tokens=30000, temperature=0.2)

    def validate_project_description(
        self,
        project_description: str,
        log_info: Dict
    ) -> List[Dict[str, Any]]:
        """Validate and parse multiple project descriptions into JSON drafts.

        Args:
            project_description: Plain text containing one or more project descriptions.
            log_info: Logging information.

        Returns:
            Array of dicts, each with is_valid, draft (if valid), and message (if invalid).
        """
        prompt = ChatCompletion(
            system=f"""
                You are an assistant validating and parsing multiple project descriptions for Trmeric projects.

                # Input
                - Project Description: {project_description}

                # Task
                - Identify and separate multiple project descriptions in the input text, regardless of format (e.g., separated by newlines, bullets, or free text).
                - For each description:
                  - Check if it contains project-like data (e.g., title, description, objectives, technologies).
                  - If valid, parse into a JSON draft with:
                    - title: Project title.
                    - description: Narrative (150–500 words).
                    - objectives: 3–5 actionable goals as a list.
                    - tech_stack: Suitable technologies as a list.
                    - business_impact: Expected impact.
                  - If invalid, provide a reason why it’s not a valid project description.
                - Return an array of JSON objects, each with:
                  - is_valid: Boolean.
                  - draft: JSON draft (if valid, else empty).
                  - message: Reason or prompt (if invalid).

                # Output Format
                ```json
                [
                    {{
                        "is_valid": <boolean>,
                        "draft": {{"title": "<string>", "description": "<string>", "objectives": ["<string>", ...], "tech_stack": ["<string>", ...], "business_impact": "<string>"}} or {{}},
                        "message": "<string>"
                    }},
                    ...
                ]
                ```
            """,
            prev=[],
            user="Validate and parse the project descriptions into JSON drafts."
        )

        try:
            response = self.llm.runV2(
                prompt, self.model_opts, 'agent::project::validate_description', log_info
            )
            result = self._extract_json(response)
            if not result or not isinstance(result, list):
                raise ValueError("Invalid LLM response; expected an array")
            appLogger.info(f"Validated {len(result)} project descriptions")
            return result
        except Exception as e:
            appLogger.error(f"Description validation error: {e}")
            return [
                {
                    "is_valid": False,
                    "draft": {},
                    "message": f"Failed to validate descriptions: {str(e)}. Please provide project descriptions with title, description, objectives, and technologies."
                }
            ]

    def create_project(
        self,
        draft: Dict,
        tenant_id: str,
        user_id: str,
        log_info: Dict
    ) -> Tuple[Dict, str]:
        """Create a single project.

        Args:
            draft: Project draft data (dictionary).
            tenant_id: Tenant ID.
            user_id: User ID.
            log_info: Logging information.

        Returns:
            Tuple of (project_response, error_message).
        """
        try:
            project_service = ProjectService()
            response = ProjectService().createProjectV2(
                tenant_id=tenant_id,
                project_name=draft.get("title", "") or "",
                project_description=draft,
                is_provider=False,
                log_input=log_info
            )
            print("project created -- ", response)
            
            mapping_data = AutomousProjectAgent().only_request_creation(
                request_data=response,
                tenantId=tenant_id,
                userId=user_id
            )
            
            print("data created  -- ", mapping_data)
    
            # appLogger.info(f"Created project: {response.get('project_id')}")
            return response, ""
        except Exception as e:
            appLogger.error({"error": e, "traceback": traceback.format_exc(), "event": "faoiled project creation"})
            return {}, str(e)

    def process_project(
        self,
        conversation: List[str],
        last_user_message: str,
        tenant_id: str,
        user_id: str,
        log_info: Dict
    ) -> List[str]:
        """Process multiple plain text project descriptions and create projects one by one.

        Args:
            conversation: List of conversation history strings.
            last_user_message: Latest user message.
            tenant_id: Tenant ID.
            user_id: User ID.
            log_info: Logging information.

        Returns:
            List of result messages, including prompt for more data.
        """
        results = []

        # Get the latest project description
        project_description = last_user_message if last_user_message else ""
        if not project_description and conversation:
            project_description = conversation[0]

        if not project_description:
            appLogger.warning("No project description provided")
            results.append("Error: Please provide one or more project descriptions.")
            results.append("Provide project descriptions (e.g., title, description, objectives, technologies) to create projects.")
            return results

        print("debug here 1")
        # Validate descriptions and get array of results
        validation_results = self.validate_project_description(project_description, log_info)
        if not validation_results:
            appLogger.warning("No project descriptions validated")
            results.append("Error: No project descriptions found.")
            results.append("Provide project descriptions (e.g., title, description, objectives, technologies) to create projects.")
            return results

        # Collect valid drafts and report invalid ones
        valid_drafts = []
        for validation in validation_results:
            if validation["is_valid"]:
                valid_drafts.append(validation["draft"])
            else:
                results.append(f"Invalid description: {validation['message']}")

        if not valid_drafts:
            appLogger.warning("No valid drafts to process")
            results.append("No valid project descriptions to create.")
            results.append("Provide valid project descriptions to continue.")
            return results
        
        print("debug here 2", validation_results)
        print("debug here 3", valid_drafts)

        # Create projects one by one using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(len(valid_drafts), 3)) as executor:
            futures = [
                executor.submit(
                    self.create_project,
                    draft,
                    tenant_id,
                    user_id,
                    log_info
                )
                for draft in valid_drafts
            ]

            for future in as_completed(futures):
                try:
                    response, error = future.result()
                    if error:
                        results.append(f"Failed to create project: {error}")
                    else:
                        results.append(f"Project created: {response.get('project_name', 'Untitled')}")
                except Exception as e:
                    results.append(f"Error creating project: {str(e)}")

        # Prompt for more data
        results.append("Provide more project descriptions to create additional projects.")
        appLogger.info("Prompting user for more project descriptions")
        return results

    def _extract_json(self, response: Any) -> Any:
        """Extract JSON from LLM response."""
        try:
            return extract_json_after_llm(response)
        except Exception as e:
            appLogger.error(f"JSON extraction failed: {e}")
            return None

def small_fn(
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
) -> List[str]:
    """Entry point for Project Creation Agent.

    Args:
        tenantID: Tenant ID.
        userID: User ID.
        llm: LLM instance.
        model_opts: Model options for LLM.
        socketio: SocketIO instance (unused).
        client_id: Client ID (unused).
        logInfo: Logging information.
        last_user_message: Latest user message.
        sessionID: Session ID.
        **kwargs: Additional arguments.

    Returns:
        List of result messages.
    """
    tango_dao = TangoDao

    # Store user message
    if last_user_message:
        tango_dao.insertTangoState(
            tenant_id=tenantID,
            user_id=userID,
            key="pc_conv",
            value=last_user_message,
            session_id=sessionID
        )

    # Fetch conversation history
    conv_ = tango_dao.fetchTangoStatesForSessionIdAndUserAndKeyAll(
        session_id=sessionID, user_id=userID, key="pc_conv"
    )
    conversation = [c.get("value", "") for c in conv_][::-1]

    # Initialize agent
    agent = ProjectCreationAgent(llm)

    # Process project
    results = agent.process_project(
        conversation=conversation,
        last_user_message=last_user_message,
        tenant_id=str(tenantID),
        user_id=str(userID),
        log_info=logInfo or {}
    )

    yield json.dumps(results)

PROJECT_CREATION_AGENT = AgentFunction(
    name="project_creation_agent",
    description="Creates Trmeric projects from plain text project descriptions in conversation.",
    args=[],
    return_description="List of result messages, including project creation status and prompts for more descriptions.",
    function=small_fn,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name,
    return_type=AgentReturnTypes.YIELD.name
)