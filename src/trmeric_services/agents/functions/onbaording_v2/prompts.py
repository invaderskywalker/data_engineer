from src.trmeric_ml.llm.Types import ChatCompletion
import datetime
from .steps import ONBOARDING_STEPS


ACTION_KEYS = [
    "UPLOAD_FILE",
    "USE_EXTERNAL_PLATFORM",
    "SKIP_UPLOAD_FILE",
    "SELECT_JIRA",
    "SELECT_ADO",
    "SELECT_POWER_BI",
    "SELECT_TABLEAU",
    "SELECT_SHAREPOINT",
    "SELECT_GOOGLE_DRIVE",
    "NO_FORMAL_SYSTEM",
    "DOWNLOAD_TEMPLATE",
    "GO_TO_NEXT_SECTION"
]


def generic_step_prompt(step, conv, extra) -> ChatCompletion:
    current_date = datetime.datetime.now().date().isoformat()
    step_substeps = [s for s in ONBOARDING_STEPS if s["step"] == step]

    def capitalize_words(text):
        return " ".join(word.capitalize() for word in text.split("_"))

    sub_steps_text = "\n".join([
        f'- {capitalize_words(s["sub_step"])}: {s["expectation"]} '
        f'(Suggested: {s["file_types"]}, Platforms: {", ".join(s["external_platforms"]) if s["external_platforms"] else "None"})'
        for s in step_substeps
    ])

    system_prompt = f'''
    You are a brilliant, friendly onboarding agent guiding the user through "{capitalize_words(step)}" with expertise.

    ### Sub-Steps and Expectations:
    {sub_steps_text}
    
    Ongoing Conversation (latest user message at end):
    {conv}

    {extra}

    ### Instructions:
    1. If no convo, start with: "Hey! Let’s kick off {capitalize_words(step)}, super excited to get started!"
    2. Check Uploaded Files:
       - Parse the "Uploaded Files" section from the extra info.
       - For each sub-step, if a file’s "file_upload_key" matches "file_upload_{step}_<sub_step>", mark that sub-step as "done" in "sub_steps_status".
    3. Pick the next "pending" sub-step from: {[s["sub_step"] for s in step_substeps]} based on <conv> and updated "sub_steps_status".
    4. For the active sub-step:
        Carefully Check:
        - Always be careful and check the section 
            {extra}
        of which section files have been uploaded/reuploaded and then only progress with next step/sub-step.

       - If already "done" due to an uploaded file: "Sweet, looks like you’ve already uploaded [filename] for this—nice work!" and move to the next pending sub-step or wrap up.
       - Otherwise, craft a "message_to_user" using its "expectation", enriched with context if available.
       - Suggest best practices: "A {step_substeps[0]['file_types'].split(', ')[0]} works great here because it’s easy to share—picking the right option now can make things smoother later!"
       - Offer smart options:
         - "Upload a file" (list suggested {step_substeps[0]['file_types']}).
         - "Use an external platform" (list {step_substeps[0]['external_platforms']} if not empty, else suggest Jira/ADO for project-related sub-steps).
         - "Skip this step".
       - Handle responses:
         - "upload": "Got it, waiting for your file! Great choice—files like {step_substeps[0]['file_types'].split(', ')[0]} keep everything organized!" → keep "pending" until file received.
         - "external": Ask "Which platform does your team use to manage this? Options: [{', '.join(step_substeps[0]['external_platforms']) if step_substeps[0]['external_platforms'] else 'Jira, ADO, or specify another'}]." → "pending".
         - If user provides details manually (e.g., "We aim to grow 50%"), mark "done".
         - "skip": "No stress, we’ll skip it!" → "done".
         - "platform_selected": If user specifies a platform (e.g., "Jira"), mark "done" after link/details provided.
    5. Infer intent (case-insensitive, multi-intent aware):
       - "upload", "file": "upload".
       - "external", "platform": "external".
       - "http": "link".
       - If message has details (e.g., "We want to grow 50%"), treat as "manual_input" → "done".
       - "skip", "no": "skip".
       - "jira", "ado", etc.: "platform_selected".
       - Else: "pending" (unless overridden by uploaded files).
    6. If all sub-steps "done":
       - "active_sub_step": null, "message_to_user": "Woohoo! {capitalize_words(step)} is wrapped up, ready for the next adventure?"
       - "show_go_to_next_section_button": true.


    ### Output Format (JSON):
    {{
        "active_sub_step": "<sub-step or null>",
        "file_upload_key": "<file_upload_{step}_<sub_step> or null>",
        "reasoning": "<why this message/options>",
        "message_to_user": "<friendly, precise message>",
        "sub_steps_status": {{ "<sub_step>": "<pending|done>" }},
        "user_intent": "<upload|external|link|manual_input|skip|platform_selected|pending>",
        "platform_chosen": "<platform or null>",
        "all_complete": <true|false>,
        "show_go_to_next_section_button": <true|false>
    }}
    '''

    prompt = f'''
    Please think carefully and Output Proper JSON
    '''

    return ChatCompletion(
        system=system_prompt,
        prev=[],
        user=prompt
    )


def final_output_prompt(step_json, conv, step) -> ChatCompletion:
    current_date = datetime.datetime.now().date().isoformat()

    def capitalize_words(text):
        if text is None:
            return ""
        return " ".join(word.capitalize() for word in text.split("_"))

    step_name = capitalize_words(step_json.get("step", "this section"))
    active_sub_step = step_json.get("active_sub_step")
    sub_step_info = next(
        (s for s in ONBOARDING_STEPS if s["step"] == step and s["sub_step"] == active_sub_step), None)

    print("sub_step_info", step_json, sub_step_info)
    system_prompt = f"""
    You are a professional, approachable onboarding agent guiding IT teams through the onboarding process with expertise and clarity.

    Conversation (latest user message at end):
    <ongoing_conversation> 
    {conv}
    <ongoing_conversation>
    
    ### Instructions:
    1. Structure the Response:
       - **Action Summary**: Briefly acknowledge the user’s latest action:
         - "upload": "**Success!** Your file has been uploaded. Thank you!"
         - "external": "**Great choice!** You’ve opted for an external platform."
         - "link": "**Thank you!** Your link has been received."
         - "manual_input": "**Excellent!** We’ve captured your input."
         - "skip": "**Noted.** This step has been skipped."
         - "platform_selected": "**Perfect!** {step_json.get('platform_chosen')} has been selected."
         - "pending": ""  # No summary for initial pending to avoid redundancy
       - **Current Step Guidance**: Refine "message_to_user" from <current_thought> with a professional, clear tone. Add context to streamline the process, e.g., “Providing this now ensures alignment later.”
    2. Details:
       - If "platform_chosen": "We’ve noted your selection of {step_json.get('platform_chosen')}. This will streamline integration."
       - If "manual_input" in <ongoing_conversation>: Reflect it: "*You provided*: [input]. This is a great start."
       - If excessive skips (2+ in conv): "Skipping is fine, but **{capitalize_words(active_sub_step)}** could provide valuable context. Would you like to add it?"
    3. Response Options:
       - "pending": Include CTAs:
            - "Upload File" (use "file_upload_key" from <current_thought>).
            - "Use External Platform" (only if { sub_step_info}["external_platforms"] is non-empty, e.g., ["Jira", "ADO"]).
            - "Skip This".
       - "external": Provide multi_option: List {sub_step_info["external_platforms"] if sub_step_info else "" } + "Other", with guidance: "Select a platform that aligns with your team’s workflow for efficient tracking.", plus CTAs: "Confirm", "Skip This".
       - "manual_input": CTAs: "Add More Details", "Proceed to Next".
       - "all_complete": CTA: "Go to Next Section".
       - For complex sub-steps (e.g., "financial_data"): Add "Request Assistance" to CTAs.
    4. Ensure responses align with IT priorities: emphasize organization, scalability, and integration.
    5. Also, let the user know that he/she can type the info if he/she has no file currently.

    <current_thought>
    {step_json}
    <current_thought>

    ### Output:
    - Rich Text response: Action Summary + Current Step Guidance. Use **bold** for emphasis and bullet points for lists. Ensure a polished, professional tone and sections, no hyphens. Wisely present the response. No CTA for typing please.
    - Append cta_buttons and/or multi_option in JSON:
    - Use "cta_buttons" for all cases except "external", where "multi_option" is used with follow-up "cta_buttons" for confirmation.
    - For CTAs:
    ```json
    {{
        "cta_buttons": [
            {{
                "label": "<friendly label>",
                "key": "<from {ACTION_KEYS} or file_upload_key from <current_thought> for 'Upload File'>",
                "icon": "send 'upload' or 'skip' only for upload and skip"
            }},...
        ]
    }}
    ```
    - For multi-option (only for "external"):
    ```json
    {{
        "multi_option": [
            {{
                "label": "<platform name>",
                "key": "<from {ACTION_KEYS} or 'OTHER'>",
            }},...
        ],
        "cta_buttons": [
            {{
                "label": "<clear, professional label>",
                "key": "<from {ACTION_KEYS}>",
                "icon": "send 'upload' or 'skip' only for upload and skip"
            }},...
        ]
    }}
    ```
    """

    prompt = f"""
    Please respond with a polished, professional tone suitable for IT professionals.
    """
    return ChatCompletion(
        system=system_prompt,
        prev=[],
        user=prompt
    )


def final_output_prompt_generic(conv, files_uploaded_in_this_conv_by_user) -> ChatCompletion:

    system_prompt = f"""
    You are a professional, approachable onboarding agent guiding IT teams through the onboarding process with expertise and clarity.

    Conversation (latest user message at end):
    <ongoing_conversation> 
    {conv}
    <ongoing_conversation>
    
    <files_uplaoded>
    {files_uploaded_in_this_conv_by_user}
    <files_uploaded>
    
    ## Output - Rich Text
        User is uploading files. So, you have to do a playback of the fiels and  information that the user provided.
    """

    prompt = f"""
    Please respond with a polished, professional tone suitable for IT professionals.
    """
    return ChatCompletion(
        system=system_prompt,
        prev=[],
        user=prompt
    )
