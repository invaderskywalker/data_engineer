import re
import json
import time
import requests
import traceback
import concurrent.futures
from src.trmeric_s3.s3 import S3Service
from src.trmeric_database.dao import TangoDao
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.provider.quantum.utils import *
from src.trmeric_services.provider.prompts.Quantum import *
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_utils.web.CompanyScraper import CompanyInfoScraper
from src.trmeric_utils.web.SocialMediaScraper import SocialMediaScraper
from src.trmeric_services.summarizer.SummarizerService import SummarizerService
from src.trmeric_services.agents.core.agent_functions import AgentFunction,AgentFnTypes,AgentReturnTypes



SECTIONS = [
    {"section": "core_capabilities", "timeline": "Fetching Core capabilities"},
    {"section": "service_catalog", "timeline": "Extracting Service offerings"},
    {"section": "ways_of_working", "timeline": "Framing Ways of Working"},
    {"section": "case_studies", "timeline": "Looking for Case studies"},
    {"section": "certifications_and_audit", "timeline": "Acquiring Audit & Certifications."},
    {"section": "leadership_and_team", "timeline": "Showcasing Leadership team"},
    {"section": "voice_of_customer", "timeline": "Collecting Customer Voice"},
    {"section": "information_and_security","timeline": "Strengthening Security measures"},
    # {"section": "partnerships", "timeline": "Establishing Strategic Partnerships"},
    # {"section": "offers", "timeline": "Creating promotional offers"}
]


SUMMARIZATION_MSG = """You are Quantum agent responsible for Onboarding Providers onto Trmeric Platform which is a B2B AI-SaaS company.
        For the given information, you have to fetch all the necessary data points which will be used in preparing the onboarding profile for the user
        i.e. Company context, Service catalogs, Offers, Certifications, publications etc.
"""



def scraper_service(type,logInfo=None,website_url=None):
    match type:
        case "company":
            return CompanyInfoScraper(landing_page_url=website_url)
        case "social_media":
            return SocialMediaScraper()
        case "docs": 
            return S3Service()
        case "summarize":
            return SummarizerService(logInfo=logInfo,word_count_threshold=60000)
        case _:
            return None
    
def quantum_service(
    tenantID: int, 
    userID: int, 
    llm= None,
    logInfo= None,
    socketio=None,
    client_id=None,
    sessionID= None,
    last_user_message=None,
    **kwargs
):
    
    model_opts2 = ModelOptions(model="gpt-4.1", max_tokens=10000, temperature=0.1)
    """Build the quantum service for the provider"""
    print("---debug inside quantum_service---------",tenantID,userID,model_opts2.model)
    try:
        sender = kwargs.get("step_sender") or None
        print("--debug [Quantum] last msg---", last_user_message)
        
        if last_user_message:
            TangoDao.insertTangoState(
                tenant_id=tenantID,
                user_id=userID,
                key="quantum_conv",
                value=json.dumps(last_user_message),
                session_id=sessionID
            )
            
        conv_ = TangoDao.fetchTangoStatesForSessionIdAndUserAndKeyAll(session_id=sessionID, user_id=userID, key="quantum_conv")
        # print("--debug [Quantum] conversation history---", conv_)

        context = {"company_website": "","social_media_links": [],"uploaded_docs": []}
        message,quantum_inputs = parse_latest_conv(conv_,context,tenantID)
        # print("\n\n--debug message,quantum inputs-----", message,'\n', quantum_inputs)
        
        if quantum_inputs:
                        
            input_context = analyze_inputs(context,sender=sender)
            # print("--debug [Processed Context]---", input_context)
            links_traversed = input_context.get("links",[]) or []
            image_links = input_context.get("imgs",[]) or []
            print("\n\n---debug links_traversed-----", links_traversed,'\nImages: ', len(image_links))
            
            if input_context is None or len(links_traversed)==0:
                socketio.emit('quantum_agent', {
                    "event": 'quantum_canvas_error',
                    'status':{"message":f"Something went wrong, {len(links_traversed)} links traversed)"},
                    'data': None
                }, 
                room=client_id)
            
            sender.sendSteps(key="Analyzing inputs",val=False)
            
            #Idea is to execute parallel processing of input contexts #Send agentic timeline while above goes and inform the user about the fetched details & missing line items
            summarization_message = SUMMARIZATION_MSG
            formatted_context = {
                "website": input_context.get("website","") or "",
                "social_media": input_context.get("social_media","") or "",
                "uploaded_docs": input_context.get("uploaded_docs","") or ""
            }

            summarization_results = {"website": None, "social_media": None, "uploaded_docs": None}
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = []

                #task configurations with event messages
                tasks = [
                    {"identifier": "website",   "data": formatted_context["website"],"event_message": "Retrieving Company website"},
                    {"identifier": "social_media","data": formatted_context["social_media"],"event_message": "Fetching Social Media Links"},
                    {"identifier": "uploaded_docs",   "data": formatted_context["uploaded_docs"],"event_message": "Scanning Uploaded Documents"}
                ]
                
                for task in tasks:
                    # print("--debug task----", task)
                    identifier = task["identifier"]
                    data = task["data"]
                    event_message = task["event_message"]
                    
                    if data:  
                        sender.sendSteps(key=event_message,val=False)
                        futures.append((identifier,event_message, 
                            executor.submit(
                                scraper_service("summarize",logInfo=logInfo).summarizer,
                                large_data=data,
                                message=summarization_message,
                                identifier=identifier
                            )
                        ))

                for identifier, event_message, future in futures:
                    try:
                        result = future.result()  
                        summarization_results[identifier] = result if result else "No summary generated"
                        
                        sender.sendSteps(key=event_message,val=True)
                        # socketio.emit('quantum_agent', {"event": 'timeline', 'data': {"text":event_message,'is_completed':True}}, room=client_id)
                    except Exception as e:
                        summarization_results[identifier] = f"Error: {str(e)}"
                        print(f"--debug error processing {identifier}: {e}, {traceback.format_exc()}")
            
            # with open('summmarized_context.json', 'w') as file:
            #     json.dump(summarization_results, file, indent=4)
            
            # Analyze summarized results
            prompt = analyze_inputs_prompt(summarization_results)
            # print("\n --debug [Summarized results]----", prompt.formatAsString())
            result = llm.run(prompt, model_opts2, 'quantum_agent::analyze_inputs', logInfo,socketio=socketio,client_id=client_id)
            response = extract_json_after_llm(result,step_sender=sender)

            clarifying_info = response.get("clarifying_information", "")
            next_question = response.get("question_to_ask", "")
            
            sender.sendSteps(key="Analyzing inputs",val=True)
            socketio.emit('quantum_agent', {"event": 'quantum_qna',
                'data': {"clarifying_info": clarifying_info,"next_question": next_question}
            }, room=client_id)
            
                
            TangoDao.insertTangoState(
                tenant_id=tenantID, 
                user_id=userID,
                key=f"quantum_input_context_{tenantID}", 
                value= json.dumps({
                    "website": summarization_results["website"],
                    "social_media": summarization_results["social_media"],
                    "uploaded_docs": summarization_results["uploaded_docs"],
                    "image_links": image_links,
                    "links":links_traversed
                }), 
                session_id=sessionID
            )

            if not response:
                print("--debug no response of quantum inputs------------")
                appLogger.error({"event":"quantum_service","status":"analyze_inputs_failed","tenant_id":tenantID,"traceback":traceback.format_exc()}) 
            return
        
        
        if message is not None:
            print("--debug [Quantum] User provided message:", message)
            TangoDao.insertTangoState(
                tenant_id=tenantID,
                user_id=userID,
                key=f"quantum_user_response_{tenantID}_{userID}",
                value=json.dumps(message),  # Ensure message is string
                session_id=sessionID
            )
            create_quantum_canvas(
                tenantID=tenantID,
                userID=userID,
                sessionID=sessionID,
                llm=llm,
                model_opts=model_opts2,
                socketio=socketio,
                client_id=client_id,
                logInfo=logInfo,
                step_sender = sender
            )
            return
        
    except Exception as e:
        print("error in quantum_service", str(e))
        appLogger.error({"event":"quantum_service","error":str(e),"tenant_id":tenantID,"traceback":traceback.format_exc()})
        


def analyze_inputs(context,sender=None):
    
    # print("\n\n--debug analyze_inputs context---", len(context))
    try:
        result = {"website": "","social_media": "","uploaded_docs": "","links": [],"imgs": []}
        
        website = context.get("company_website",None)
        social_media = context.get("social_media_links",[])
        uploaded_docs = context.get("uploaded_docs",[])
        
        # print("\n\n---debug analyze_inputs-------", social_media,website,uploaded_docs)
        appLogger.info({"event":"analyze_inputs","data": context})
        if website:
            if website.startswith("http://"):
                # Replace http:// with https://
                website = "https://" + website[7:]
            elif not website.startswith("https://"):
                # Add https:// if no protocol is present
                website = "https://" + website
            
            company_service = CompanyInfoScraper(landing_page_url=website)
            scraped_data = company_service.scrape_v2()
            # with open("company_data.json", 'w') as file:
            #     json.dump(scraped_data, file, indent=4)
            
            if scraped_data is None or len(scraped_data.get("data",""))<=1000:
                print("---debug calling fallback------------")
                
                sender.sendSteps(key="Please wait, retrieving!",val=False)
                
                fallback = fetch_company_info(website=website)
                data = fallback.get("company_info", "") or ""
                links = fallback.get("links",[]) or []
                imgs = []
                
                sender.sendSteps(key="Please wait, retrieving!",val=True)
            else:
                data = scraped_data.get("data","") or ""
                links = scraped_data.get("links",[]) or []
                imgs = scraped_data.get("image_links",[]) or []
            
            result["website"] += data if data else "$$$$$$NOTHING____FOUND#######"
            result["links"] = links
            result["imgs"] = imgs
                
        print("[result]", len(result["website"]))
        if social_media:
            # print("--debug social media111111")
            for item in social_media:
                platform  = item.get("type",None)
                url = item.get("address","")
                # print("--debug platform , url-----", platform, url)
                
                if platform and url:
                    social_media_scraper = SocialMediaScraper(url = url,limit=5).parse_result()
                    social_media_data = json.dumps(social_media_scraper)

                    data = f"From platform: {platform}\n\n {social_media_data}\n\n" if social_media_data else "$$$$$$NOTHING____FOUND#######"
                    
                    result["social_media"] += data 
            
        if uploaded_docs:
            for doc in uploaded_docs:
                key = doc.get("s3_key",None)
                data = None
                if key:
                    data= scraper_service("docs").download_file_as_text(s3_key=key)
                result["uploaded_docs"] += data if data else "$$$$$$NOTHING____FOUND#######"
                
        with open("inputs.json", 'w') as file:
            json.dump(result, file, indent=4)
    
        return result
    except Exception as e:
        print("error in analyze_inputs", str(e))
        appLogger.error({"event":"analyze_inputs","error":str(e),"traceback":traceback.format_exc()})
        return {"website": "","social_media": "","uploaded_docs": "","links": [],"imgs": []}
        
    
        
                                
                            
QUANTUM_ONBOARD = AgentFunction(
    name="quantum_onboard",
    description="This function will initiate the quantum process which is to prepare the blueprint for the Onboarding process of Providers in Trmeric platform.",
    args=[],
    return_description=f"""
        Yields message strings to guide the user through the scrapped web inputs about the provider and its company data and 
        provide assistance in onboarding process.
    """,
    function=quantum_service,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name,
    # return_type=AgentReturnTypes.YIELD.name
)


def create_quantum_canvas(
    tenantID,
    userID,
    sessionID,
    llm,
    model_opts,
    socketio,
    client_id,
    logInfo,
    step_sender
):
    print("\n\n--debug [create_quantum_canvas]-------", tenantID, userID, sessionID)
    try:
        sender = step_sender or None
        start_time = time.time()
        
        print("---debug modelopts----", model_opts.model,model_opts.max_tokens)
        
        context = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key=f"quantum_input_context_{tenantID}")
        
        context_value = {"website": "", "social_media": "", "uploaded_docs": "","image_links": [], "links": []}
        # print("\n\n\n---debug context-----", context)
        
        if len(context)>0:
            context_value = json.loads(context[0]['value'])
            # print("-----debug context value000000000", context_value,'\n\n\n\n\n')
        else:
            appLogger.error({"event":"create_quantum_canvas","status":"no_context","tenant_id":tenantID,"traceback":traceback.format_exc()})
            # socketio.emit('quantum_agent',{"event":'error','data': context_value},room=client_id)
            sender.sendError(key="Error retrieving context",function="create_quantum_canvas")
            return
        
        is_website, is_uploaded_docs, is_social_media = validate_inputs(context_value,tenantID,userID,socketio,client_id)
        # print("\n\n---debug all [Context] checks------", is_website, is_uploaded_docs, is_social_media)
                
        if (is_website and is_uploaded_docs and is_social_media):
            appLogger.error({"event":"quantum_service","status":"no_website","tenant_id":tenantID,"traceback":traceback.format_exc()})
            # socketio.emit('quantum_agent',{"event":'error',"context": "No valid inputs to proceed",'data': context_value},room=client_id)
            sender.sendError(key="No valid inputs to proceed",function="create_quantum_canvas")
            return
        
        clarifying_info = TangoDao.fetchTangoStatesForSessionIdAndUserAndKey(session_id=sessionID, user_id=userID, key=f"quantum_user_response_{tenantID}_{userID}")
        print("--debug [Clarifying Info]---", clarifying_info)
        
        company_info_ = {
            "website": context_value.get("website","No info available"),
            "social_media": context_value.get("social_media",None),
            "uploaded_docs": context_value.get("uploaded_docs",None),
            "clarifying_info": clarifying_info[0]['value'] if clarifying_info else None,
        }
        company_info = json.dumps(company_info_)
        imgs = context_value.get("image_links",[])
        links = context_value.get("links",[])
        # print("\n\n\n--debug fetched image_links-----", len(imgs), "\n\n Links traversed: ", links)
        
        socketio.emit('quantum_agent',{"event":'timeline','data': {"text":"Creating Quantum Canvas",'is_completed':False,'list':links}},room=client_id)
        #Quantum Canvas sections        
        sections = SECTIONS
        section_partnership = {"section": "partnerships", "timeline": "Establishing Strategic Partnerships"}
        section_offers = {"section": "offers", "timeline": "Creating promotional offers"}
        
        canvas_data = {}
        
        #ThreadPoolExecutor for parallel processing of all sections
        with ThreadPoolExecutor(max_workers=len(sections)) as executor:
            # Dictionary to map futures to section names
            futures = {}
            
            for section_ in sections:
                section = section_["section"]
                timeline = section_["timeline"]
                
                sender.sendSteps(key=timeline,val=False)
                # socketio.emit('quantum_agent',{"event":'timeline','data': {"text":timeline,'is_completed':False}},room=client_id)
                prompt_func = call_section_prompt(section)
                
                if prompt_func is None:
                    print(f"No prompt function defined for section: {section}")
                    canvas_data[section] = {"error": "No prompt function defined"}
                    continue
                
                print("\n\n--debug prompt_func----", section)
                prompt = prompt_func(company_info,imgs) if section == "case_studies" else prompt_func(company_info)
                
                # print("\n\n--debug prompt_func----", prompt.formatAsString())
                    
                future = executor.submit(llm.run, prompt, model_opts, 'quantum_agent', logInfo,socketio=socketio,client_id=client_id)
                futures[future] = section
                # socketio.emit('quantum_agent',{"event":'timeline','data': {"text":timeline,'is_completed':True}},room=client_id)
                sender.sendSteps(key=timeline,val=True)
            
            print("\n\n--debug [Futures]-------", len(futures))
            for future in as_completed(futures):
                section = futures[future]
                print("--debug collecting results-----", section)
                try:
                    
                    result = future.result()
                    section_data = extract_json_after_llm(result,step_sender=sender)
                    
                    canvas_data[section] = section_data
                    # socketio.emit('quantum_agent',{"event":'timeline','data': {"text":timeline,'is_completed':True}},room=client_id)
                except Exception as e:
                    print(f"Error generating section {section}: {e}")
                    appLogger.error({"event": canvas_data[section], "status": "prompt_failed", "tenant_id": tenantID,"traceback": traceback.format_exc()})
                    canvas_data[section] = {"error": str(e)}
                    
        ##Post processing of Offers and Partnerships (capabilities & partner list from above core sections)
        capabilities = canvas_data.get("core_capabilities", {}).get("capabilities", [])
        current_capabilities = capabilities.get("current_capabilities", [])
        # print("\n\n--debug [current_capabilities]------", current_capabilities)
        offer_capability_list = [item["text"] for item in current_capabilities if item["text"] is not None or item["text"] != ""]
        
        service_catalog = canvas_data.get("service_catalog", {}).get("services", [])
        partner_list = set()
        for item in service_catalog:
            if item.get("partner_list"):  
                partners = item["partner_list"].split(",")  
                partner_list.update(partner.strip() for partner in partners) 
        
        # print("\n\n--debug [Offer & Partnership list-------]------", offer_capability_list,'\n', partner_list)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                 
            #Offers
            future_offers = executor.submit(
                create_quantum_offers_partnerships,input_type=section_offers,input_list=offer_capability_list,
                company_info=company_info,llm=llm,model_opts=model_opts,logInfo=logInfo,socketio=socketio,client_id=client_id,sender=sender
            )
            
            #Partnerships
            future_partnerships = executor.submit(
                create_quantum_offers_partnerships,input_type=section_partnership,input_list=partner_list,
                company_info=company_info,llm=llm,model_opts=model_opts,logInfo=logInfo,socketio=socketio,client_id=client_id,sender=sender
            )

            offers_result = future_offers.result()
            partnerships_result = future_partnerships.result()

        canvas_data["offers"] = offers_result
        canvas_data["partnerships"] = partnerships_result
        
        # identifier = f"quantum_canvas_{tenantID}.json"
        # with open(identifier, 'w') as file:
        #     json.dump(canvas_data, file, indent=4)
        
        elapsed_time = time.time() - start_time
        print("\n\n\n\n\n--debug Quantum Canvas done, time: ", elapsed_time)
        
        formatted_data = format_quantum_canvas(canvas_data=canvas_data,tenant_id=tenantID,user_id=userID)
        with open(f'canvas_formatted_{tenantID}.json', 'w') as file:
            json.dump(formatted_data, file, indent=4)
            
        db_response = save_quantum_canvas(canvas_data = formatted_data)
        status_code = db_response.get("status_code",None)
        print("\n\n\n [DB] response----", db_response,'\n',status_code)
        
        if status_code != 200:
            sender.sendError(key=db_response,function="quantum_canvas_error")
        else:    
            socketio.emit('quantum_agent', {"event": 'quantum_canvas', 'data': formatted_data,'status': db_response}, room=client_id)
        
        socketio.emit('quantum_agent',{"event":'timeline','data': {"text":"Creating Quantum Canvas",'is_completed':True}},room=client_id)  
        return 
    
    except Exception as e:
        print("--debug error generating Quantum canvas",str(e))
        appLogger.error({"event":"create_quantum_canvas", "error": e,"traceback": traceback.format_exc()})


def create_quantum_offers_partnerships(
    input_type,
    input_list,
    company_info,
    llm,
    model_opts,
    logInfo,
    socketio,
    client_id,
    sender
):
    try:
        print("--debug create_quantum_offers_partnerships for ", input_type)
        section = input_type["section"]
        timeline = input_type["timeline"]
        
        sender.sendSteps(key=timeline,val=False)
        # socketio.emit('quantum_agent',{"event":'timeline','data': {"text":timeline,'is_completed':False}},room=client_id)
        
        prompt_func = call_section_prompt(section)
        prompt = prompt_func(company_info,input_list)
        # print("\n\n--debug [Offer_prompt_func----", prompt.formatAsString())
        
        response = llm.run(prompt, model_opts, f'quantum_agent::{section}', logInfo,socketio=socketio,client_id=client_id)
        # print("--debug create_quantum_partnerships", response)
        result = extract_json_after_llm(response,step_sender=sender)
        
        sender.sendSteps(key=timeline,val=True)
        # socketio.emit('quantum_agent',{"event":'timeline','data': {"text":timeline,'is_completed':True}},room=client_id)
        return result
    except Exception as e:
        print("--debug error generating Quantum canvas",e)
        sender.sendError(key=f"Error generating {section}",function="create_quantum_offers_partnerships")
        appLogger.error({"event":"create_quantum_partnerships","error":e,"traceback": traceback.format_exc()})




def validate_inputs(context_value,tenantID,userID,socketio,client_id):
       
    is_website = False
    is_social_media = False
    is_uploaded_docs = False
    
    # print("\n\n\n\n---debug valideate inputs--------", context_value)
    
    if context_value["website"] is None:
        is_website = True
        appLogger.error({"event":"quantum_service","status":"no_website","tenant_id":tenantID,"traceback":traceback.format_exc()})
        socketio.emit('quantum_agent',{"event":'error',"context": "website",'data': context_value["website"]},room=client_id)
            
    if context_value["uploaded_docs"] is None:
        is_uploaded_docs = True
        appLogger.error({"event":"quantum_service","status":"no_docs","tenant_id":tenantID,"traceback":traceback.format_exc()})
        socketio.emit('quantum_agent',{"event":'error',"context": "uploaded_docs",'data': context_value["uploaded_docs"]},room=client_id)
        
    if context_value["social_media"] is None or context_value == "$$$$$$NOTHING____FOUND#######":
        is_social_media = True
        appLogger.error({"event":"quantum_service","status":"no_social_media","tenant_id":tenantID,"traceback":traceback.format_exc()})
        socketio.emit('quantum_agent',{"event":'error',"context": "social_media",'data': context_value["social_media"]},room=client_id)
    
    # with open("context_value.json", 'w') as file:
    #     json.dump(context_value, file, indent=4)
    
    response ={
        "is_website": is_website,
        "is_uploaded_docs": is_uploaded_docs,
        "is_social_media": is_social_media
    }
    
    appLogger.info({"event":"validate_inputs","data":response,"tenant_id":tenantID})
    return is_website, is_uploaded_docs, is_social_media
    
        
        
        
def parse_latest_conv(conv_,context,tenantID):
    
    message = None
    quantum_inputs = None
    
    if conv_ and len(conv_) > 0:
        latest_conv_json = conv_[0]['value']
        try:
            latest_conv = json.loads(latest_conv_json)
            parts = latest_conv.split("Data:", 1)
            if len(parts) == 2:
                message_part = parts[0].strip()
                data_part = parts[1].strip()
                
                # Extract message
                if "message: " in message_part:
                    message_str = message_part.split("message: ", 1)[1].strip()
                    # message = message_str if len(message_str)>0 else None
                    if message_str == "None":
                        message = None
                    else:
                        message = message_str
                else:
                    message = None
                
                # Extract data
                # quantum_inputs = json.loads(data_part) if data_part else None
                if data_part == "null":
                    quantum_inputs = None
                else:
                    quantum_inputs = json.loads(data_part)
                
                # print("--debug [Message]---", message)
                if quantum_inputs:
                    # print("--debug quantum_inputs-------", quantum_inputs)
                    
                    context["company_website"] = quantum_inputs.get("company_website", "")
                    context["social_media_links"] = quantum_inputs.get("social_media_links", [])
                    context["uploaded_docs"] = quantum_inputs.get("uploaded_docs", [])
                    # print("--debug [Quantum Inputs]---", context)
                    
                appLogger.info({"event":"parse_latest_conv","data":quantum_inputs,"tenant_id":tenantID})
            else:
                print("Error: Invalid format in conversation value")
                appLogger.error({"event":"quantum_service","status":"invalid_format","tenant_id":tenantID,"traceback":traceback.format_exc()})
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in conversation data - {e}")
            
        except Exception as e:
            print(f"Error: Failed to process conversation data - {e}")
            appLogger.error({"event":"quantum_service","status":"processing_failed","tenant_id":tenantID,"traceback":traceback.format_exc()})
    else:
        print("Error: No conversation history found")
        appLogger.error({"event":"quantum_service","status":"no_history","tenant_id":tenantID,"traceback":traceback.format_exc()})
    
    return message,quantum_inputs










####temp
#For Testing
        ## website = context_value.get("website", None)
        ## match = re.search(r'://(?:www\.)?([^/.]+)', website)
        # website = "https://www.beautifulcode.co/"
        # company_search = CompanyInfoScraper(landing_page_url=website)
        # result = company_search.scrape()
        # with open("company.json", 'w') as file:
        #     json.dump(result, file, indent=4)
        # print("--debug [Company] done----------")
        # summarized = scraper_service("summarize",logInfo=logInfo).summarizer(
        #     large_data=result,
        #     message="Extract all the important info from the document",
        #     identifier="files_uploaded"
        # )
        # company_info = {"website": summarized}
        # print("\n\n --debug [create_quantum_canvas]-------")