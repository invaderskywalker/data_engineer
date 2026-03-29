

from src.trmeric_database.Database import TrmericDatabase
import json

def fetchProviderInfoForOpportunity(database: TrmericDatabase, providerId: int):
    query = f"""
                WITH catalogue_data_json AS (
                    SELECT 
                        tpc.partnerships, 
                        tpc.industry_experience, 
                        tpc.partnerships_tier, 
                        tpc.service_category, 
                        tpc.service_description, 
                        tpc.service_name
                    FROM 
                        discovery_trmericproviderservicecatalog AS tpc 
                    WHERE 
                        service_provider_id IN (
                            SELECT id 
                            FROM tenant_serviceprovider 
                            WHERE provider_id_id = {providerId}
                        )
                ),
                provider_capability_data AS (
                    SELECT 
                        best_in_class_capabilities, 
                        mainstream_capabilities, 
                        function_domain_expertise, 
                        strength_area, 
                        key_technologies, 
                        industries_we_work 
                    FROM 
                        tenant_providercapabilities 
                    WHERE 
                        service_provider_id IN (
                            SELECT id 
                            FROM tenant_serviceprovider 
                            WHERE provider_id_id = {providerId}
                        )
                ),
                case_study_data as (
                    select * from tenant_providercasestudies WHERE 
                        service_provider_id IN (
                            SELECT id 
                            FROM tenant_serviceprovider 
                            WHERE provider_id_id = {providerId}
                        )
                )
                SELECT 

                    json_agg(row_to_json(c)) AS service_catalogue_data,
                    json_agg(row_to_json(p)) AS provider_capability_data,
                    json_agg(row_to_json(cd)) AS case_study_data
                FROM 
                    catalogue_data_json c
                    CROSS JOIN provider_capability_data p
                    LEFT JOIN case_study_data cd ON true;

            """
    # print("sql 0---- ", query)
    # print("--")
    result = database.retrieveSQLQueryOld(query)
    
    # # Check if result is a list
    # if isinstance(result, list):
    #     # Assume the first item in the list is the result you need
    #     result = result[0]
    # else:
    #     # If not a list, proceed as normal
    #     pass
    if result:
        result = result[0]
        
    # print("sql 1---- ", result)
    # print("--")
    
    service_catalogue_data = result.get('service_catalogue_data', []) or []
    provider_capability_data = result.get('provider_capability_data', []) or []
    case_study_data = result.get('case_study_data', []) or []
    
    # print("sql 2---- ", len(case_study_data))
    # print("--")

    # Process case study data
    processed_case_study_data = []
    for case_study in case_study_data:
        if case_study:
            try:
                # Assuming case_study is a JSON string
                case_study_json = json.loads(case_study.get("case_study_details"))
                # Extract relevant fields
                processed_case_study = {
                    'header': case_study_json.get('header'),
                    'summary': case_study_json.get('summary'),
                    'the_problem': case_study_json.get('the_problem')
                }
            except Exception as e:
                print("debug --- fetchProviderInfoForOpportunity error  ", e)
                # Handle JSON parsing error
                processed_case_study = {
                    'header': None,
                    'summary': None,
                    'the_problem': None
                }
        else:
            processed_case_study = {
                'header': None,
                'summary': None,
                'the_problem': None
            }
        processed_case_study_data.append(processed_case_study)

    return {
        'service_catalogue_data': service_catalogue_data,
        'provider_capability_data': provider_capability_data,
        'case_study_data': processed_case_study_data
    }

    # return database.retrieveSQLQueryOld(query)
