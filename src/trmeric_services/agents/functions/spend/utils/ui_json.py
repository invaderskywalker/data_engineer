from src.trmeric_database.dao import TangoDao
import json

def ui_json(sessionID):
    return_json = {}
    return_json["event"] = "spend_agent_data"

    states = TangoDao.fetchTangoStatesForSessionId(sessionID)
    overall = None
    spend_dcs_json = None
    spend_s_json = None
    spend_is_json = None
    spend_cs_json = None
    spend_d_json = None
    for state in states:
        if state['key'] == 'SPEND_STORED_EVALUATION_UI':
            overall = state['value']
        if state['key'] == 'SPEND_STORED_DCS_UI':
            spend_dcs_json = state['value']
        if state['key'] == 'SPEND_STORED_S_UI':
            spend_s_json = state['value']
        if state['key'] == 'SPEND_STORED_IS_UI':
            spend_is_json = state['value']
        if state['key'] == 'SPEND_STORED_CS_UI':
            spend_cs_json = state['value']
        if state['key'] == 'SPEND_STORED_D_UI':
            spend_d_json = state['value']

    data = {}

    if overall:
        overall = json.loads(overall)
        data["tango_insights"] = overall.get("tango_insights")
        data["overall_summary"] = overall.get("overall_summary")
        data["executive_json"] = overall.get("executive_summary")
        data["currency"] = overall.get("currency")
        
    recommendations = []
    if spend_dcs_json:
        recommendations.append(json.loads(spend_dcs_json))
    if spend_s_json:
        recommendations.append(json.loads(spend_s_json))
    if spend_is_json:
        recommendations.append(json.loads(spend_is_json))
    if spend_cs_json:
        recommendations.append(json.loads(spend_cs_json))
    if spend_d_json:
        recommendations.append(json.loads(spend_d_json))

    data["categories_breakdown"] = recommendations

    return_json["data"] = data
    return return_json

def start_show_timeline():
    return {"event": "show_timeline"}

def stop_show_timeline():
    return {"event": "stop_show_timeline"}

def timeline_event(text, key, is_completed):
    return { "event": "timeline", "data": {"text": text, "key": key, "is_completed": is_completed}}
