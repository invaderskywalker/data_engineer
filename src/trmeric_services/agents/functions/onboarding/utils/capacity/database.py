import traceback, json, random
from datetime import datetime
import pytz
from src.trmeric_s3.s3 import S3Service
from src.trmeric_database.dao import TenantDao, ProjectsDao, TangoDao
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.models.project import CapacityResource, CapacityResourceProviders, CapacityResourceTimeline

# Define timezone and helper for current timestamp
timezone = pytz.timezone('Asia/Kolkata')
def get_current_time():
    return datetime.now(timezone)

# Helper to convert allocation value
def convert_allocation(allocation_value):
    try:
        if isinstance(allocation_value,int):
            return allocation_value
        else:
            return int(float(str(allocation_value)) * 100)
    except ValueError:
        return 0

# Provider functions
def get_existing_provider(provider_name):
    """Check if a provider already exists and return its tenant id."""
    try:
        existing = TenantDao.getTenantID(provider_name)
        return existing[0]["tenant_id"] if existing else None
    except Exception as e:
        appLogger.error({"event": "get_existing_provider", "error": str(e), "traceback": traceback.format_exc()})
        return None

def create_provider_entry(entry, user_id, tenant_id):
    """Create a new provider entry in the external providers table."""
    print("--debug in create_provider_entry--------------",entry)
    try:
        
        
        provider_name = entry.get("provider_name", None)
        existing_provider = TenantDao.getCapacityProviderID(provider_name,tenant_id)
        # id = existing_provider[0]["id"]
        print("--debug existing_provider", existing_provider , type(existing_provider),provider_name)
        
        if not existing_provider:
            new_provider = CapacityResourceProviders.create(
                company_name=entry.get("provider_name",None),
                address=entry.get("address",None),
                company_website=entry.get("website",None),
                created_on=get_current_time(),
                updated_on=get_current_time(),
                created_by_id=user_id,
                tenant_id=tenant_id,
                updated_by_id=user_id
            )
            # print(f"--debug: Provider created with id {new_provider.id}")
            return new_provider.id
        else:
            print(f"--debug: Provider already exists with id {existing_provider[0]['id']}")
            return existing_provider[0]["id"]
    except Exception as e:
        appLogger.error({"event": "create_provider_entry", "error": str(e), "traceback": traceback.format_exc()})
        return None

# Resource entry function
def create_resource_entry(entry, user_id, tenant_id,is_trmeric_provider, provider_id=None, is_external=False):
    """Create or update a resource entry in CapacityResource."""
    
    # print("--debug in create_resource_entry--------------------",entry)
    try:
        name_parts = entry.get("name", "").split()
        first_name = name_parts[0] if name_parts else None
        last_name = name_parts[1] if len(name_parts) > 1 else None
        
        allocation = convert_allocation(entry.get("allocation", 0))
        current_time = get_current_time()
        
        # Check if resource already exists (using TenantDao helper for example)
        existing_resource = TenantDao.getCapacityResource(first_name, last_name,tenant_id)
        print("--debug existing_resource", existing_resource ,type(existing_resource), " ","trmeric-provider",is_trmeric_provider)
        
        if not existing_resource:
            new_resource = CapacityResource.create(
                first_name=first_name,
                last_name=last_name,
                country=entry.get("country", ""),
                email=entry.get("email", ""),
                role=entry.get("role", ""),
                skills=entry.get("skills"),
                allocation=allocation,
                experience_years=int(entry.get("experience", 0)),
                projects=entry.get("projects",''),
                is_active=True,
                is_external=is_external,
                created_on=current_time,
                updated_on=current_time,
                created_by_id=user_id,
                tenant_id=tenant_id,
                trmeric_provider_tenant_id=provider_id if is_trmeric_provider else None,
                external_provider_id=provider_id if is_external else None,
                updated_by_id=user_id
            )
            # print(f"--debug: Resource {first_name} created with id {new_resource.id}")
            return new_resource.id
        else:
            print(f"--debug: Resource {first_name} already exists with id {existing_resource[0]['id']}")
            if is_trmeric_provider and existing_resource.trmeric_provider_tenant_id != provider_id:
                existing_resource.trmeric_provider_tenant_id = provider_id
            elif(existing_resource.external_provider_id != provider_id):
                existing_resource.external_provider_id = provider_id
                
            existing_resource.save()
            return existing_resource[0]["id"]
    except Exception as e:
        appLogger.error({"event": "create_resource_entry", "error": str(e), "traceback": traceback.format_exc()})
        return None

# Timeline entry function
def create_resource_timeline_entry(resource_id, project, user_id, tenant_id, allocation):
    """Create a timeline entry for a resource's project assignment."""
    
    print("--debug in create_resource_timeline_entry--------------")
    try:
        project_name = project.get("project_name")
        # Check if project exists in trmeric system
        project_info = ProjectsDao.fetchProjectForCapacity(project_name)
        if project_info:
            trmeric_project_id = project_info[0]["id"]
            start_date = project_info[0]["start_date"]
            end_date = project_info[0]["end_date"]
        else:
            trmeric_project_id = None
            start_date = project.get("start_date")
            end_date = project.get("end_date")
        
        existing_timeline = TenantDao.getCapacityResourceTimeline(resource_id, project_name,tenant_id)
        # print("--debug existing_timeline", existing_timeline ,type(existing_timeline))
        
        if not existing_timeline:
            CapacityResourceTimeline.create(
                start_date=start_date,
                end_date=end_date,
                allocation=allocation,  
                project_name=project_name,
                created_on=get_current_time(),
                updated_on=get_current_time(),
                created_by_id=user_id,
                resource_id=resource_id,
                tenant_id=tenant_id,
                trmeric_project_id=trmeric_project_id,
                updated_by_id=user_id
            )
        else:
            # Update existing timeline entry
            if start_date and end_date:
                if (existing_timeline.start_date != start_date) or (existing_timeline.end_date != end_date):
                    existing_timeline.start_date = start_date
                    existing_timeline.end_date = end_date
                    existing_timeline.save()
        # print(f"--debug: Timeline entry created for resource {resource_id} on project {project_name}")
    except Exception as e:
        appLogger.error({"event": "create_resource_timeline_entry", "error": str(e), "traceback": traceback.format_exc()})


def process_entry(entry, user_id, tenant_id):
    """Process a single entry, deciding whether it is for a resource or provider."""
    
    print("--debug in process_entry--------------------",entry)
    provider_name = entry.get("provider_name")
    print("--debug provider found--------------",provider_name)
    
    resource_id = None
    is_external = False
    provider_id = None
    is_trmeric_provider = False
    
    if provider_name and len(provider_name.strip()) > 0:
        # This entry is for a provider resource.
        existing_provider_id = get_existing_provider(provider_name)
        if existing_provider_id:
            provider_id = existing_provider_id
            is_external = True
            is_trmeric_provider = True
        else:
            provider_id = create_provider_entry(entry, user_id, tenant_id)
            is_external = True

    # Create resource entry
    resource_id = create_resource_entry(entry, user_id, tenant_id,is_trmeric_provider, provider_id=provider_id, is_external=is_external,)
    
    # Process timeline/project entries if available
    projects = entry.get("projects", [])
    if resource_id and projects:
        # If projects is a string (comma-separated) convert to list of dicts, else assume list of dicts
        if isinstance(projects, str):
            
            project_list = [{"project_name": proj.strip()} for proj in projects.split(",")]
        else:
            project_list = projects
        for proj in project_list:
            create_resource_timeline_entry(resource_id, proj, user_id, tenant_id, allocation=convert_allocation(entry.get("allocation", 0)))

    return resource_id

# Main function to save to DB from structured data
def save_to_db(key, structured_data, user_id, tenant_id):
    """
    Saves structured capacity data into the database 
#         check entry: 
#         1. it will be internal or provider: create entry in capacity resource and capacity external providers if current entry has provider name also
#         2. if resource is provider then check if that provider company is already registered in trmeric, if yes add that resource in tenant_provider table
#         3. if new provider then add it to Capacity external provider table
#         4. the current resource can have project timeline data the list of projects with their start, end dates & allocation assigned
    """
    msg = ""
    print("--debug save_to_db structured_data", structured_data)
    
    if isinstance(structured_data, str):
        try:
            structured_data = json.loads(structured_data)
        except json.JSONDecodeError:
            appLogger.error({"event": "capacity_save_db", "error": "Invalid JSON format for structured_data."})
            return "Error: Invalid JSON format for structured_data."
    
    # Process each entry
    for entry in structured_data:
        if not isinstance(entry, dict):
            appLogger.error({"event": "capacity_save_db", "error": f"Invalid entry format: {entry}"})
            continue
        try:
            print("--debug in save_to_db----------------------------",entry)
            process_entry(entry, user_id, tenant_id)
        except Exception as e:
            appLogger.error({"event": "capacity_save_db", "error": str(e), "traceback": traceback.format_exc()})
            continue

    msg += "Data successfully inserted into capacity_resource."
    return msg













# def createResourceEntry(entry,user_id,tenant_id):

#     print("--debug in createResourceEntry",entry)
#     pass

# def createResourceTimelineEntry(entry,user_id,tenant_id):
#     print("--debug in createResourceTimelineEntry",entry)
#     pass

# def createResourceProviderEntry(entry,user_id,tenant_id):
#     print(f"--debug in createResourceProviderEntry {entry}")
#     pass


# def entry_type(table_name,entry,user_id,tenant_id):
#     if table_name == "capacity_resource":
#         return createResourceEntry(entry,user_id,tenant_id)
#     elif table_name == "capacity_resource_timeline":
#         return createResourceTimelineEntry(entry,user_id,tenant_id)
#     elif table_name == "capacity_resource_providers":
#         return createResourceProviderEntry(entry,user_id,tenant_id)

# def save_to_db(key,structured_data, user_id, tenant_id):
    
#     """
#         Saves structured capacity data into the database 
#         check entry: 
#         1. it will be internal or provider: create entry in capacity resource and capacity external providers if current entry has provider name also
#         2. if resource is provider then check if that provider company is already registered in trmeric, if yes add that resource in tenant_provider table
#         3. if new provider then add it to Capacity external provider table
#         4. the current resource can have project timeline data the list of projects with their start, end dates & allocation assigned
#     """
    
#     #internal employee json
#         # 'value': '[{"name": "Mike Johnson", "experience": 3, "skills": "Java, Spring Boot", "role": "Backend Engineer",
#         # "rate": 45, "allocation": 0.9}
#     # provider json:
#         #     {"provider_name": "Provider E", "name": "Charlie Davis", "email": "charlie.davis@example.com",
#         #      "experience": 4, "allocation": 70, "skills": "Java, Spring Boot"}]'
        
#     msg = ""
#     print("--debug save_to_db structrued_data", structured_data)
    
#     if isinstance(structured_data, str):
#         try:
#             structured_data = json.loads(structured_data)  # Convert JSON string to Python list
#         except json.JSONDecodeError:
#             appLogger.error({"event": "capacity_save_db", "error": "Invalid JSON format for structured_data."})
#             return "Error: Invalid JSON format for structured_data."
    
#         print("--debug data", structured_data)
#         for entry in structured_data:
#             # print("--debug entry", entry)
#             if not isinstance(entry, dict):
#                 appLogger.error({"event": "capacity_save_db", "error": f"Invalid entry format: {entry}"})
#                 continue  
            
#             try:
#                 # Extract name details
#                 name_parts = entry.get("name", "").split()
#                 first_name = name_parts[0] if name_parts else None
#                 last_name = name_parts[1] if len(name_parts) > 1 else None
#                 provider_name = entry.get("provider_name", None)
#                 is_trmeric_provider = False
#                 provider_id = random.randint(1,10000)
                
                
#                 if len(provider_name)>0:
#                     #since entry is encrypted need to check if it's already in trmeric
#                     existing_provider = TenantDao.getTenantID(provider_name)
#                     existing_provider_id = existing_provider[0]["tenant_id"] if existing_provider else None
#                     if existing_provider_id:
#                         is_trmeric_provider = True
#                         provider_id = existing_provider_id
                        
#                     else:
#                         #create provider entry in capacity external resource table
#                         createResourceProviderEntry(entry,user_id,tenant_id)
#                 else:
#                     # print("--debug name", name_parts,first_name,last_name)
#                     existing_resource = CapacityResource.select().where(
#                         CapacityResource.first_name == first_name,
#                         CapacityResource.last_name == last_name,
#                         CapacityResource.role == entry.get["role"],
#                         CapacityResource.experience ==entry.get["experience"]
#                     ).first()
                    
#                     if not existing_resource:
#                         allocation_str = entry.get("allocation", "0")  
#                         try:
#                             allocation = int(float(allocation_str) * 100) 
#                         except ValueError:
#                             allocation = 0  
#                         current_time = datetime.now(timezone)
#                         print("--debug current_time:", current_time, type(current_time))
    
#                         # Create database entry
#                         CapacityResource.create(
#                             first_name=first_name,
#                             last_name=last_name,
#                             country = entry.get("country", ""),
#                             email=entry.get("email", ""),
#                             role=entry.get("role", ""),
#                             skills=entry.get("skills", None),
#                             allocation=allocation,
#                             experience_years=entry.get("experience", 0),
#                             projects = entry.get("projects",None),
#                             is_active=True,
#                             is_external= False if is_trmeric_provider else True,
#                             created_on=current_time,
#                             updated_on=current_time,
#                             created_by_id=user_id,
#                             tenant_id=tenant_id,
#                             trmeric_provider_tenant_id  = provider_id if is_trmeric_provider else None ,
#                             external_provider_id = provider_id if not is_trmeric_provider else None
#                         )
                    
#                     #if projects for curr resource are present in db fetch the resource_id from Capacityresource table and map
#                     existing_capacityResource = TenantDao.getCapacityResourceID(first_name,last_name)
#                     existing_capacityResource_id = existing_capacityResource[0]["id"] if existing_capacityResource else None
#                     print("--debug existing_capacityResource_id", existing_capacityResource_id)
                    
#                     if existing_capacityResource_id:
#                         # curr resource timeline
#                         for project in entry.get("projects",[]):
#                             project_name = project.get("project_name",None)
                            
#                             #check if project exist in trmeric
#                             trmeric_project_id = None
#                             is_trmeric_project = ProjectsDao.fetchProjectForCapacity(project_name)
#                             if is_trmeric_project:
#                                 trmeric_project_id = is_trmeric_project[0]["id"] 
#                                 start_date = is_trmeric_project[0]["start_date"] 
#                                 end_date = is_trmeric_project[0]["end_date"] 

#                             else:                            
#                                 start_date = project.get("start_date",None)
#                                 end_date = project.get("end_date",None)
#                             CapacityResourceTimeline.create(
#                                 # id = BigIntegerField()
#                                 start_date = start_date,
#                                 end_date = end_date,
#                                 allocation = allocation,
#                                 project_name =project_name,
#                                 created_on = datetime.now(),
#                                 updated_on = datetime.now(),
#                                 created_by_id = user_id,
#                                 resource_id = existing_capacityResource_id,
#                                 tenant_id = tenant_id,
#                                 trmeric_project_id = trmeric_project_id,
#                                 updated_by_id = user_id        
#                             )

#                     print(f"--debug entry added---------{first_name}")
#                     if not is_trmeric_provider:  
#                     #     {"provider_name": "Provider E", "name": "Charlie Davis", "email": "charlie.davis@example.com","experience": 4, "allocation": 70, "skills": "Java, Spring Boot"}]'
#                         CapacityResourceProviders.create(
#                                 company_name=provider_name,
#                                 address=entry.get("address",None),
#                                 company_website=entry.get("website", None),
#                                 created_on = datetime.now(),
#                                 updated_on = datetime.now(),
#                                 created_by_id=user_id,
#                                 tenant_id=tenant_id,
#                                 is_active=True
#                             )
#                         print(f"Inserted provider {is_trmeric_provider} into the db")
                        
#             except Exception as e:
#                 appLogger.error({"event": "capacity_save_db", "error": str(e), "traceback":traceback.format_exc()})
#                 continue

#     msg += "Data successfully inserted into capacity_resource."
#     return msg






# v1
    # def _validate_allocation(allocation_str):
    #     """Validate allocation percentage (0-100)"""
    #     try:
    #         allocation = int(float(allocation_str) * 100)
    #         if not 0 <= allocation <= 100:
    #             raise ValueError("Allocation out of 0-100% range")
    #         return allocation
    #     except (ValueError, TypeError):
    #         return 0  # Default to 0% on invalid data

    # def _get_or_create_provider(provider_name, user_id, tenant_id):
    #     """Check existing providers and return provider ID"""
    #     provider = CapacityResourceProviders.get_or_none(
    #         CapacityResourceProviders.company_name == provider_name,
    #         CapacityResourceProviders.tenant_id == tenant_id
    #     )
    #     if provider:
    #         return provider.id, True  # (existing_provider_id, is_trmeric_provider)
    #     else:
    #         # Create new provider
    #         new_provider = CapacityResourceProviders.create(
    #             company_name=provider_name,
    #             created_on=datetime.now(timezone),
    #             updated_on=datetime.now(timezone),
    #             created_by_id=user_id,
    #             tenant_id=tenant_id,
    #             is_active=True
    #         )
    #         return new_provider.id, False

    # def _create_resource(entry, user_id, tenant_id, is_external, provider_id=None):
    #     """Create CapacityResource entry with validation"""
    #     name_parts = entry.get("name", "").split()
    #     first_name = name_parts[0] if name_parts else ""
    #     last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        
    #     allocation = _validate_allocation(entry.get("allocation", 0))
        
    #     return CapacityResource.create(
    #         first_name=first_name,
    #         last_name=last_name,
    #         email=entry.get("email", ""),
    #         role=entry.get("role", ""),
    #         skills=entry.get("skills", ""),
    #         allocation=allocation,
    #         experience_years=entry.get("experience", 0),
    #         is_external=is_external,
    #         trmeric_provider_tenant_id=provider_id if is_external else None,
    #         created_on=datetime.now(timezone),
    #         updated_on=datetime.now(timezone),
    #         created_by_id=user_id,
    #         tenant_id=tenant_id
    #     )

    # def _create_timeline(resource_id, projects, user_id, tenant_id):
    #     """Create project timeline entries"""
    #     for project in projects:
    #         project_name = project.get("project_name")
    #         trmeric_project = ProjectsDao.fetchProjectForCapacity(project_name)
            
    #         CapacityResourceTimeline.create(
    #             start_date=project.get("start_date") or (trmeric_project.start_date if trmeric_project else None),
    #             end_date=project.get("end_date") or (trmeric_project.end_date if trmeric_project else None),
    #             allocation=_validate_allocation(project.get("allocation", 0)),
    #             project_name=project_name,
    #             resource_id=resource_id,
    #             trmeric_project_id=trmeric_project.id if trmeric_project else None,
    #             created_by_id=user_id,
    #             tenant_id=tenant_id,
    #             created_on=datetime.now(timezone),
    #             updated_on=datetime.now(timezone)
    #         )

    # # def save_to_db(key, structured_data, user_id, tenant_id):
    # """Main entry point with transaction support"""
    # if isinstance(structured_data, str):
    #     try:
    #         structured_data = json.loads(structured_data)
    #     except json.JSONDecodeError:
    #         return "Invalid JSON format"

    # try:
    #     with CapacityResource._meta.database.atomic():  # Transaction start
    #         for entry in structured_data:
    #             provider_name = entry.get("provider_name")
    #             is_external = bool(provider_name)
                
    #             # Handle Providers
    #             provider_id = None
    #             if is_external:
    #                 provider_id, is_trmeric_provider = _get_or_create_provider(
    #                     provider_name, user_id, tenant_id
    #                 )
                
    #             # Create Resource
    #             resource = _create_resource(
    #                 entry, user_id, tenant_id,
    #                 is_external=is_external,
    #                 provider_id=provider_id
    #             )
                
    #             # Create Timeline
    #             if entry.get("projects"):
    #                 _create_timeline(
    #                     resource.id, 
    #                     entry["projects"], 
    #                     user_id, 
    #                     tenant_id
    #                 )
                    
    #         return "Data saved successfully with transaction"
            
    # except DatabaseError as e:
    #     appLogger.error(f"Database transaction failed: {str(e)}")
    #     return "Error: Database transaction failed"
    # except Exception as e:
    #     appLogger.error(f"Unexpected error: {traceback.format_exc()}")
    #     return "Error: Check logs for details"