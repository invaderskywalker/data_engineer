from src.database.Database import db_instance
from src.api.types.TabularData import TabularData



def fetchAvailableIntegrations(userId) -> TabularData:
    """Fetches the available integrations for the user

    Args:
        userId (str): The user id
        tenantId (str): The tenant id

    Returns:
        list: A list of available integrations
    """
   
    query = f"""
    select * from integration_userconfig where user_id = {userId} and status = 'Active'
    """
    data = db_instance.retrieveSQLQuery(query)
    return data