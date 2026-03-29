import json
import textwrap
from jsonschema import validate

from src.trmeric_services.agents.core import AgentFunction
from src.trmeric_database.dao import TangoDao
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.functions.spend.utils.spend import emit_progress
import traceback
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.journal.Activity import detailed_activity

# Schema definition for JSON validation
SCHEMA = {
    "type": "object",
    "properties": {
        "tango_insights": {
            "type": "object",
            "properties": {
                "cost_distribution": {"type": "array", "items": {"type": "string"}},
                "savings_potential": {"type": "array", "items": {"type": "string"}},
                "trend_analysis": {"type": "array", "items": {"type": "string"}},
                "efficiency_gaps": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["cost_distribution", "savings_potential", "trend_analysis", "efficiency_gaps"]
        },
        "overall_summary": {
            "type": "object",
            "properties": {
                "total_spend": {"type": "string"},
                "savings_potential": {"type": "string"},
                "year_to_year_change": {"type": "string"}
            },
            "required": ["total_spend", "savings_potential", "year_to_year_change"]
        },
        "executive_json": {
            "type": "object",
            "properties": {
                "sheet_summary": {"type": "string"},
                "chart_data": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string"},
                            "actual_spend": {"type": "string"}
                        }
                    }
                },
                "insights": {"type": "array", "items": {"type": "string"}}
            }
        },
        "currency": {"type": "string"},
        "categories_breakdown": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "current_spend": {"type": "string"},
                    "category_sub_heading": {"type": "string"},
                    "category_insights": {"type": "array", "items": {"type": "string"}},
                    "bar_chart_sorted_data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sub_category": {"type": "string"},
                                "spend_amount": {"type": "string"}
                            }
                        }
                    },
                    "sub_category_breakdown": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sub_category": {"type": "string"},
                                "current_spend": {"type": "string"},
                                "action": {"type": "string"},
                                "my_todo_actions_based_on_numerical_assesment": {"type": "string"},
                                "impact": {"type": "string"},
                                "effort": {"type": "string"}
                            }
                        }
                    }
                }
            }
        }
    }
}


def spend_edit(tenantID, userID, llm, sessionID, client_id,
               user_feedback_to_edit_final_spend_analysis=None, **kwargs):
    """
    Update the spend analysis UI JSON based on provided user feedback with enhanced accuracy controls.
    """
    socketio = kwargs.get('socketio')

    # Retrieve stored UI JSON
    states = TangoDao.fetchTangoStatesForSessionId(sessionID)
    state_obj = next((state for state in states if state.get('key') == 'SPEND_EVALUATION_FINISHED'), None)

    if state_obj is None:
        return "Spend evaluation state not found. Please run spend evaluation first."

    try:
        uijson = json.loads(state_obj['value'])
    except (json.JSONDecodeError, KeyError) as e:
        appLogger.error({
            "event": "spend_edit_json_parse_error",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error": str(e), 
            "traceback": traceback.format_exc()
        })
        return "Failed to parse stored UI data."

    user_feedback = user_feedback_to_edit_final_spend_analysis or ""
    
    # Single comprehensive LLM call to identify and apply changes
    system_prompt = """You are a financial data editor specializing in precise JSON modifications.
Your task is to edit a financial dashboard JSON based on user feedback.

IMPORTANT RULES:
1. ONLY modify text/string content fields mentioned in the user feedback.
2. NEVER change numerical values, currency amounts, or ratings/scores.
3. Maintain the exact same JSON structure and property names.
4. Return the COMPLETE modified JSON object with all properties.
5. Ensure all modifications maintain domain accuracy for financial analysis.

The JSON contains:
- tango_insights: cost_distribution[], savings_potential[], trend_analysis[], efficiency_gaps[]
- overall_summary: text summaries of spend data
- executive_json: insights[] and chart data
- categories_breakdown[]: array of categories with insights and subcategories

If no specific areas need changes, return the original JSON unchanged."""

    user_prompt = (
        f"USER FEEDBACK:\n{user_feedback}\n\n"
        f"COMPLETE JSON TO MODIFY:\n{json.dumps(uijson, indent=2)}\n\n"
        f"Apply the requested changes and return the complete, updated JSON. Remember to only modify text content mentioned "
        f"in the feedback while preserving all numerical values, structure, and property names."
    )

    try:
        response = llm.run(
            ChatCompletion(
                system=system_prompt,
                prev=[],
                user=user_prompt
            ),
            ModelOptions(
                model="gpt-4o", 
                temperature=0.0,
                max_tokens=4000  # Increased token limit to handle the complete JSON
            ),
            "spend_edit_unified"
        )
    except Exception as e:
        appLogger.error({
            "event": "spend_edit_llm_error",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error": str(e), 
            "traceback": traceback.format_exc()
        })
        return "An error occurred while processing your request. Please try again later."

    # Extract the updated JSON from LLM response
    try:
        updated_uijson = extract_json_after_llm(response)
        
        # Validate against schema to ensure structural integrity
        try:
            validate(instance=updated_uijson, schema=SCHEMA)
        except Exception as schema_error:
            appLogger.error({
                "event": "spend_edit_schema_validation_error",
                "tenant_id": tenantID, 
                "user_id": userID,
                "error": str(schema_error), 
                "traceback": traceback.format_exc()
            })
            return "The edited JSON does not match the expected structure. Please try with different feedback."
        
    except Exception as e:
        appLogger.error({
            "event": "spend_edit_json_parse_error",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error": str(e), 
            "traceback": traceback.format_exc()
        })
        return "Failed to process the updated data."

    # Update state
    try:
        TangoDao.upsertTangoState(
            tenantID, userID, 'SPEND_EVALUATION_FINISHED',
            json.dumps(updated_uijson), sessionID
        )
    except Exception as e:
        appLogger.error({
            "event": "spend_edit_state_update_error",
            "tenant_id": tenantID, 
            "user_id": userID,
            "error": str(e), 
            "traceback": traceback.format_exc()
        })
        return "Failed to update the UI state."

    # Emit updates
    if socketio:
        emit_progress(socketio, client_id, updated_uijson)
    
    # Log activity: User customized spend analysis
    detailed_activity(
        activity_name="spend_analysis_customization",
        activity_description="User provided feedback to refine spend analysis. Tango intelligently updated insights, recommendations, and visualizations based on user preferences while preserving all numerical accuracy.",
        user_id=userID
    )
        
    return "Your changes have been successfully applied to the UI."

SPEND_EDIT = AgentFunction(
    name="spend_edit",
    description=(
        "Call this function when the user has finished running their spend evaluation and would like "
        "to edit their spend analysis. If they give some specific feedback, pass the feedback as an argument."
    ),
    args=[
        {
            "name": "user_feedback_to_edit_final_spend_analysis",
            "description": (
                "If the user has provided feedback to edit the final spend analysis, pass the feedback here. "
            ),
            "type": "str",
        },
    ],
    return_description="The UI will be updated with the user's request.",
    function=spend_edit,
)
