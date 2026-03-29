import os
import json
import datetime
import requests
import traceback
from src.trmeric_s3.s3 import S3Service
from src.trmeric_database.dao import FileDao
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.summarizer.SummarizerService import SummarizerService
from src.trmeric_services.provider.prompts.Quantum import call_process_doc_prompt
from src.trmeric_services.agents.core.agent_functions import AgentFunction,AgentFnTypes

def process_uploaded_doc(
    tenantID=None,
    userID=None,
    data =None,
    llm=None,
    model_opts=None,
    socketio=None,
    client_id=None,
    logInfo=None,
    **kwargs
):
    
    print("--debug Quantum process_uploaded_doc------",tenantID,userID,data)
    step_sender = kwargs.get("steps_sender") or None
    try:
        result = None
        s3_service = S3Service()
        summarizer_service = SummarizerService(logInfo=logInfo)
        
        doc_type = data.get("type","")
        file = data.get("file",{})
        s3_key = file.get("s3_key","")
        file_desc = file.get("desc","")
        
        # print("--debug Quantum process_uploaded_doc11------",doc_type,file,s3_key,file_desc)
        file_info = FileDao.FileUploadedDetailsS3Key(s3_key=s3_key)
        if file_info is None:
            appLogger.error({"event":"process_uploaded_doc","error":file_info,"traceback":traceback.format_exc()})
            step_sender.sendError(key = "Couldn't retrieve file details, please retry!", function="process_uploaded_doc")
            return
        
        file_name = file_info.get("filename","") or "Filename"
        file_url = s3_service.generate_presigned_url(s3_key)
        file_info["url"] = file_url
        print("--debug file info---------", file_name," Url: ",file_info)
        prompt = None
        
        file_content = s3_service.download_file_as_text(s3_key=s3_key)
        if file_content is None:
            error = f"Skipping file {s3_key} due to download error."
            appLogger.error({"event":"process_uploaded_doc","error":error,"traceback":traceback.format_exc()})
            step_sender.sendError(key=error,function="process_uploaded_doc")
            return
        
        document = summarizer_service.summarizer(
            large_data = file_content,
            message = f"This is a document uploaded by the user of type {doc_type}.It has description as {file_desc}.\nYou need to process it and fetch all the necessary details.",
            identifier = "files_uploaded"
        )
        
        if document:  
            prompt_func = call_process_doc_prompt(doc_type)
            print("\n\n\n--debug prompt_func----", prompt_func, "\nDoc type: ",doc_type)
            prompt = prompt_func(company_info=document)
            # print("\n\n--debug promp----", prompt.formatAsString())
            
            response = llm.run(prompt, model_opts,'quantum_agent::process_doc', logInDb = logInfo)
            # print("\\nn response------", response)
            result = extract_json_after_llm(response,step_sender=step_sender)
        
        if doc_type == "case_study":
            result = result.get("case_study") or []
        print("\n\n--debug process_uploaded_doc result----", result)
        socketio.emit("quantum_agent",{
            "event":"process_uploaded_doc",
            "tenant_id":tenantID,
            "doc_type":doc_type,
            "data":result,
            "file_info":file_info
            },
            room=client_id
        )
        return 
    
    except Exception as e:
        print(f"--debug error in process_uploaded_doc----",e)
        step_sender.sendError(key=f"Error in processing {doc_type}",function="process_uploaded_doc")
        appLogger.error({"event": "process_uploaded_doc","error": e,"traceback": traceback.format_exc()})
        return 
    
    
QUANTUM_PROCESS_DOCS = AgentFunction(
    name="process_uploaded_doc",
    description="""
        This function is responsible for capacity planner for the project.
        It will return all the roles, their duration and allocation percentage (monthwise) which will be required throughout the project.
    """,
    args=[],
    return_description="""This function will return the processed data of the uploaded document bcp or case study for quantum.""",
    function=process_uploaded_doc,
    type_of_func=AgentFnTypes.SKIP_FINAL_ANSWER.name
)