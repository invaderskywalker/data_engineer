from src.trmeric_services.agents.functions.onboarding.transition import transition_text
from src.trmeric_database.dao import TangoDao
from src.trmeric_services.tango.types.TangoYield import TangoYield
import traceback, json
from src.trmeric_services.agents.functions.onboarding.creation_tools.AutonomousCreateProfile import ProfileAgent

def further_specific_profile_creation(tenantID, userID, sessionID, **kwargs):
    ret_val =  """Please provide sources using which we can create your profile:  You can add documents or write free text."""
    TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_PROFILE_SHOW_SOURCE', "", sessionID)
    yield_after = """
```json
{
    "onboarding_add_source": [
        {
            "label": "Add Sources",
            "key": "TANGO_ONBOARDING_PROFILE"
        }
    ]
}
```
    """
    
    return TangoYield(return_info=ret_val, yield_info=yield_after)

def profile_creation_cancel(tenantID, userID, sessionID, **kwargs):
    TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_PROFILE_CANCEL', "", sessionID)
    return transition_text(sessionID)
    
def process_profiles(profiles, user_id, tenant_id, sessionID, llm):
    progress_json = []
    progress_str = ""
    for profile in profiles:
        profile_name = profile.get('organization_details', {}).get('name', 'Unnamed profile')
        input_json = {
            "organization_details": profile.get('organization_details', {}),
            "key_contacts": profile.get('key_contacts', []),
            "demographics": profile.get('demographics', {}),
            "solutions_offerings": profile.get('solutions_offerings', {}),
            "business_goals_and_challenges": profile.get('business_goals_and_challenges', {}),
            "engagement_details": profile.get('engagement_details', {}),
            "technological_landscape": profile.get('technological_landscape', {}),
            "operational_context": profile.get('operational_context', {}),
            "financial_context": profile.get('financial_context', {}),
            "compliance_and_security": profile.get('compliance_and_security', {}),
            "organizational_knowledge": profile.get('organizational_knowledge', {}),
            "genai_context": profile.get('genai_context', {}),
            "external_trends": profile.get('external_trends', {})
        }

        # Call the autonomous_create_profile function
        try:
            yield f"Tango is doing final enhancements to the profile for {profile_name}. Please wait a few moments... \n\n"
            request_data, ret_val = ProfileAgent().create_profile(
                tenant_id=tenant_id,
                user_id=user_id,
                input_json=input_json,
                llm = llm
            )
            if not request_data:
                return ret_val
            else:
                progress_json.append(dict(request_data))
            
            progress_str += ret_val + "\n"
            
            print(f"Created profile: {profile_name}")
        except Exception as e:
            print(f"Error creating profile {profile_name}: {str(e)}")
            traceback.print_exc()
    if progress_json != []:
        yield_after = f"""
```json
{{
    "review_progress": {json.dumps(progress_json, indent=4)}
}}
```
        """ 
        ret_val = progress_str
        TangoDao.insertTangoState(tenant_id, user_id, 'ONBOARDING_PROFILE_FINISHED', "", sessionID) 
    else: return progress_str
    return TangoYield(return_info=ret_val, yield_info=yield_after)
