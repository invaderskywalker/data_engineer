def availablePortfoliosQuery(tenantId: int):
    return f"""
            select 
                id as portfolio_id,
                title as portfolio_title,
                description as portfolio_description
            from projects_portfolio 
            where tenant_id_id = {tenantId}
        """


def projectsPerPortfolioQuery(portfolioId: int):
    return f"""
            select 
            wp.id as project_id,
            title as title,
            description as description,
            project_category as category,
            project_manager_id_id as project_manager_id
        From
            workflow_project as wp
        Join 
            users_user as uu on uu.id = wp.project_manager_id_id
        Where
            wp.portfolio_id_id = {portfolioId}
            and wp.parent_id IS NOT NULL
            AND wp.archived_on IS NULL
        """


def eligibleProjectsQuery(user_id: int, tenant_id: int):
    return f"""
        SELECT wp.id
                    FROM workflow_project AS wp
                    WHERE wp.parent_id IS NOT NULL
                    AND wp.archived_on IS NULL
                    AND wp.tenant_id_id = {tenant_id}
                    AND EXISTS (
                        -- User has 'org_admin' role
                        SELECT 1
                        FROM authorization_userorgrolemap AS aurm
                        JOIN authorization_orgroles AS aor ON aor.id = aurm.org_role_id
                        WHERE aurm.user_id = {user_id}
                            AND aor.identifier = 'org_admin'
                    )

                    UNION

                    SELECT wp.id
                    FROM workflow_project AS wp
                    JOIN workflow_projectportfolio AS wpp ON wpp.project_id = wp.id
                    JOIN authorization_portfolioleadermap AS aplm 
                        ON aplm.portfolio_id = wpp.portfolio_id 
                    AND aplm.user_id = {user_id}
                    WHERE wp.parent_id IS NOT NULL
                    AND wp.archived_on IS NULL
                    AND wp.tenant_id_id = {tenant_id}
                    AND EXISTS (
                        -- User has 'org_leader' or 'org_portfolio_leader' role
                        SELECT 1
                        FROM authorization_userorgrolemap AS aurm
                        JOIN authorization_orgroles AS aor ON aor.id = aurm.org_role_id
                        WHERE aurm.user_id = {user_id}
                            AND aor.identifier IN ('org_leader', 'org_portfolio_leader')
                    )

                    UNION

                    SELECT wp.id
                    FROM workflow_project AS wp
                    WHERE wp.parent_id IS NOT NULL
                    AND wp.archived_on IS NULL
                    AND wp.tenant_id_id = {tenant_id}
                    AND NOT EXISTS (
                        -- User is not a portfolio leader
                        SELECT 1
                        FROM authorization_portfolioleadermap AS aplm
                        WHERE aplm.user_id = {user_id}
                    )
                    AND EXISTS (
                        -- User has 'org_leader' or 'org_portfolio_leader' role
                        SELECT 1
                        FROM authorization_userorgrolemap AS aurm
                        JOIN authorization_orgroles AS aor ON aor.id = aurm.org_role_id
                        WHERE aurm.user_id = {user_id}
                            AND aor.identifier IN ('org_leader', 'org_portfolio_leader')
                    )

                    UNION

                    SELECT DISTINCT wp.id
                    FROM workflow_project AS wp
                    WHERE wp.parent_id IS NOT NULL
                    AND wp.archived_on IS NULL
                    AND wp.tenant_id_id = {tenant_id}
                    AND (
                        wp.project_manager_id_id = {user_id} OR
                        wp.created_by_id = {user_id}
                    );

    """
