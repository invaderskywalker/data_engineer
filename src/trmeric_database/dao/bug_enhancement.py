from src.trmeric_database.Database import db_instance
import uuid
from datetime import datetime


class BugEnhancementDao:
    @staticmethod
    def create_bug_enhancement(tenant_id, type, title, created_by_id, description, priority=None, assigned_to_id=None):
        """
        Create a new bug or enhancement record for a specific tenant.
        :param tenant_id: ID of the tenant (UUID, mandatory)
        :param type: 'bug' or 'enhancement' (mandatory)
        :param title: Title of the bug/enhancement (mandatory)
        :param created_by_id: ID of the user creating the record (mandatory)
        :param description: Description of the bug/enhancement (mandatory)
        :param priority: 'low', 'medium', 'high', or 'critical' (optional)
        :param assigned_to_id: ID of the user assigned (optional)
        :return: Custom ID of the created record
        """
        # Validate mandatory fields
        if not all([tenant_id, type, title, created_by_id]):
            raise ValueError(
                "All mandatory fields (tenant_id, type, title, created_by_id) must be provided")

        # Validate type
        valid_types = {"bug", "enhancement"}
        if type.lower() not in valid_types:
            raise ValueError(f"Type must be one of {valid_types}")

        # Validate priority (if provided)
        valid_priorities = {"low", "medium", "high", "critical"}
        if priority is not None and priority not in valid_priorities:
            priority = "low"

        # Generate computed fields
        text = "B" if type.upper() == "BUG" else "E"
        custom_id = f"TR{text}-{uuid.uuid4().hex[:8]}"
        created_on = datetime.utcnow().isoformat()

        # Mandatory columns and values
        columns = ["tenant_id", "type", "title", "created_by_id"]
        params = [tenant_id, type, title, created_by_id]

        # Optional columns and values (only include if not None or empty)
        optional_fields = {
            "description": description,
            "status": "open",  # Default status
            "priority": priority,
            "created_on": created_on,
            "updated_on": created_on,
            "assigned_to_id": None if assigned_to_id == '' else assigned_to_id,
            "custom_id": custom_id
        }

        for col, val in optional_fields.items():
            if val is not None and val != '':
                columns.append(col)
                params.append(val)

        # Build dynamic query
        query = f"""
            INSERT INTO tango_bugenhancement ({', '.join(columns)})
            VALUES ({', '.join(['%s'] * len(columns))})
        """

        # Execute query
        try:
            result = db_instance.executeSQLQuery(query, tuple(params))
        except Exception as e:
            raise Exception(f"Failed to create bug/enhancement: {str(e)}")

        return custom_id

    @staticmethod
    def fetch_bug_enhancement_by_id(tenant_id, bug_id):
        """
        Fetch a bug/enhancement by its integer ID, scoped to a specific tenant, including usernames.
        :param tenant_id: ID of the tenant (UUID)
        :param bug_id: Integer ID of the bug/enhancement
        :return: Dictionary containing bug/enhancement details or None if not found
        """
        query = """
            SELECT 
                be.id, be.tenant_id, be.type, be.title, be.description, be.status, be.priority,
                be.created_on, be.created_by_id, creator.username AS created_by_username,
                be.updated_on, be.updated_by_id, updater.username AS updated_by_username,
                be.assigned_to_id, assignee.username AS assigned_to_username,
                be.resolution_description, be.resolved_by_id, resolver.username AS resolved_by_username,
                be.comments, be.transaction_history, be.custom_id
            FROM tango_bugenhancement be
            LEFT JOIN users_user creator ON be.created_by_id = creator.id AND creator.tenant_id = '{}'
            LEFT JOIN users_user updater ON be.updated_by_id = updater.id AND updater.tenant_id = '{}'
            LEFT JOIN users_user assignee ON be.assigned_to_id = assignee.id AND assignee.tenant_id = '{}'
            LEFT JOIN users_user resolver ON be.resolved_by_id = resolver.id AND resolver.tenant_id = '{}'
            WHERE be.id = '{}' AND be.tenant_id = '{}'
        """.format(
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(bug_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id))
        )
        data = db_instance.retrieveSQLQueryOld(query)
        return data[0] if data else None

    @staticmethod
    def fetch_bugs_by_tenant(tenant_id, status=None):
        """
        Fetch all bugs/enhancements for a tenant, optionally filtered by status, including usernames.
        :param tenant_id: ID of the tenant (UUID)
        :param status: Optional status filter ('open', 'in_progress', 'resolved', 'closed')
        :return: List of bug/enhancement dictionaries
        """
        query = """
            SELECT 
                be.id, be.tenant_id, be.type, be.title, be.description, be.status, be.priority,
                be.created_on, be.created_by_id, creator.username AS created_by_username,
                be.updated_on, be.updated_by_id, updater.username AS updated_by_username,
                be.assigned_to_id, assignee.username AS assigned_to_username,
                be.resolution_description, be.resolved_by_id, resolver.username AS resolved_by_username,
                be.comments, be.transaction_history, be.custom_id
            FROM tango_bugenhancement be
            LEFT JOIN users_user creator ON be.created_by_id = creator.id AND creator.tenant_id = '{}'
            LEFT JOIN users_user updater ON be.updated_by_id = updater.id AND updater.tenant_id = '{}'
            LEFT JOIN users_user assignee ON be.assigned_to_id = assignee.id AND assignee.tenant_id = '{}'
            LEFT JOIN users_user resolver ON be.resolved_by_id = resolver.id AND resolver.tenant_id = '{}'
            WHERE be.tenant_id = '{}'
        """.format(
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id))
        )
        if status:
            query += " AND be.status = '{}'".format(
                BugEnhancementDao._sanitize_string(status))
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def update_bug_enhancement(tenant_id, bug_id, updates, updated_by_id):
        """
        Update a bug/enhancement record, scoped to a specific tenant using executeSQLQuery.
        :param tenant_id: ID of the tenant (UUID)
        :param bug_id: Integer ID of the bug/enhancement
        :param updates: Dictionary of fields to update (e.g., {'status': 'resolved', 'resolution_description': 'Fixed'})
        :param updated_by_id: ID of the user making the update
        :return: None
        """
        set_clauses = []
        params = []
        for key, value in updates.items():
            if value is not None and key != 'custom_id':  # Prevent updating custom_id unless explicitly allowed
                set_clauses.append(f"{key} = %s")
                params.append(value)
        set_clauses.append("updated_on = %s")
        set_clauses.append("updated_by_id = %s")
        params.extend([datetime.utcnow().isoformat(), updated_by_id])

        if not set_clauses:
            return  # No updates to perform

        query = f"""
            UPDATE tango_bugenhancement
            SET {', '.join(set_clauses)}
            WHERE id = %s AND tenant_id = %s
        """
        params.extend([bug_id, tenant_id])
        db_instance.executeSQLQuery(query, tuple(params))

    @staticmethod
    def resolve_bug_enhancement(tenant_id, bug_id, resolution_description, resolved_by_id):
        """
        Mark a bug/enhancement as resolved with a resolution description, scoped to a tenant using executeSQLQuery.
        :param tenant_id: ID of the tenant (UUID)
        :param bug_id: Integer ID of the bug/enhancement
        :param resolution_description: Description of the resolution
        :param resolved_by_id: ID of the user resolving the issue
        :return: None
        """
        updates = {
            'status': 'resolved',
            'resolution_description': resolution_description,
            'resolved_by_id': resolved_by_id
        }
        BugEnhancementDao.update_bug_enhancement(
            tenant_id, bug_id, updates, resolved_by_id)

    @staticmethod
    def fetch_bugs_by_filters(tenant_id, filters=None):
        """
        Fetch bugs/enhancements for a tenant with dynamic filters, including usernames, compatible with retrieveSQLQueryOld.
        :param tenant_id: ID of the tenant (UUID)
        :param filters: Dictionary of filters (e.g., {'status': 'open', 'created_by_id': 123, 'type': 'bug'})
        :return: List of bug/enhancement dictionaries
        """
        print("fetch_bugs_by_filters ", filters)
        query = """
            SELECT 
                be.id, be.tenant_id, be.type, be.title, be.description, be.status, be.priority,
                be.created_on, be.created_by_id, creator.username AS created_by_username,
                be.updated_on, be.updated_by_id, updater.username AS updated_by_username,
                be.assigned_to_id, assignee.username AS assigned_to_username,
                be.resolution_description, be.resolved_by_id, resolver.username AS resolved_by_username,
                be.comments, be.transaction_history, be.custom_id
            FROM tango_bugenhancement be
            LEFT JOIN users_user creator ON be.created_by_id = creator.id AND creator.tenant_id = '{}'
            LEFT JOIN users_user updater ON be.updated_by_id = updater.id AND updater.tenant_id = '{}'
            LEFT JOIN users_user assignee ON be.assigned_to_id = assignee.id AND assignee.tenant_id = '{}'
            LEFT JOIN users_user resolver ON be.resolved_by_id = resolver.id AND resolver.tenant_id = '{}'
            WHERE be.tenant_id = '{}'
        """.format(
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id))
        )

        # Add filter conditions
        if filters:
            conditions = []
            if "type" in filters:
                conditions.append("be.type = '{}'".format(
                    BugEnhancementDao._sanitize_string(filters["type"])))
            if "status" in filters:
                conditions.append("be.status = '{}'".format(
                    BugEnhancementDao._sanitize_string(filters["status"])))
            if "created_by_id" in filters:
                conditions.append("be.created_by_id = {}".format(
                    BugEnhancementDao._sanitize_integer(filters["created_by_id"])))
            if "resolved_by_id" in filters:
                conditions.append("be.resolved_by_id = {}".format(
                    BugEnhancementDao._sanitize_integer(filters["resolved_by_id"])))
            if "created_on" in filters:
                conditions.append("DATE(be.created_on) = '{}'".format(
                    BugEnhancementDao._sanitize_string(filters["created_on"])))
            if "priority" in filters:
                conditions.append("be.priority = '{}'".format(
                    BugEnhancementDao._sanitize_string(filters["priority"])))
            if conditions:
                query += " AND " + " AND ".join(conditions)

        # Execute query using retrieveSQLQueryOld
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def _sanitize_string(value):
        """
        Sanitize string inputs to prevent SQL injection.
        :param value: String to sanitize
        :return: Sanitized string
        """
        if value is None:
            return ""
        # Remove dangerous characters and escape quotes
        value = str(value).replace("'", "''").replace(";", "").replace(
            "--", "").replace("/*", "").replace("*/", "")
        return value

    @staticmethod
    def _sanitize_integer(value):
        """
        Sanitize integer inputs to prevent SQL injection.
        :param value: Integer to sanitize
        :return: Sanitized integer or 0 if invalid
        """
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
        
    @staticmethod
    def fetch_bugs_by_filters_v2(tenant_id, filters=None):
        """
        Fetch bugs/enhancements for a tenant with dynamic filters, including usernames, compatible with retrieveSQLQueryOld.
        :param tenant_id: ID of the tenant (UUID)
        :param filters: Dictionary of filters (e.g., {'status': 'open', 'created_by_id': 123, 'type': 'bug'})
        :return: List of bug/enhancement dictionaries
        """
        print("fetch_bugs_by_filters ", filters)
        query = """
            SELECT 
                be.tenant_id, be.type, be.title, be.description, be.status, be.priority,
                be.created_on, be.created_by_id, creator.username AS created_by_username,
                be.updated_on, be.updated_by_id, updater.username AS updated_by_username,
                be.assigned_to_id, assignee.username AS assigned_to_username,
                be.resolution_description, be.resolved_by_id, resolver.username AS resolved_by_username,
                be.comments, be.transaction_history, be.custom_id as bug_identifier
            FROM tango_bugenhancement be
            LEFT JOIN users_user creator ON be.created_by_id = creator.id AND creator.tenant_id = '{}'
            LEFT JOIN users_user updater ON be.updated_by_id = updater.id AND updater.tenant_id = '{}'
            LEFT JOIN users_user assignee ON be.assigned_to_id = assignee.id
            LEFT JOIN users_user resolver ON be.resolved_by_id = resolver.id
            WHERE be.tenant_id = '{}'
        """.format(
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id)),
            BugEnhancementDao._sanitize_string(str(tenant_id))
        )

        # Add filter conditions
        if filters:
            conditions = []
            if "type" in filters:
                conditions.append("be.type = '{}'".format(
                    BugEnhancementDao._sanitize_string(filters["type"])))
            if "status" in filters:
                conditions.append("be.status = '{}'".format(
                    BugEnhancementDao._sanitize_string(filters["status"])))
            if "created_by_id" in filters:
                conditions.append("be.created_by_id = {}".format(
                    BugEnhancementDao._sanitize_integer(filters["created_by_id"])))
            if "created_on" in filters:
                conditions.append("DATE(be.created_on) = '{}'".format(
                    BugEnhancementDao._sanitize_string(filters["created_on"])))
            if "priority" in filters:
                conditions.append("be.priority = '{}'".format(
                    BugEnhancementDao._sanitize_string(filters["priority"])))
            if conditions:
                query += " AND " + " AND ".join(conditions)

        result = db_instance.retrieveSQLQueryOld(query)
        print("res", result)
        return result


    @staticmethod
    def get_internal_id_from_custom_id(tenant_id, custom_id):
        query = """
            SELECT id FROM tango_bugenhancement
            WHERE tenant_id = %s AND custom_id = %s
        """
        res = db_instance.execute_query_safe(query, (tenant_id, custom_id))
        return res[0]["id"] if res else None
