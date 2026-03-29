import re
import json
import traceback
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List
from src.trmeric_database.Database import db_instance
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_ml.llm.Types import ModelOptions, ChatCompletion
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_services.agents.core.agent_functions import AgentFunction
from src.trmeric_services.agents.functions.potential_agent.utils import SKILL_MAP  # If needed




def clean_text(text):
    """Clean text by replacing problematic characters."""
    if isinstance(text, str):
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # Replace non-ASCII characters
        text = text.replace('¬†', ' ').replace('‚Äã', '')  # Replace specific artifacts
        text = text.replace("'", "''")  # Escape single quotes for SQL
        return text.strip()
    return str(text) if text is not None else ''

def resourceSkillMappingPrompt(batch) -> ChatCompletion:
    prompt = f"""
        You are an expert Resource planner, given an array of resources data where each entry is a json having resource's unique id,role and skills.
        Understanding their role & skills, you need to create a categorization for each one of them as their primary_skill and secondary_skill
        looking at the {SKILL_MAP}
        
        ##Input
        Batch resource data: {json.dumps(batch)}
        
        ##Output: Return in JSON format:
        ```json
        {{
            "resource_data": [
                {{  
                    "id": "<integer, same as input>",
                    "role":"<same as input>",
                    "primary_skill_group": "",
                    "secondary_skill_group": ""
                }}...
            ]
        }}
        ```
    """
    return ChatCompletion(system=prompt,prev=[],user='')

def process_batch(batch, tenant_id, user_id, **kwargs):
    """Processes a single batch of project status entries."""
    print(f"--processing batch-- {batch} for tenant {tenant_id} & user {user_id}\n")
    try:
        llm = kwargs.get("llm")
        model_opts = kwargs.get("model_opts")
        logInfo = kwargs.get("logInfo")
        socketio = kwargs.get("socketio")
        client_id = kwargs.get("client_id")
        sender = kwargs.get("steps_sender")
        
        # llm = ChatGPTClient()
        # model_opts = ModelOptions(model="gpt-4.1", max_tokens=2000, temperature=0.1)
        
        prompt = resourceSkillMappingPrompt(batch)
        result = llm.run(prompt, model_opts, "potential::upload_data", logInDb=logInfo,socketio=socketio, client_id=client_id)
        
        data = extract_json_after_llm(result,step_sender=sender)
        return data.get("resource_data", [])
    
    except Exception as e:
        sender.sendError(key= f"Error processing resources: {str(e)}", function="potential::process_batch")
        appLogger.error({"event":"potential::process_batch","error":str(e),"traceback":traceback.format_exc()})
    

def process_items_from_sheet(file_path: str = '', tenant_id: int = None, user_id: int = None, sender=None, **kwargs) -> List[Dict[str, Any]]:
    """
        Process resources from a spreadsheet file (e.g., CSV) row by row, assign primary/secondary skills via LLM, and insert into DB.
        List of results for each processed row, including success or error details.
    """
    results = []
    print("Processing resource data -- job ", file_path)
    
    # Step 1: Load the CSV file
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
    except FileNotFoundError:
        error_msg = f"Input file {file_path} not found"
        print(error_msg)
        return [{"error": error_msg}]
    except Exception as e:
        error_msg = f"Error reading {file_path}: {str(e)}"
        print(error_msg)
        return [{"error": error_msg}]

    msg = f"Processing {len(df)} rows from sheet"
    print("--debug process_items_from_sheet length------", msg)

    # Step 2: Collect row data
    rows = []
    sender.sendSteps(key=msg,val=False)
    for index, row in df.iterrows():
        row_data = {
            'temp_id': index,
            'first_name': clean_text(row.get('first_name', '')),
            'last_name': clean_text(row.get('last_name', '')),
            'country': clean_text(row.get('country', '')),
            'email': clean_text(row.get('email', '')),
            'role': clean_text(row.get('role', '')),
            'skills': clean_text(row.get('skills', '')),
            'allocation': row.get('allocation', ''),
            'experience_years': row.get('experience_years', ''),
            'experience': clean_text(row.get('experience', '')),
            'projects': clean_text(row.get('projects', '')),
            'is_active': row.get('is_active', 'True'),
            'is_external': row.get('is_external', 'False'),
            'availability_time': row.get('availability_time', ''),
            # Add if present: 'location': clean_text(row.get('location', '')), 'rate': row.get('rate', '')
        }
        rows.append(row_data)
        results.append({"row": index + 1, "status": "processed", "data": row_data})
    
    sender.sendSteps(key=msg,val=True)
    # Step 3: Batch process for LLM to assign primary/secondary skills
    
    sender.sendSteps(key = "Categorizing Primary & secondary skills",val=False)
    if rows:
        batch_size = 20
        futures = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                llm_batch = [{"id": r['temp_id'], "role": r['role'], "skills": r['skills']} for r in batch]
                futures.append(executor.submit(process_batch, llm_batch, tenant_id, user_id, **kwargs))

        all_mappings = []
        for future in as_completed(futures):
            try:
                mappings = future.result()
                all_mappings.extend(mappings)
            except Exception as e:
                print(f"Error in batch processing: {e}")
                results.append({"error": str(e)})

        # Apply mappings to rows
        for mapping in all_mappings:
            for row in rows:
                if row['temp_id'] == mapping['id']:
                    row['primary_skill'] = mapping['primary_skill_group']
                    row['secondary_skill'] = mapping['secondary_skill_group']

    sender.sendSteps(key = "Categorizing Primary & secondary skills",val=True)
    # Step 4: Insert into DB using parameterized queries

    sender.sendSteps(key = "✅ Updating Potential UI data", val=False)
    insert_query = """
        INSERT INTO public.capacity_resource (
            first_name, last_name, country, email, role, skills, allocation, experience_years, experience, projects,
            is_active, is_external, created_on, updated_on, created_by_id, updated_by_id, tenant_id,
            trmeric_provider_tenant_id, external_provider_id, availability_time, location, rate, primary_skill, secondary_skill
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    for row in rows:
        try:
            is_active = True if str(row['is_active']).lower() == 'true' else False
            is_external = True if str(row['is_external']).lower() == 'true' else False
            allocation = int(row['allocation']) if row['allocation'] else 0
            experience_years = int(row['experience_years']) if row['experience_years'] else 0
            availability_time = int(row['availability_time']) if row['availability_time'] else None
            location = row.get('location', None)
            rate = float(row.get('rate')) if row.get('rate') else None
            params = (
                row['first_name'], row['last_name'], row['country'], row['email'], row['role'], row['skills'],
                allocation, experience_years, row['experience'], row['projects'],
                is_active, is_external, datetime.now(), None, user_id, None, tenant_id,
                None, None, availability_time, location, rate, row.get('primary_skill', ''), row.get('secondary_skill', '')
            )
            db_instance.executeSQLQuery(insert_query, params)
            debugLogger.info(f"Inserted resource: {row['first_name']} {row['last_name']}")
            results.append({"row": row['temp_id'] + 1, "status": "inserted"})
        except Exception as e:
            error_msg = f"Error inserting row {row['temp_id'] + 1}: {str(e)}"
            appLogger.error({"event": "Insert failed", "error": error_msg})
            results.append({"error": error_msg})
    
    sender.sendSteps(key = "✅ Updating Potential UI data", val=True)
    return results




def run():
    results = process_items_from_sheet(file_path="Solutions.csv", tenant_id=776, user_id=86)
    for result in results:
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Processed/Inserted row {result.get('row')}: {result.get('status')}")
            




# SKILL_MAP = {
#   "ERP": ["SAP (FI/CO, MM, SD, PP, HCM)","Oracle ERP (E-Business Suite, Fusion, NetSuite)","Microsoft Dynamics 365 Finance & Operations","ERP Implementation & Customization","ERP Reporting & Data Migration"],
#   "Data & Analytics": ["Data Engineering (ETL, Data Pipelines, Warehousing)","Business Intelligence (Power BI, Tableau, Qlik)","Advanced Analytics & Forecasting","Big Data Platforms (Databricks, Hadoop, Spark)","Data Governance & Master Data Management"],
#   "AI": ["Machine Learning (ML) Engineering","Natural Language Processing (NLP)","Computer Vision","Generative AI (LLMs, Prompt Engineering, Fine-tuning)","MLOps & Model Deployment"],
#   "CRM": ["Salesforce (Sales, Service, Marketing Clouds)","Microsoft Dynamics 365 CRM","SAP Customer Experience (C4C, Hybris)","CRM Integration & Customization","CRM Analytics & Customer Journey Mapping"],
#   "Cloud & DevOps": ["Cloud Platforms (AWS, Azure, GCP)","CI/CD & Release Management","Infrastructure as Code (Terraform, Ansible, ARM)","Containerization & Orchestration (Docker, Kubernetes)","Monitoring & Observability (Prometheus, Grafana, ELK)"],
#   "Infrastructure Management": ["Network Administration (LAN, WAN, VPN, Firewalls)","Server & Storage Management","Virtualization (VMware, Hyper-V)","End-User Computing & Device Management","IT Service Management (ITIL, ServiceNow)"],
#   "Automation": ["RPA (UiPath, Automation Anywhere, Blue Prism)","IT Process Automation (Ansible, Puppet, Chef)","Test Automation (Selenium, Cypress, Playwright)","Workflow Automation (Power Automate, Zapier)","Infrastructure Automation (Terraform, CloudFormation)"],
#   "Integration": ["API Management (MuleSoft, Apigee, Kong)","ESB (Dell Boomi, TIBCO, IBM Integration Bus)","Event Streaming & Messaging (Kafka, RabbitMQ)","Cloud Integration (iPaaS, Azure Logic Apps)","B2B/EDI Integration"],
#   "Security": ["Identity & Access Management (Okta, Azure AD, Ping)","Application Security (AppSec, DevSecOps)","Network & Infrastructure Security","Cloud Security & Compliance","Threat Detection & Incident Response (SIEM, SOC)"],
#   "Business Apps": ["CPQ Platforms (Salesforce CPQ, Apttus, Oracle CPQ)","HR & HCM Apps (Workday, SuccessFactors)","Finance & Accounting Apps (BlackLine, Coupa)","Collaboration Apps (O365, Google Workspace)","Supply Chain & Procurement Apps"],
#   "Project Management": ["Agile (Scrum, Kanban, SAFe)","Waterfall & Hybrid Methodologies","PM Tools (Jira, MS Project, Smartsheet)","Portfolio & Program Management (PPM)","Risk & Change Management"],
#   "Quality Assurance": ["Manual Testing (Functional, Regression, UAT)","Test Automation Frameworks","Performance & Load Testing (JMeter, LoadRunner)","Security Testing","QA Tools & Management (TestRail, Zephyr)"],
#   "Business Analyst": ["Requirements Gathering & Documentation","Process Modeling & Mapping (BPMN, Visio)","Functional Specification & User Stories","Data Analysis & Reporting","Domain-Specific BA (ERP, CRM, Finance, Supply Chain)"],
#   "App Development": ["Frontend Development (React, Angular, Vue)","Backend Development (Java, .NET, Python, Node.js)","Mobile Development (iOS, Android, Flutter, React Native)","Full Stack Development","API & Microservices Development"],
#   "UX": ["UX Research & User Testing","Wireframing & Prototyping (Figma, Sketch, XD)","Interaction Design","UI Development & Design Systems","Accessibility & Usability Standards"]
# }