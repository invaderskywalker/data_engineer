from src.database.Database import db_instance
from src.utils.enums import AuthRoles

class AuthDao:
    @staticmethod
    def fetchRoleOfUserInTenant(user_id) -> AuthRoles:
        query = f"""
            select aor.identifier as role from authorization_userorgrolemap as aurm
            join authorization_orgroles as aor on aor.id = aurm.org_role_id
            where aurm.user_id = {user_id}
        """
        data = db_instance.retrieveSQLQueryOld(query)
        if len(data) > 0:
            role = data[0]["role"]
            if AuthRoles.has_role(role):
                return AuthRoles(role).name
            return role
        else:
            return None
        
    @staticmethod
    def fetchAllRolesInTrmericForTenant(tenant_id):
        query = f"""
            select distinct aor.identifier as role from authorization_userorgrolemap as aurm
            join authorization_orgroles as aor on aor.id = aurm.org_role_id
            where aurm.tenant_id = {tenant_id}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            return []

    @staticmethod
    def fetchAllRolesOfUserInTenant(user_id) -> list[AuthRoles]:
        query = f"""
            select aor.identifier as role from authorization_userorgrolemap as aurm
            join authorization_orgroles as aor on aor.id = aurm.org_role_id
            where aurm.user_id = {user_id}
        """
        data = db_instance.retrieveSQLQueryOld(query)
        result = []
        if len(data) > 0:
            for d in data:
                role = d.get("role")
                if AuthRoles.has_role(role):
                    result.append(AuthRoles(role).name)
            return result
        else:
            return []

    @staticmethod
    def fetchAllUsersOfRoleInTenant(role: AuthRoles|str, tenant_id: int) -> list[int]:
        role_identifier = role.value if isinstance(role, AuthRoles) else role
        try:
            query = f"""
                 SELECT DISTINCT
                    u.id    AS user_id,
                    u.email AS email,
                    u.first_name,
                    u.last_name
                FROM authorization_userorgrolemap AS aurm
                JOIN authorization_orgroles AS aor
                    ON aor.id = aurm.org_role_id
                JOIN users_user AS u
                    ON u.id = aurm.user_id
                WHERE
                    aurm.tenant_id = {tenant_id}
                    AND aor.identifier = '{role_identifier}'
                    AND aurm.deleted_on IS NULL
                    AND u.is_active = TRUE
            """
            data = db_instance.retrieveSQLQueryOld(query)
            return data
        except Exception as e:
            print("Error fetching users of role:", e)
            return []