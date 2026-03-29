from src.trmeric_database.dao.portfolios import PortfolioDao

def portfolio_data(tenant_id):
    """Fetch portfolio data for the given tenant ID."""
    data = PortfolioDao.fetchPortfoliosOfTenant(tenant_id=tenant_id)
    final_data = []
    for i in range(len(data)):  
        portfolio = {
            "id": i,
            "filter_value": data[i].get("id"),
            "description": "Portfolio Title: " + data[i].get("title"),
        }
        final_data.append(portfolio)
    return final_data

ROW_MAPPINGS = [
    {"name": "portfolio", "columns": ["portfolio_id"], "data": portfolio_data, "args": ["tenant_id"], "type": "exact", "description": "This is a mapping of portfolio IDs to portfoliio names for this tenant."},
]
