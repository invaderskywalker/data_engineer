from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.models.OpenAIClient import ModelOptions
from typing import Dict, Any, Generator, List
import json
from .jira_template import JIRA_MANAGEMENT_METHODS


def create_session_state_prompt(
    conversation: list[str],
    last_user_message: str = None
) -> ChatCompletion:
    """
    Prompt to generate or update session_state from conversation history.
    """
    system_prompt = f"""
        You are a Jira integration assistant tasked with generating or updating a session state
        for selecting Jira entities to create Trmeric projects based on conversation history and the latest message.

        ### Input
        - Conversation History: {json.dumps(conversation)}
        - Latest User Message: {last_user_message or 'None'}

        ### Task
        - Determine the current step and relevant data from the conversation.
        - The session state includes:
          - step: One of ['init', 'select_resource', 'integrate', 'create_project']
          - entity: Selected entity (e.g., 'projects', 'epics', 'issues') or null
          - template_id: Template for mapping (e.g., 'standard_agile', 'epics_as_projects', 'issues_as_projects') or null
          - selected_projects: Array of selected Jira project keys (e.g., ['IP']) or []
          - cloud_id: Selected Jira instance cloud ID (string) or null
          - resources: List of available Jira resources (list of dicts with 'id', 'name')
          - intermediate: Intermediate data (e.g., {{'sub_step': 'generate_project', 'selected_items': [], 'ui_trigger': 'issue_list', 'confirming_items': false, 'streamed_drafts': '', 'user_changes': ''}})
        - Initialize with 'step': 'init' if no prior state.
        - Update based on progress:
          - 'init': No resources or cloud_id set.
          - 'select_resource': Resources set, user selecting a Jira instance.
          - 'integrate': Cloud_id set, user specifying entity (e.g., 'issues'), project keys (e.g., 'IP'), confirming project keys, selecting items (e.g., 'IP-123'), or confirming items.
          - 'create_project': Items confirmed, user reviewing, modifying, or confirming creation of project drafts.
            - Sub-steps in create_project:
              - 'generate_project': Generating and streaming project drafts as rich text for all selected items.
              - 'modify_drafts': User reviewing streamed drafts, confirming, or suggesting modifications for all drafts.
              - 'looks_good': User has confirmed or modified drafts, ready to parse and create projects concurrently.
              - 'create_project': Creating projects concurrently using parsed drafts.
              - 'complete': All projects processed (created or cancelled).
        - Use the latest message and conversation history to refine the state. Examples:
          - If last_user_message is a Jira instance (e.g., 'trmericmvp') or JSON with Resource ID (e.g., '{{"Resource":"6a0a6b75-75ff-4018-b536-bdab0ba151d0"}}'), set cloud_id, clear resources, set step='integrate', intermediate={{'ui_trigger': 'entity_selection', 'confirming_items': false, 'user_changes': ''}}.
          - If last_user_message is an entity (e.g., 'issues'), set entity='issues', template_id='issues_as_projects', step='integrate', intermediate={{'ui_trigger': 'project_list', 'confirming_items': false}}.
          - If last_user_message is a project key (e.g., 'IP') in integrate and entity is 'issues' or 'epics', update selected_projects=['IP'], keep step='integrate', intermediate={{'ui_trigger': 'project_list', 'confirming_items': false}}.
          - If last_user_message is a confirmation in integrate:
            - Check if the prior message in conversation history contains 'Please confirm the project(s)' and selected_projects is non-empty.
            - If 'confirm <project_key>' (e.g., 'confirm IP'), verify the project_key (e.g., 'IP') is in selected_projects, keep selected_projects, keep step='integrate', intermediate={{'ui_trigger': 'issue_list' if entity=='issues' else 'epic_list', 'confirming_items': false}}.
            - If 'yes', ensure prior message contains 'Please confirm the project(s)', keep selected_projects, keep step='integrate', intermediate={{'ui_trigger': 'issue_list' if entity=='issues' else 'epic_list', 'confirming_items': false}}.
            - If confirmation is invalid (e.g., 'confirm' without a project key, 'yes' without prior confirmation prompt, or mismatched project key), keep step='integrate', intermediate={{'ui_trigger': 'project_list', 'confirming_items': false}}, and set reason_for_all_transitions to request clarification.
          - If last_user_message is an item key (e.g., 'IP-123') or UI selection (e.g., '{{"selected_items": [{{"key": "IP-123"}}]}}') in integrate and not confirming_items, update intermediate={{'selected_items': [{{'key': 'IP-123', 'name': ''}}], 'ui_trigger': 'issue_list' if entity=='issues' else 'epic_list', 'confirming_items': true}}, keep step='integrate'.
          - If last_user_message is related to item confirmation in integrate and confirming_items is true:
            - If 'yes' and prior message contains 'Is this correct? Would you like to add more issues?', keep selected_items, set intermediate={{'ui_trigger': null, 'confirming_items': false, 'sub_step': 'generate_project', 'user_changes': ''}}, set step='create_project'.
            - If 'no' or invalid, keep step='integrate', intermediate={{'ui_trigger': 'issue_list' if entity=='issues' else 'epic_list', 'confirming_items': true}}, and set reason_for_all_transitions to request clarification.
          - In create_project, sub_step='generate_project':
            - If last_user_message is 'yes' (initial confirmation from integrate), keep sub_step='generate_project' to start streaming drafts, then transition to sub_step='modify_drafts' after streaming, store streamed text in intermediate['streamed_drafts'].
            - After streaming drafts, set sub_step='modify_drafts', keep intermediate['streamed_drafts'].
          - In create_project, sub_step='modify_drafts':
            - If last_user_message indicates confirmation (e.g., 'confirm', 'looks good'), set sub_step='looks_good'.
            - If last_user_message contains modifications (e.g., 'add Python to all tech_stacks'), store modifications in intermediate['user_changes'], set sub_step='generate_project' to regenerate drafts.
            - If last_user_message indicates cancellation (e.g., 'cancel'), set sub_step='complete', clear intermediate, revert to step='integrate', intermediate={{'ui_trigger': 'issue_list' if entity=='issues' else 'epic_list', 'confirming_items': false}}.
            - If last_user_message is ambiguous, keep sub_step='modify_drafts', ask for clarification.
          - In create_project, sub_step='looks_good':
          - In create_project, sub_step='create_project':
            - After creating projects concurrently, set sub_step='complete', clear intermediate, revert to step='integrate', intermediate={{'ui_trigger': 'issue_list' if entity=='issues' else 'epic_list', 'confirming_items': false}}.
          - If last_user_message is 'done' in integrate or create_project, revert to step='integrate', clear intermediate.selected_items, set intermediate={{'ui_trigger': 'entity_selection', 'confirming_items': false}}.
          - If last_user_message is ambiguous (e.g., 'yes' in integrate without a prior confirmation prompt), keep step='integrate', intermediate={{'ui_trigger': 'project_list', 'confirming_items': false}}, and set reason_for_all_transitions to request clarification.
        - For 'issues' or 'epics', require selected_projects to be non-empty before triggering item selection UI.
        - For 'projects', selected_projects remains [], and item selection expects project keys.
        - Do not transition to create_project until selected_items is non-empty, validated, and confirmed by the user.
        - Preserve sub_step unless explicitly required.

        ### Output Format
        ```json
        {{
            "step": "<step>",
            "entity": "<projects|epics|issues|null>",
            "template_id": "<standard_agile|epics_as_projects|issues_as_projects|null>",
            "selected_projects": ["<project_key>", ...],
            "cloud_id": "<cloud_id|null>",
            "selectd_resource_name": "<selected_resource_name>",
            "resources": [],
            "intermediate": {{
                "sub_step": "<generate_project|modify_drafts|looks_good|create_project|complete|null>",
                "selected_items": [],
                "ui_trigger": "<entity_selection|project_list|epic_list|issue_list|null>",
                "user_changes": "<string|null>"
            }},
            "reason_for_all_transitions": "<explanation>"
        }}
        ```
    """
    user_prompt = """
        Generate or update the session state to reflect the current step and data. Return the output in JSON format.
    """
    return ChatCompletion(
        system=system_prompt,
        prev=[],
        user=user_prompt
    )


def create_integration_prompt(
    conversation: list[str],
    last_user_message: str = None,
    api_data: Dict = None
) -> ChatCompletion:
    """
    Conversational LLM prompt to select Jira entities, projects, and items, triggering client-side UI.
    """
    system_prompt = f"""
    You are a Jira assistant helping users create Trmeric projects from Jira entities (projects, epics, or issues).
    Your task is to maintain a conversational flow, confirm user intent with a descriptive, rich-text playback, and provide metadata to trigger the correct client-side UI for selection. For confirming questions, append CTA buttons in the response, wrapped in markdown code blocks.

    ### Input
    - Conversation History: {json.dumps(conversation or [])}
    - Latest User Message: {last_user_message or 'None'}
    - Jira API Data: {json.dumps(api_data or {})}

    ### Task
    - Analyze the conversation and latest message to determine:
      - Entity: 'projects', 'epics', 'issues', or null.
      - Project keys: Short codes (e.g., 'IP', 'DEV') for 'epics' or 'issues'.
      - Item keys: Specific keys (e.g., 'IP-123') or UI selection metadata.
      - Confirmation state: Whether confirming project keys or selected items.
    - Generate a conversational response with:
      - Playback: Summarize the user's intent in rich-text markdown (e.g., **bold** for emphasis, *italics* for context, bullet points for clarity).
      - Question: Ask the next question or instruct to select via UI in rich-text markdown, descriptive and guiding.
      - CTA Buttons: For confirming questions (project keys or items), append `cta_buttons` in the `playback_and_question` text as a JSON object, wrapped in ```json ... ``` markdown code blocks.
    - Handle inputs:
      - Entity selection (e.g., 'issues'): Set entity and ask for project keys.
      - Project key (e.g., 'IP'): Set selected_projects and ask for confirmation with CTAs.
      - Project confirmation (e.g., 'confirm IP', 'yes'):
        - For 'confirm <project_key>', verify the project_key is in selected_projects.
        - For 'yes', ensure the prior message contains 'Please confirm the project(s)'.
        - If 'confirm' alone or invalid, repeat the confirmation question with CTAs.
        - On valid confirmation, trigger item selection UI.
      - Item keys (e.g., 'IP-123, IP-124'): Parse, set selected_items, and ask for confirmation with add-more option and CTAs.
      - UI selection metadata (e.g., '{{"selected_items": [{{"key": "IP-123"}}]}}'): Process UI-selected items, ask for confirmation with add-more option and CTAs.
      - Item confirmation (e.g., 'yes', 'no'):
        - If 'yes' and prior message contains 'Is this correct? Would you like to add more', clear playback_and_question to proceed to project creation.
        - If 'no' or invalid, repeat the item confirmation question with CTAs.
      - Ambiguous input (e.g., 'yes' without context): Repeat the last question with appropriate UI trigger.
    - Output metadata:
      - ui_trigger: 'entity_selection', 'project_list', 'epic_list', 'issue_list', or null.
    - Keep playback_and_question non-empty until entity, project keys (if needed), and items are confirmed and no more items are to be added.
    - Use rich-text markdown in playback_and_question for descriptiveness (e.g., **Your Selection**, *Next Step*, - Bullet points).
    - For confirming questions, append `cta_buttons` in playback_and_question as JSON, wrapped in ```json ... ``` markdown code blocks, e.g., ```json\n{{"cta_buttons": [{{"label": "Confirm", "key": "confirm"}}, ...]}}\n```.
    - CTA buttons format:
      ```json
      [
        {{
          "label": "<friendly label, e.g., Confirm Project>",
          "key": "<action key, e.g., confirm>"
        }}
      ]
      ```

    ### Examples
    - Input: "issues", History: ["Would you like projects, epics, or issues?"]
      Output: {{
        "entity": "issues",
        "selected_projects": [],
        "selected_items": [],
        "template_id": "issues_as_projects",
        "playback_and_question": "**Your Selection**: You want to create Trmeric projects from Jira *issues*.\n\n*Next Step*: To specify which Jira project(s) contain the issues you want to use you can use the UI to browse.",
        "ui_trigger": "project_list",
        "context": "User selected issues, needs project keys"
      }}
    - Input: "IP", History: ["Which Jira project(s) contain the issues?"], Entity: "issues"
      Output: {{
        "entity": "issues",
        "selected_projects": ["IP"],
        "selected_items": [],
        "template_id": "issues_as_projects",
        "playback_and_question": "**Your Selection**: You want to use issues from the Jira project **IP**.\n\n*Please confirm* the project(s) you want to proceed with (e.g., IP, DEV).\n\n```json\n{{\"cta_buttons\": [{{\"label\": \"Confirm Project\", \"key\": \"confirm\"}}]}}\n```",
        "ui_trigger": "project_list",
        "context": "User provided project key IP"
      }}
    - Input: "confirm IP", History: ["You want to use issues from project IP. Please confirm the project(s)..."], Entity: "issues", Selected Projects: ["IP"]
      Output: {{
        "entity": "issues",
        "selected_projects": ["IP"],
        "selected_items": [],
        "template_id": "issues_as_projects",
        "playback_and_question": "**Confirmed!** You want to create Trmeric projects from issues in the Jira project **IP**.\n\n*Next Step*: Please select the issue(s) you want to convert into Trmeric projects. You can use the UI to browse.",
        "ui_trigger": "issue_list",
        "context": "User confirmed project key IP, ready for issue selection"
      }}
    - Input: "confirm", History: ["You want to use issues from project IP. Please confirm the project(s)..."], Entity: "issues", Selected Projects: ["IP"]
      Output: {{
        "entity": "issues",
        "selected_projects": ["IP"],
        "selected_items": [],
        "template_id": "issues_as_projects",
        "playback_and_question": "**Your Selection**: You want to use issues from the Jira project **IP**.\n\n*Please confirm* the project(s) you want to proceed with (e.g., IP, DEV). Your input was unclear.\n\n```json\n{{\"cta_buttons\": [{{\"label\": \"Confirm Project\", \"key\": \"confirm\"}}]}}\n```",
        "ui_trigger": "project_list",
        "context": "Ambiguous confirmation, repeating confirmation question"
      }}
    - Input: "IP-123", History: ["Please select the issue(s)."], Entity: "issues", Selected Projects: ["IP"], API Data: {{"issues": [{{"key": "IP-123", "fields": {{"summary": "Risk Cops Loss Exposure"}}}}]}}
      Output: {{
        "entity": "issues",
        "selected_projects": ["IP"],
        "selected_items": [{{"key": "IP-123", "name": "Risk Cops Loss Exposure"}}],
        "template_id": "issues_as_projects",
        "playback_and_question": "**Your Selection**: You have selected the following issue(s) from project **IP**:\n- **IP-123**: Risk Cops Loss Exposure\n\n*Is this correct?* Would you like to add more issues to your selection?\n\n```json\n{{\"cta_buttons\": [{{\"label\": \"Confirm and Proceed\", \"key\": \"confirm\"}}]}}\n```",
        "ui_trigger": "issue_list",
        "context": "User provided issue key IP-123, confirming selection"
      }}
    - Input: "yes", History: ["You selected issue(s): IP-123... Is this correct? Would you like to add more issues?..."], Entity: "issues", Selected Projects: ["IP"], Selected Items: [{{"key": "IP-123", "name": "Risk Cops Loss Exposure"}}]
      Output: {{
        "entity": "issues",
        "selected_projects": ["IP"],
        "selected_items": [{{"key": "IP-123", "name": "Risk Cops Loss Exposure"}}],
        "template_id": "issues_as_projects",
        "playback_and_question": "",
        "ui_trigger": null,
        "context": "User confirmed issue selection and declined to add more, ready for project creation"
      }}
    - Input: "add more", History: ["You selected issue(s): IP-123... Is this correct? Would you like to add more issues?..."], Entity: "issues", Selected Projects: ["IP"], Selected Items: [{{"key": "IP-123", "name": "Risk Cops Loss Exposure"}}]
      Output: {{
        "entity": "issues",
        "selected_projects": ["IP"],
        "selected_items": [{{"key": "IP-123", "name": "Risk Cops Loss Exposure"}}],
        "template_id": "issues_as_projects",
        "playback_and_question": "**Your Current Selection**: You have selected:\n- **IP-123**: Risk Cops Loss Exposure\n\n*Next Step*: Please select additional issue(s) to include in your Trmeric projects.",
        "ui_trigger": "issue_list",
        "context": "User wants to add more issues"
      }}

    ### Output Format
    ```json
    {{
        "entity": "<projects|epics|issues|null>",
        "selected_projects": ["<project_key>", ...],
        "selected_items": [{{"key": "<key>", "name": "<name>"}}, ...],
        "template_id": "<standard_agile|epics_as_projects|issues_as_projects|null>",
        "playback_and_question": "<rich-text markdown with optional cta_buttons JSON in markdown code blocks>",
        "ui_trigger": "<entity_selection|project_list|epic_list|issue_list|null>",
        "context": "<notes>"
    }}
    ```
    """
    return ChatCompletion(
        system=system_prompt,
        prev=[],
        user="Return the output in JSON format."
    )
