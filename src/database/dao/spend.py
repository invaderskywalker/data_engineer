from src.database.Database import db_instance
from src.api.logging.AppLogger import appLogger


class SpendDao:

    @staticmethod
    def FetchProjectsSpend(project_ids, spend_types=None, tenant_id=None):
        """
        Fetch spend for multiple projects.

        Filters:
        - project_ids: list of workflow_project.id
        - spend_types: ['CAPEX'], ['OPEX'], or both
        - tenant_id (optional but recommended)
        """
        print("FetchProjectsSpend ", spend_types, tenant_id)

        if not project_ids:
            return []

        try:
            conditions = []
            params = []

            # Project filter via JOIN
            placeholders = ",".join(["%s"] * len(project_ids))
            conditions.append(f"wp.id IN ({placeholders})")
            params.extend(project_ids)
            
            if not spend_types:
                spend_types = ["CAPEX", "OPEX"]

            # Spend type filter
            if spend_types:
                spend_types = [s.upper() for s in spend_types]
                type_placeholders = ",".join(["%s"] * len(spend_types))
                conditions.append(f"tpro.capex_opex IN ({type_placeholders})")
                params.extend(spend_types)

            # Tenant filter
            if tenant_id:
                conditions.append("tpro.tenant_id = %s")
                params.append(tenant_id)

            where_clause = " AND ".join(conditions)

            query = f"""
                SELECT
                    wp.id AS project_id,
                    tpro.id,
                    tpro.capex_opex,
                    tpro.epmo_number,
                    tpro.vendor,
                    tpro.category,
                    tpro.material_group,
                    tpro.order_value_lc,
                    tpro.ir_value_lc,
                    tpro.pr_value_lc,
                    tpro.open_liability_amount_lc,
                    tpro.po_created_on,
                    tpro.document_date,
                    tpro.pd_fiscal_year_qtr
                FROM
                    tenant_purchase_request_order tpro
                JOIN
                    workflow_project wp
                    ON wp.ref_project_id = tpro.epmo_number
                WHERE
                    {where_clause}
                ORDER BY
                    tpro.po_created_on DESC
            """

            data = db_instance.execute_query_safe(query, tuple(params))
            print("data - ", data)
            return data

        except Exception as e:
            appLogger.error(f"Error FetchProjectsSpend: {e}")
            return []
