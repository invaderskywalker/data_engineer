from src.controller.integration import IntegrationController
import json
from src.trmeric_services.tango.types.TangoYield import TangoYield
from src.trmeric_database.dao import TangoDao


def integration_sync(integrations, tenantID, userID, sessionID, file_type):
    sources = []
    for integration in integrations:
        if integration.name == "jira":
            accessible_resources = integration.api.getOrganizationDomain()
            print(accessible_resources)
            projects = IntegrationController().fetchIntegrationSourceProjects(0, 'Projects', accessible_resources, tenantID=tenantID, userID=userID)
            if projects:
                for project in projects:
                    sources.append(f"Jira Project: {project['name']}")    
                
            # epics = IntegrationController().fetchIntegrationSourceProjects(0, 'Epics', accessible_resources, tenantID=tenantID, userID=userID)
            # if epics:
            #     for epic in epics:
            #         sources.append(f"Jira Epic: {epic['name']}")   
    
            initiatives = IntegrationController().fetchIntegrationSourceProjects(0, 'Initiatives', accessible_resources, tenantID=tenantID, userID=userID)
            if initiatives:
                for initiative in initiatives:
                    sources.append(f"Jira Initiative: {initiative['name']}")
                    
        # if integration.name == "drive":
        #     api = integration.api
        #     sheets = api.list_google_sheets()
        #     if sheets: sheets = sheets.getColumn("Sheet Name")
        #     docs = api.list_google_docs()
        #     if docs: docs = docs.getColumn("Document Name")
        #     pdfs = api.list_google_pdfs()
        #     if pdfs: pdfs = pdfs.getColumn("PDF Name")
        #     ppts = api.list_google_ppts()
        #     if ppts: ppts = ppts.getColumn("Presentation Name")
            
        #     if sheets:
        #         for sheet in sheets:
        #             sources.append(f"Drive Sheet: {sheet}")
        #     if docs:
        #         for doc in docs:
        #             sources.append(f"Drive Document: {doc}")
        #     if pdfs:
        #         for pdf in pdfs:
        #             sources.append(f"Drive PDF: {pdf}")
        #     if ppts:
        #         for ppt in ppts:
        #             sources.append(f"Drive PPT: {ppt}")
        
        if integration.name == 'office':
            api = integration.api
            sheets = api.list_excel_sheets()
            if sheets: sheets = sheets.getColumn("Workbook Name")
            docs = api.list_word_documents()
            if docs: docs = docs.getColumn("Document Name")
            pdfs = api.list_pdfs()
            if pdfs: pdfs = pdfs.getColumn("PDF Name")
            ppts = api.list_powerpoint_presentations()
            if ppts: ppts = ppts.getColumn("Presentation Name")
            
            if sheets:
                for sheet in sheets:
                    sources.append(f"Office Sheet: {sheet}")
            if docs:
                for doc in docs:
                    sources.append(f"Office Document: {doc}")
            if pdfs:
                for pdf in pdfs:
                    sources.append(f"Office PDF: {pdf}")
            if ppts:
                for ppt in ppts:
                    sources.append(f"Office PPT: {ppt}")     
                    
        if integration.name == 'uploaded_files':
            import time
            time.sleep(10)
            files = integration.fetchCurrentSessionUploadedFiles(file_type)
            for file_id, file_name in files.items():
                sources.append(f"Uploaded Document: {file_name}")
            print(files)    
    ret_val = f"Here are some of the possible sources we recognized from your integrations. We will use your uploaded documents. If you would like to use any of these other sources from integrations, please provide the names in the chat."   
    yield_after = f"""
```json
{{
"onboarding_sync": {json.dumps(sources, indent=4)}     
}}
```
    """        
    if len(sources) > 0:
        if file_type == 'TANGO_ONBOARDING_PROJECT':
            TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_PROJECT_SYNC', str(sources), sessionID)
        elif file_type == 'TANGO_ONBOARDING_ROADMAP':
            TangoDao.insertTangoState(tenantID, userID, 'ONBOARDING_ROADMAP_SYNC', str(sources), sessionID)
        return TangoYield(return_info=ret_val, yield_info=yield_after)
    else:
        return None