from src.trmeric_database.dao import TangoDao
from src.trmeric_services.tango.types.TangoYield import TangoYield    
from src.trmeric_database.dao.projects import ProjectsDao
from src.trmeric_services.agents.functions.spend.sql.CompareSpend import compare_projects_by_spend
from src.trmeric_services.agents.functions.spend.overall_compilation import analyze_overall_spend
from src.trmeric_services.agents.functions.spend.per_category_optimization import analyze_per_category
from src.trmeric_services.tango.functions.integrations.internal.prompts.GetGeneralProjects import view_projects
from src.trmeric_services.agents.functions.spend.utils.ui_json import  start_show_timeline, stop_show_timeline, timeline_event, ui_json
from src.trmeric_services.agents.functions.spend.utils.df_analysis import generate_df_analysis_suggestions
import threading


def spend_add_sources(tenantID, userID, sessionID, socketio, clientID, **kwargs):
    TangoDao.insertTangoState(tenantID, userID, 'SPEND_ADD_SOURCE', "", sessionID)
    ret_val =  """Please upload the any additional documents from which you may want your spend to be analyzed. We are looking for IT spend sheets. """
    yield_after = """
```json
{
    "spend_add_source": [
        {
            "label": "Add Sources",
            "key": "SPEND_SOURCES"
        }
    ]
}
```
    """
    json = {
        "event": "spend_add_source",
        "data": {
            "label": "Add Sources",
            "key": "SPEND_SOURCES"
        }
    }
    
    emit_progress(socketio, clientID, json)
    return TangoYield(return_info=ret_val, yield_info=yield_after)  
  
def get_spend_by_provider(projects, tenant_id):
    return compare_projects_by_spend(projects, "provider_id", tenant_id)

def get_spend_by_tech_stack(projects, tenant_id):
    return compare_projects_by_spend(projects, "tech_stack", tenant_id)

def get_spend_by_project_category(projects, tenant_id):
    return compare_projects_by_spend(projects, "project_category", tenant_id)

def get_spend_by_kpis(projects, tenant_id):
    return compare_projects_by_spend(projects, "kpis", tenant_id)

def get_spend_by_portfolio(projects, tenant_id):
    return compare_projects_by_spend(projects, "portfolio_id", tenant_id)

def get_spend_by_project_manager(projects, tenant_id):
    return compare_projects_by_spend(projects, "project_manager_id", tenant_id)

def get_spend_by_roadmap(projects, tenant_id):
    return compare_projects_by_spend(projects, "roadmap_id", tenant_id)

def analyze_spend_by_data_center_category(llm, projects, tenant_id, external_data, projectInformation, analysis, tenantID, userID, sessionID):

    spend_by_provider = get_spend_by_provider(projects, tenant_id)
    spend_by_tech_stack = get_spend_by_tech_stack(projects, tenant_id)
    spend_by_project_category = get_spend_by_project_category(projects, tenant_id)
    spend_by_kpis = get_spend_by_kpis(projects, tenant_id)


    organized_data = f"""
    
    Here is some calculations done on overall spend data. There may be some information relevant to data center systems in this data.
    {analysis}
    """
    
    analysis = analyze_per_category(llm, organized_data, external_data, 'data center systems', tenantID, userID, sessionID)
    return analysis

def analyze_spend_by_software_category(llm, projects, tenant_id, external_data, projectInformation, analysis, tenantID, userID, sessionID):
    spend_by_provider = get_spend_by_provider(projects, tenant_id)
    spend_by_tech_stack = get_spend_by_tech_stack(projects, tenant_id)
    spend_by_project_category = get_spend_by_project_category(projects, tenant_id)
    spend_by_kpis = get_spend_by_kpis(projects, tenant_id)

    organized_data = f"""

    Here is some calculations done on overall spend data. There may be some information relevant to software in this data.
    {analysis}
    """
    
    analysis = analyze_per_category(llm, organized_data, external_data, 'software', tenantID, userID, sessionID)
    return analysis

def analyze_spend_by_it_services_category(llm, projects, tenant_id, external_data, projectInformation, analysis, tenantID, userID, sessionID):
    spend_by_provider = get_spend_by_provider(projects, tenant_id)
    spend_by_tech_stack = get_spend_by_tech_stack(projects, tenant_id)
    spend_by_project_category = get_spend_by_project_category(projects, tenant_id)
    spend_by_kpis = get_spend_by_kpis(projects, tenant_id)

    organized_data = f"""

    Here is some calculations done on overall spend data. There may be some information relevant to IT services in this data.
    {analysis}
    """
    
    analysis = analyze_per_category(llm, organized_data, external_data, 'it services', tenantID, userID, sessionID)
    return analysis

def analyze_spend_by_communication_services_category(llm, projects, tenant_id, external_data, projectInformation, analysis, tenantID, userID, sessionID):
    spend_by_provider = get_spend_by_provider(projects, tenant_id)
    spend_by_tech_stack = get_spend_by_tech_stack(projects, tenant_id)
    spend_by_project_category = get_spend_by_project_category(projects, tenant_id)
    spend_by_kpis = get_spend_by_kpis(projects, tenant_id)

    organized_data = f"""

    Here is some calculations done on overall spend data. There may be some information relevant to communication services in this data.
    {analysis}
    """
    
    analysis = analyze_per_category(llm, organized_data, external_data, 'communication services', tenantID, userID, sessionID)
    return analysis

def analyze_spend_by_devices_category(llm, projects, tenant_id, external_data, projectInformation, analysis, tenantID, userID, sessionID):
    spend_by_provider = get_spend_by_provider(projects, tenant_id)
    spend_by_tech_stack = get_spend_by_tech_stack(projects, tenant_id)
    spend_by_project_category = get_spend_by_project_category(projects, tenant_id)
    spend_by_kpis = get_spend_by_kpis(projects, tenant_id)

    organized_data = f"""
    
    Here is some calculations done on overall spend data. There may be some information relevant to devices in this data.
    {analysis}
    """
    
    analysis = analyze_per_category(llm, organized_data, external_data, 'devices', tenantID, userID, sessionID)
    return analysis

def spend_cancel(tenantID, userID, sessionID, **kwargs):
    TangoDao.insertTangoState(tenantID, userID, 'SPEND_CANCEL', "", sessionID)
    return "Your progress has been cancelled. You can start over by uploading your documents again."

def emit_progress(socketio, clientID, message):
    socketio.emit("spend_agent", 
        message, 
        room=clientID
    )

def analyze_spend(tenantID, userID, sessionID, llm, socketio, clientID, dfs, saved_corpus, **kwargs):
    # go through uploaded documents

    emit_progress(socketio, clientID, start_show_timeline())

    emit_progress(socketio, clientID, timeline_event("Spend Data Analysis", "spend_data_analysis", False))
    emit_progress(socketio, clientID, timeline_event("Software", "software", False))
    emit_progress(socketio, clientID, timeline_event("IT Services", "it_services", False))
    emit_progress(socketio, clientID, timeline_event("Communication Services", "communication_services", False))
    emit_progress(socketio, clientID, timeline_event("Devices", "devices", False))
    emit_progress(socketio, clientID, timeline_event("Overall Analysis", "overall_analysis", False))
    print("checking files")



    emit_progress(socketio, clientID, "Tango is calculating some key metrics about your spend...")
    # Create threads for all analyses including general
    results = {}
    
    def analyze_general():
        results["analysis"] = generate_df_analysis_suggestions(dfs, llm)
        
    def analyze_category(category_name, dfs):
        results[f"{category_name.lower().replace(' ', '_')}_analysis"] = generate_df_analysis_suggestions(dfs, llm, category=category_name)
    
    # Create and start all threads including general analysis
    general_thread = threading.Thread(target=analyze_general)
    general_thread.start()
    
    # Continue with other analysis in background
    software_dfs = {}
    it_services_dfs = {}
    communication_services_dfs = {}
    devices_dfs = {}
    for excel_name, df_names in dfs.items():
        for df_name, df in df_names.items():
            software_val = {df_name: (df[df["Tango_Category"] == "Software"] if "Tango_Category" in df.columns else df)}
            it_services_val = {df_name: (df[df["Tango_Category"] == "IT Services"] if "Tango_Category" in df.columns else df)}
            communication_services_val = {df_name: (df[df["Tango_Category"] == "Communication Services"] if "Tango_Category" in df.columns else df)}
            devices_val = {df_name: (df[df["Tango_Category"] == "Devices"] if "Tango_Category" in df.columns else df)}
        software_dfs[excel_name] = software_val
        it_services_dfs[excel_name] = it_services_val
        devices_dfs[excel_name] = devices_val
        communication_services_dfs[excel_name] = communication_services_val
    
    # Create threads for category-specific analysis
    results = {}
    
    def analyze_category(category_name, dfs):
        results[f"{category_name.lower().replace(' ', '_')}_analysis"] = generate_df_analysis_suggestions(dfs, llm, category=category_name)
    
    print("starting threads")
    
    # Create and start all threads
    software_thread = threading.Thread(target=analyze_category, args=("Software", software_dfs))
    it_services_thread = threading.Thread(target=analyze_category, args=("IT Services", it_services_dfs))
    communication_services_thread = threading.Thread(target=analyze_category, args=("Communication Services", communication_services_dfs))
    devices_thread = threading.Thread(target=analyze_category, args=("Devices", devices_dfs))
    
    software_thread.start()
    it_services_thread.start()
    communication_services_thread.start()
    devices_thread.start()
    
    # Wait for all threads to complete
    software_thread.join()
    it_services_thread.join()
    communication_services_thread.join()
    devices_thread.join()
    general_thread.join()
    
    # Get results from the dictionary
    software_analysis = results["software_analysis"]
    it_services_analysis = results["it_services_analysis"]
    communication_services_analysis = results["communication_services_analysis"]
    devices_analysis = results["devices_analysis"]
    analysis = results["analysis"]

    emit_progress(socketio, clientID, timeline_event("Spend Data Analysis", "spend_data_analysis", True))
    emit_progress(socketio, clientID, analysis)
    
    eligible_projects = ProjectsDao.FetchAvailableProject(tenantID, userID)

    projectInformation = view_projects(eligible_projects, tenantID, userID)


    
   #yield "Tango is analyzing your spend data for data center systems... \n\n"
    # emit_progress(socketio, clientID, timeline_event("Data Center Systems", "data_center_systems", False))
    # data_center_analysis = analyze_spend_by_data_center_category(llm, eligible_projects, tenantID, saved_corpus, projectInformation, analysis, tenantID, userID, sessionID)
    # emit_progress(socketio, clientID, ui_json(sessionID))
    # emit_progress(socketio, clientID, timeline_event("Data Center Systems", "data_center_systems", True))

    # Create threads for each analysis
    software_thread = threading.Thread(
        target=lambda: process_category(
            "Software", 
            "software",
            lambda: analyze_spend_by_software_category(llm, eligible_projects, tenantID, saved_corpus, projectInformation, software_analysis, tenantID, userID, sessionID)
        )
    )
    
    it_services_thread = threading.Thread(
        target=lambda: process_category(
            "IT Services", 
            "it_services",
            lambda: analyze_spend_by_it_services_category(llm, eligible_projects, tenantID, saved_corpus, projectInformation, it_services_analysis, tenantID, userID, sessionID)
        )
    )
    
    comm_services_thread = threading.Thread(
        target=lambda: process_category(
            "Communication Services", 
            "communication_services",
            lambda: analyze_spend_by_communication_services_category(llm, eligible_projects, tenantID, saved_corpus, projectInformation, communication_services_analysis, tenantID, userID, sessionID)
        )
    )
    
    devices_thread = threading.Thread(
        target=lambda: process_category(
            "Devices", 
            "devices",
            lambda: analyze_spend_by_devices_category(llm, eligible_projects, tenantID, saved_corpus, projectInformation, devices_analysis, tenantID, userID, sessionID)
        )
    )
    
    # Dictionary to store results
    results = {
        "software_analysis": software_analysis,
        "it_services_analysis": it_services_analysis,
        "communication_services_analysis": communication_services_analysis,
        "devices_analysis": devices_analysis
    }
    
    # Helper function to process each category
    def process_category(name, key, analysis_func):
        result = analysis_func()
        results[f"{key}_analysis"] = result
        emit_progress(socketio, clientID, ui_json(sessionID))
        emit_progress(socketio, clientID, timeline_event(name, key, True))
    
    # Start all threads
    software_thread.start()
    it_services_thread.start()
    comm_services_thread.start()
    devices_thread.start()
    
    # Wait for all threads to complete
    software_thread.join()
    it_services_thread.join()
    comm_services_thread.join()
    devices_thread.join()
    
    # Get results from the dictionary
    software_analysis = results["software_analysis"]
    it_services_analysis = results["it_services_analysis"]
    communication_services_analysis = results["communication_services_analysis"]
    devices_analysis = results["devices_analysis"]
    
    overall = f"""
    Here is the breakdown of spend by various categories:
    
    Software:
    {software_analysis}

    IT Services:
    {it_services_analysis}

    Communication Services:
    {communication_services_analysis}

    Devices:
    {devices_analysis}

    Spend Related Calculations:
    {analysis}
    """
    

    #yield "Tango is now performing a final overall analysis on your data."

    overall_analsis = analyze_overall_spend(
        llm,
        overall,
        sessionID,
        tenantID,
        userID,
    )
    emit_progress(socketio, clientID, timeline_event("Overall Analysis", "overall_analysis", True))
    emit_progress(socketio, clientID, stop_show_timeline())

    everything_combined = f"""
    Overall:
    {overall_analsis}
    
    Ask the user if they would like to delve further into any of the four categories: software, it services, communication services, devices.
    """

    response_json = {
        "response": everything_combined
    }
    return response_json
    
    