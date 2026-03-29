from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question
from src.trmeric_services.agents.core.agent_functions import AgentFunction,AgentFnTypes
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.dao import TangoDao, ProjectsDao
from src.trmeric_services.agents.prompts.agents import portfolio, vrz
import json
from src.trmeric_api.logging.AppLogger import appLogger
import traceback
from uuid import UUID
import datetime
import re
import os


def format_output(output):
    """format the output to be sent to the user"""
    return output["message_for_user"]


event_states = {
    "value_event": False,
    "doc_event": False,
    "learnings_event": False,
    "revisit_event": False,
    "actions_event": False,
    "end_event": False,
}

def emit_event(event_key, emit_data, socketio, client_id):
    """emit socketio events"""
    print("emit event -- fn ---- ",  event_key, emit_data)
    # if not event_states[event_key]:  
    for payload in emit_data:    
        socketio.emit("value_realization", payload, room=client_id)
    event_states[event_key] = True  


def handle_value_event(response, socketio, client_id,project_id,key_result_id):

    baseline_value = response["baseline_value"]
    planned_value = response["planned_value"]
    achieved_value = response["achieved_value"]
    # print("--debug inside handle_value_event","--ids", f"{project_id} + {key_result_id} + {planned_value ,achieved_value}")
    print("debug -- handle_value_event ", planned_value,  achieved_value, baseline_value)
    if baseline_value:
        emit_event("value_event", [
            {"event": "timeline", "data": {"text": "Reflection on Chart", "key": "values", "is_completed": False,"project_id": project_id,"key_result_id": key_result_id}},
                {"event": "values", "data": {"project_id": project_id,"key_result_id": key_result_id,"baseline_value": baseline_value}},
            {"event": "timeline", "data": {"text": "Reflection on Chart", "key": "values", "is_completed": True,"project_id": project_id,"key_result_id": key_result_id}},
            {"event": "values", "data": "<<end>>"},
        ],socketio, client_id)
    if planned_value or achieved_value:
        emit_event("value_event", 
            [
                {"event": "timeline", "data": {"text": "Reflection on Chart", "key": "values", "is_completed": False,"project_id": project_id,"key_result_id": key_result_id}},
                {"event": "values", "data": {"project_id": project_id,"key_result_id": key_result_id,
                    "planned_value": planned_value,"achieved_value": achieved_value
                }},
                {"event": "timeline", "data": {"text": "Reflection on Chart", "key": "values", "is_completed": True,"project_id": project_id,"key_result_id": key_result_id}},
                {"event": "values", "data": "<<end>>"},
            ], 
        socketio, client_id)

def handle_doc_event(response, socketio, client_id,project_id,key_result_id,session_id,user_id):

    should_upload_doc = response["trigger_upload_doc"]
    doc_uploaded = response["doc_uploaded_by_user"]
    # if last_user_message == f"""I have uploaded the documents.""":
    #     has_user_uploaded_doc =True
        
    doc_state = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id, user_id, key="value_realization_conv_docs_uploaded")
    has_user_uploaded_doc = None
    if doc_state and doc_state[0].get('value'):
        try:
            has_user_uploaded_doc = doc_state[0]['value']
            # print("--debug ref_docs_msg", has_user_uploaded_doc)
        except json.JSONDecodeError as e:
            print("--debug JSON decode error:", e)
    print("--debug inside handle_doc_event userMsg: ",doc_state, has_user_uploaded_doc )

    currentDate = datetime.datetime.now().date().isoformat()

    # print("--debug inside handle_doc_event","--ids", f"{project_id} + {key_result_id} + {should_upload_doc} + {doc_uploaded} + {has_user_uploaded_doc}")

    if should_upload_doc == "true":
        emit_event("doc_event", 
            [
                {"event": "timeline", "data": {"text": "Reference Documents", "key": "ref_docs", "is_completed": False,"project_id": project_id,"key_result_id": key_result_id}},
                {"event": "ref_docs", "data": {"project_id": project_id, "key_result_id": key_result_id}},
                {"event": "ref_docs", "data": "<<end>>"},
            ], 
        socketio, client_id)
        
    if doc_uploaded == "true" and has_user_uploaded_doc ==f"""I have uploaded the documents.""":
        emit_event("doc_event", 
            [
                # {"event": "timeline", "data": {"text": "Reference Documents", "key": "ref_docs", "is_completed": False,"project_id": project_id,"key_result_id": key_result_id}},
                # {"event": "ref_docs", "data": {"project_id": project_id, "key_result_id": key_result_id, "ref_docs": data}},
                {"event": "activity", "data": {"title": "Resources added", "desc": f"Updated at {currentDate}", "icon": "resources","project_id": project_id,"key_result_id": key_result_id}},
                {"event": "timeline", "data": {"text": "Reference Documents", "key": "ref_docs", "is_completed": True,"project_id": project_id,"key_result_id": key_result_id}},
            ], 
        socketio, client_id)
        

def handle_learnings_event(response, socketio, client_id,project_id,key_result_id):

    key_learnings = response["key_learnings"]
    # print("--debug inside handle_learnings_event","--ids", f"{project_id} + {key_result_id} + keyLearningsLen:{len(key_learnings)}")

    if len(key_learnings) > 0:
        emit_event("learnings_event", 
            [
                {"event": "timeline", "data": {"text": "Key Learnings", "key": "key_learnings", "is_completed": False,"project_id": project_id,"key_result_id": key_result_id}},
                {"event": "key_learnings", "data": {
                    "project_id": project_id,
                    "key_result_id": key_result_id,
                    "key_learnings": key_learnings
                }},
                {"event": "timeline", "data": {"text": "Key Learnings", "key": "key_learnings", "is_completed": True,"project_id": project_id,"key_result_id": key_result_id}},
                {"event": "key_learnings", "data": "<<end>>"},
            ],
        socketio, client_id)

def handle_revisit_event(response, socketio, client_id,project_id,key_result_id):

    revisit_schedule = response["revisit_date"]
    print("--debug inside handle_learnings_event","--ids", f"{project_id} + {key_result_id} + {revisit_schedule}")

    if(revisit_schedule != ""):
        emit_event("revisit_event", 
            [
                {"event": "timeline", "data": {"text": "Schedule Revisit", "key": "revisit", "is_completed": False,"project_id": project_id,"key_result_id": key_result_id}},
                # {"event": "revisit", "data": {
                #     "project_id": project_id,
                #     "key_result_id": key_result_id,
                #     "revisit": revisit_schedule
                # }},
                {"event": "activity", "data": {"title": "Planned Revisit", "desc": f"Revisit scheduled on {revisit_schedule}", "icon": "revisit","project_id": project_id,"key_result_id": key_result_id}},
                {"event": "timeline", "data": {"text": "Schedule Revisit", "key": "revisit", "is_completed": True,"project_id": project_id,"key_result_id": key_result_id}},
                # {"event": "revisit", "data": "<<end>>"},
            ], 
        socketio, client_id)

def handle_actions_event(response, socketio, client_id,project_id,key_result_id):

    key_actions = response["key_actions"]
    print("--debug inside handle_actions_event","--ids", f"{project_id} + {key_result_id} + actionsLen:{len(key_actions)}")

    if(len(key_actions) > 0):
        emit_event("actions_event", 
            [
                {"event": "timeline", "data": {"text": "Key Actions", "key": "key_actions", "is_completed": False,"project_id": project_id,"key_result_id": key_result_id}},
                {"event": "key_actions", "data": {
                    "project_id": project_id,
                    "key_result_id": key_result_id,
                    "key_actions": key_actions
                }},
                {"event": "activity", "data": {"title": "Key Actions", "desc": f"{len(key_actions)} Actions to notify", "icon": "decline","project_id": project_id,"key_result_id": key_result_id}},
                {"event": "timeline", "data": {"text": "Key Actions", "key": "key_actions", "is_completed": True,"project_id": project_id,"key_result_id": key_result_id}},
                {"event": "key_actions", "data": "<<end>>"},
            ], 
        socketio, client_id)


def handle_end_event(response, socketio, client_id,project_id,key_result_id):

    vr_ended = response["has_value_realization_completed"]
    print("--debug inside handle_end_event","--ids", f"{project_id} + {key_result_id} + {vr_ended}")

    # socketio.emit("value_realization_ended",{"event": "end","data": "<<end>>"},room=client_id)
    if(vr_ended == "true"):
        emit_event("end_event", 
            [
                # {"event": "activity", "data": {"title": "Key Actions", "desc": "Action to notify on high alert", "icon": "decline","project_id": project_id,"key_result_id": key_result_id}},
                # {"event": "timeline", "data": {"text": "Key Actions", "key": "key_actions", "is_completed": True,"project_id": project_id,"key_result_id": key_result_id}},
                {"event": "value_realization_ended", "data": {"project_id": project_id,"key_result_id": key_result_id}},
            ], 
        socketio, client_id)
        appLogger.info({"event":"value_realization","status":"completed","project_id":project_id})

def process_vr_response(response,socketio,client_id,project_id,key_result_id,session_id,user_id):
    try:
        print("--debug processing vr response",response)

        #event handlers:
        handle_value_event(response, socketio, client_id,project_id,key_result_id)

        handle_doc_event(response, socketio, client_id,project_id,key_result_id,session_id,user_id)

        handle_learnings_event(response, socketio, client_id,project_id,key_result_id)

        handle_revisit_event(response, socketio, client_id,project_id,key_result_id)

        handle_actions_event(response, socketio, client_id,project_id,key_result_id)

        #event for ending value realization
        handle_end_event(response, socketio, client_id, project_id, key_result_id)

    except Exception as e:
        print("--debug error in process_vr_response",e)
        appLogger.error({
            "event": "process_vr_response",
            "error": e,
            "traceback": traceback.format_exc()
        })


def value_realization(
    tenantID: int,
    userID: int,
    llm= None,
    model_opts=None,
    socketio=None,
    client_id=None,
    logInfo=None,
    last_user_message=None,
    sessionID=None,
    project_id=None,
    key_result_id=None,
    **kwargs
):
    sender = kwargs.get("step_sender") or None
    print("debug -- value_realization ", tenantID, userID, last_user_message, "ses --", sessionID,
        project_id,
        key_result_id
    )
    # last_user_message = kwargs.get("last_user_message")
    
    if last_user_message:
        TangoDao.insertTangoState(
            tenant_id=tenantID, 
            user_id=userID,
            key="value_realization_conv", 
            value=f"User: {last_user_message}", 
            session_id=sessionID
        )
        
    if project_id and key_result_id:
        ## save them in tango state.. so the i can ask keep processing them later
        TangoDao.insertTangoState(
            tenant_id=tenantID, 
            user_id=userID,
            key="value_realization_conv_project_and_key_result", 
            value=json.dumps({
                "project_id": project_id,
                "key_result_id": key_result_id
            }),
            session_id=sessionID
        )
    
    try:
        project_and_key_id_data = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key="value_realization_conv_project_and_key_result")
        # print("--debug project_and_key_id_data", project_and_key_id_data)

        project_and_key_id_data = json.loads(project_and_key_id_data[0]['value'])
        # print("--debug project_and_key_id_data",project_and_key_id_data)
        project_id_in_conv = project_and_key_id_data["project_id"]
        key_result_id_in_conv = project_and_key_id_data["key_result_id"]
        
        key_result_detail = ProjectsDao.fetchProjectKeyResultInfo(
            project_id=project_id_in_conv, 
            key_result_id=key_result_id_in_conv
        )
        
        appLogger.info({"event":"value_realization","status":"context_fetched","tenant_id":tenantID,"project_id":project_id})
        socketio.emit("value_realization",{
            "event": "timeline",
            "data": {"text":"Waiting for user input","key":"user_input","is_completed": True, "baseline_value": key_result_detail[0]["baseline_value"],
                     "project_id": project_id_in_conv,"key_result_id": key_result_id_in_conv}
            },
            room=client_id
        )
        print("obtained from tango state idsss -", project_id_in_conv, key_result_id_in_conv, key_result_detail)
        
        #project context to add??
        # project_details = ProjectsDao.fetch_project_details(project_id=project_id_in_conv)
        kr_header_prompt = vrz.kr_desc_prompt(key_result_detail)
        response = llm.run(kr_header_prompt, model_opts , 'agent::value_realization', logInfo)
        response = extract_json_after_llm(response,step_sender=sender)
        # print("--debug kr_header_prompt",response)
        
        if not response:
            print("--no key result found----")
            sender.sendError(key=f"No key result found",function="value_realization")
            return
        
        planned_value = response["planned_value"]
        socketio.emit("value_realization",{
            "event": "extra_data",
            "data": {"text":response["header"],"value": planned_value,"project_id": project_id_in_conv,"key_result_id": key_result_id_in_conv}
            },
            room=client_id
        )
        

        conv = TangoDao.fetchTangoStatesForSessionIdAndUserAndKeyAllValue(session_id=sessionID, user_id=userID, key="value_realization_conv")[::-1]
        # print("--debug conv", conv)
        prompt = vrz.value_realization_prompt3(conv, planned_value, project_data=None, key_result_data=key_result_detail,)
        # print("--prompt\n", prompt.formatAsString())
        
        response = llm.run(prompt, model_opts , 'agent::value_realization', logInfo)
        # print("--response\n", response)
        response = extract_json_after_llm(response,step_sender=sender)
        # print("--debug response1------", response)

        
        TangoDao.insertTangoState(
            tenant_id=tenantID, 
            user_id=userID,
            key="value_realization_conv", 
            value=f"Value Realization Agent: {str(response)}", 
            session_id=sessionID
        )

        if not response:
            print("--debug no response of valueRealization------------")
            appLogger.info({"event":"value_realization","status":"prompt_failed","tenant_id":tenantID,"project_id":project_id})
            return

        #to handle ref docs timeline
        # is_docs_uploaded = True if conv == "I have uploaded the documents." else False
        ref_docs_msg_data = None
        if last_user_message == f"""I have uploaded the documents.""":
            TangoDao.upsertTangoState(
                tenant_id=tenantID, 
                user_id=userID,
                key="value_realization_conv_docs_uploaded", 
                value=last_user_message, 
                session_id=sessionID
            )

            ref_docs_json = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key="value_realization_conv_docs_uploaded")
            # print("--debug ref_docs_msg_data", ref_docs_json)
            if ref_docs_json and ref_docs_json[0].get('value'):
                try:
                    ref_docs_msg_data = ref_docs_json[0]['value']
                    print("--debug ref_docs_msg", ref_docs_msg_data)
                except json.JSONDecodeError as e:
                    appLogger.error({"event": "value_realization_docs_json","error": e,"traceback": traceback.format_exc()})
            else:
                print("--debug no value in ref_docs_json--------------------")

        process_vr_response(
            response = response,
            socketio = socketio,
            client_id=client_id,
            project_id = project_id_in_conv,
            key_result_id=key_result_id_in_conv,
            session_id =sessionID,
            user_id =userID
        )
        
        # socketio.emit("value_realization_all_data", response, room=client_id)
        appLogger.info({"event":"value_realization","status":"process_vr_response:done","tenant_id":tenantID,"project_id":project_id})
        # return format_output(output=response)
    
    
        #streaming
        response1 = json.dumps(response,indent=2)
        assistPrompt = vrz.user_assist_promptV2(conv, response1)
        # print("--debug assistPrompt", assistPrompt.formatAsString())
        suggestion_string = ''
        for chunk in llm.runWithStreaming(assistPrompt,model_opts ,"agent::value_realization",logInDb=logInfo):
            # print("--debug chunk", chunk)
            suggestion_string +=chunk
            yield chunk
        print("--debug suggestion_string---", suggestion_string)
    

    except Exception as e:
        print("--debug error fetching project-key ids",e)
        sender.sendError(key=f"Error fetching Project details",function="value_realization")
        appLogger.error({
            "event": "VR ids from conv",
            "error": e,
            "traceback": traceback.format_exc()
        })

    ############################################################################################################################################
    
 

RETURN_DESCRIPTION = """
    This function is responsible for creation of value realization of the project which has been completed.
"""

ARGUMENTS = [
    {
        "name": "project_id",
        "type": "int",
        # "required": 'true',
        "description": """Project Id that user wants to create this value on""",
    },
    {
        "name": "key_result_id",
        "type": "int",
        # "required": 'true',
        "description": """Key Result Id that user wants to create this value on""",
    },
]

VALUE_REALIZATION = AgentFunction(
    name="value_realization",
    description="""
       This function is responsible for creation of value realization of the project which has been completed.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=value_realization,
    return_type="YIELD",
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name
)


#temp code:

    # def format_output(output):
    #     yield_after = {
    #         "agent_add_source": [
    #             {
    #                 "label": "Add Sources",
    #                 "key": "VALUE_REALIZATION"
    #             }
    #         ]
    #     }
    #     Convert yield_after dictionary to a JSON string with indentation
    #     formatted_json = json.dumps(yield_after, indent=4)
    #     print("--debug formatted_json", formatted_json)

    #     # Prepare the response message including the message_for_user and JSON output
    #     response = f"{output['message_for_user']}\n\n```json\n{formatted_json}\n```"
    #     return response


    #tempcode:

        #  if response:
        # #track events
        # value_event = False
        # doc_event = False
        # learnings_event = False
        # revisit_event = False
        # actions_event = False

        # planned_value = 0
        # acheived_value = 0
        # should_upload_doc = False
        # key_learnings=[]    
        # key_actions = []    
        # activity_feed = {}
        # revisit_schedule = ""
            # planned_value = response["planned_value"]
            # acheived_value = response["achieved_value"]
            # should_upload_doc = response["trigger_upload_doc"]
            # key_learnings = response["key_learnings"]
            # key_actions = response["key_actions"]
            # revisit_schedule = response["revisit_schedule"]

            # print("--debug values", planned_value,acheived_value)
            # # print("--debug response activity", response["activity_feed"])

            # if(value_event== False):
            #     if(planned_value and acheived_value):
            #         # socketio.emit("value_realization_timeline",{"text":"Reflection on Chart","key":"values","is_completed": False},room=client_id)

            #         #timeline start 
            #         socketio.emit("value_realization",{
            #                 "event": "timeline",
            #                 "data": {"text":"Reflection on Chart","key":"values","is_completed": False}
            #             },
            #             room = client_id
            #         )

            #         #data given
            #         socketio.emit("value_realization",{
            #                 "event": "values",
            #                 "data": {
            #                     "project_id": project_id_in_conv,
            #                     "key_result_id": key_result_id_in_conv,
            #                     "planned_value": planned_value,
            #                     "achieved_value": acheived_value
            #                 }
            #             },
            #             room = client_id
            #         )
            #         #timeline end : true
            #         socketio.emit("value_realization",{
            #                 "event": "timeline",
            #                 "data": {"text":"Reflection on Chart","key":"values","is_completed": True}
            #             },
            #             room = client_id
            #         )

            #         #event ended
            #         socketio.emit("value_realization",{"event":"values", "data": "<<end>>"},room=client_id)
            #         value_event = True
            # #for ref_docs
            # if(doc_event == False):
            #     socketio.emit("value_realization",{
            #                 "event": "timeline",
            #                 "data": {"text":"Reference Documents","key":"ref_docs","is_completed": False}
            #             },
            #             room = client_id
            #         )
            #     if(should_upload_doc == "true"):
            #         socketio.emit("value_realization",{
            #                 "event": "timeline",
            #                 "data": {"text":"Reference Documents","key":"ref_docs","is_completed": True}
            #             },
            #             room = client_id
            #         )
            #         # ref_doc_activity = response["activity_feed"]["is_doc_uploaded"]
            #         socketio.emit("value_realization",{
            #             "event": "ref_docs",
            #             "data": {
            #                 "project_id": project_id_in_conv,
            #                 "key_result_id": key_result_id_in_conv,
            #             }
            #         })
            #         socketio.emit("value_realization",{
            #             "event": "activity",
            #             "data": {
            #                 "title": "Resources added",
            #                 "desc": "Updated 5 mins ago",
            # 	            "icon": "resources" 
            #             }
            #         })

            #         # socketio.emit("value_realization",{
            #         #     "event": timeline, value/action/learning/revisit,
            #         #     "activity": true/false,
            #         #     "data": <<end>>, {}
            #         # })

            #         #logic to process further
            #         # socket.emit("value_realization",{
            #         #     "event": "ref_docs",
            #         #     "data": {
            #         #     }
            #         # })
    
            #         # generic agent event for : Doc upload
            #        api: 
            # #       curl --location 'http://localhost:8000/api/document/upload/' \
            #     --form 'type="PROJECT_VR"' \
            #     --form 'file=@"/Users/siddharth/Downloads/instagram.png"' \
            #     --form 'project_id="693"'
            #  url = os.getenv("DJANGO_BACKEND_URL") + f"api/projects/tango/status/add/{project_id}"
            #         headers = {
            #             "Content-Type": "application/json"
            #         }

            #             # 
            #             # ["tango_chat_onboarding","\njson\n{
            #             # \n    \"value_realization_source\": 
            #             #   [\n        {
            #             #   \n            \"label\": \"Add Sources\",\n           
            #             #  \"key\": \"TANGO_ONBOARDING_PROFILE\"\n       
            #             #    }\n    ]\n}\n\n    \n"
            #             # ]
            #         socketio.emit("value_realization",{"event":"ref_docs", "data": "<<end>>"},room=client_id)
            #         doc_event ==True

            # #key learnings
            # if(learnings_event == False):
            #     socketio.emit("value_realization",{
            #                 "event": "timeline",
            #                 "data": {"text":"Key Learnings","key":"key_learnings","is_completed": False},
            #             },
            #             room = client_id
            #         )
            #     if(len(key_learnings)>0):
            #         #trigger its event
            #         # socketio.emit("value_realization_timeline",{"text":"Key Learnings","key":"key_learnings","is_completed": True},room=client_id)            
            #         socketio.emit("value_realization",{
            #                 "event": "timeline",
            #                 "data": {"text":"Key Learnings","key":"key_learnings","is_completed": True},
            #             },
            #             room = client_id
            #         )
                    
            #         socketio.emit("value_realization",{
            #                 "event": "key_learnings",
            #                 "data": {
            #                     "project_id": project_id_in_conv,
            #                     "key_result_id": key_result_id_in_conv,
            #                     "key_learnings": key_learnings
            #                 }
            #             },
            #             room = client_id
            #         )
            #         socketio.emit("value_realization",{"event":"key_learnings", "data": "<<end>>"},room=client_id)
            #         learnings_event = True

            
            # #revisit
            # if(revisit_event == False):
            #     socketio.emit("value_realization",{
            #                 "event": "timeline",
            #                 "data": {"text":"Schedule Revisit","key":"revisit","is_completed": False}},
            #             room = client_id
            #         )

            #     # revisit_activity = response["activity_feed"]["is_revisit_scheduled"]
            #     if(revisit_schedule != ""):
            #         socketio.emit("value_realization",{
            #                 "event": "timeline","data": {"text":"Schedule Revisit","key":"revisit","is_completed": True}},
            #             room = client_id
            #         )
            #         socketio.emit("value_realization",{
            #                 "event": "revisit",
            #                 "data": {"project_id": project_id_in_conv,"key_result_id": key_result_id_in_conv,"revisit": revisit_schedule},
            #             },
            #             room = client_id
            #         )
            #         socketio.emit("value_realization",{
            #                 "event": "activity",
            #                 "data": {"title": "Planned Revisit","desc": "Revisit scheduled in another 14 days ","icon": "revisit"}
            #             },
            #             room = client_id
            #         )

            #         # socketio.emit("value_realization_activity",{"event":"revisit","data": { "project_id": project_id_in_conv,"key_result_id": key_result_id_in_conv}},room=client_id)            
            #         socketio.emit("value_realization",{"event":"revisit", "data": "<<end>>"},room=client_id)
            #         revisit_event = True

            
            # #key actions
            # if(actions_event == False):
            #     socketio.emit("value_realization",{
            #             "event": "timeline",
            #             "data": {"text":"Key Actions","key":"key_actions","is_completed": False}},
            #             room = client_id
            #     )
            #     if(len(key_actions)>0):
            #         #trigger its event
            #         socketio.emit("value_realization",{
            #                 "event": "timeline","data": {"text":"Key Actions","key":"key_actions","is_completed": True}},
            #                 room = client_id
            #         )
            #         # action_activity = response["activity_feed"]["is_actions_added"]
            #         socketio.emit("value_realization",{
            #                 "event": "key_actions",
            #                 "data": {
            #                     "project_id": project_id_in_conv,
            #                     "key_result_id": key_result_id_in_conv,
            #                     "key_actions": key_actions
            #                 }
            #             },
            #             room = client_id
            #         )  
            #         socketio.emit("value_realization",{
            #                 "event": "activity",
            #                 "data": {"title": "Value declines","desc": "Action to notify on high alert","icon": "decline"}
            #             },
            #             room = client_id
            #         )
    
            #         socketio.emit("value_realization",{"event":"key_actions", "data": "<<end>>"},room=client_id)
            #         actions_event = True