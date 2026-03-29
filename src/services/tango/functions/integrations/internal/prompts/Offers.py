
from src.trmeric_database.Database import db_instance
from src.trmeric_services.tango.functions.integrations.internal.helpers.SQLHandler import (
    SQL_Handler)

def getBaseQuery(tenant_id):
    query = f"""
With BaseOffers as (
select 
	ao.id,
	max(title) as title,
	max(desc_short) as short_description,
	max(description) as description,
	max(output) as output,
	max(timing) as timing,
	max(expiry_date) as expiry_date,
	max(created_date) as created_date,
	max(view_count) as view_count,
	max(ao.provider_id) as provider_id,
	max(customer_id) as customer_id,
	max(offer_id) as offer_id,
	max(category) as category,
	array_agg(is_paid) as is_paid,
	max(category_sub) as subcategory,
	max(category_tags) as tags
from 
	amplify_offer as ao
join
	amplify_offer_customer_provider_map as aoc on aoc.provider_id = ao.provider_id
group by 
	ao.id
    ), Offers as (
        Select * from BaseOffers 
    ) SELECT * from Offers
    """
    return query

def view_offers(tenantID: int, userID: int, **kwargs): 
    handler = SQL_Handler(getBaseQuery(tenantID))
    query = handler.createSQLQuery()
    response = db_instance.retrieveSQLQuery(query).formatData()
    return response

ARGUMENTS = []

RETURN_DESCRIPTION = """
Returns a list of all the offers in the system for a specific company. 
"""