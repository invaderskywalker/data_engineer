from src.trmeric_services.tango.types.TangoYield import TangoYield


def ask_clarifying_question(clarifying_question: str, integrations:bool, creation_type: str, **kwargs):
    if creation_type == "Profile":
        add_source = """
```json
{{
    "onboarding_add_source": [
        {
            "label": "Add Sources",
            "key": "TANGO_ONBOARDING_PROFILE"
        }
    ]
}}
```
        """
        
    if creation_type == "Project":
        add_source = """
```json
{
    "onboarding_add_integration": [
        {
            "key": "TANGO_ONBOARDING_PROJECT"
        }
    ]
}
```
        """
        
    if creation_type == "Roadmap":
        add_source = """
```json
{
    "onboarding_add_integration": [
        {
            "key": "TANGO_ONBOARDING_ROADMAP"
        }
    ]
}
```
        """
        
    ret_val = f"""Ask the user the following clarifying question:  + {clarifying_question}  """
    yield_after = add_source
    return TangoYield(return_info=ret_val, yield_info=yield_after)


def clarifying_information_enhancement(clarifying_information, clarifying_questions, last_tango_message, last_user_message):
    if len(clarifying_questions) > 0:
        clarifying_information = f"""
        'Here is clarifying information obtained from the user:',\n\n{clarifying_information}\n.
        'Here are the questions you already asked the user:',\n\n{clarifying_questions}\n.
        """
        
        interaction = ""
        if last_tango_message:
            interaction += f"Here is the last clarifying question you asked: {last_tango_message}\n\n"
        if last_user_message:
            interaction += f"Here is the user's response to the last clarifying question: {last_user_message}\n\n"
            interaction += f"Here's a tip: If the user's last message says 'create projects' in response to a clarifying question, you should probably proceed with creating projects, meaning no more clarifying questions.\n\n"
            
        clarifying_information = clarifying_information + interaction
    return clarifying_information