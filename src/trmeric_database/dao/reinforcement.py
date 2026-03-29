import json
import datetime
from src.trmeric_database.Database import db_instance



class ReinforcementDao:

    @staticmethod
    def fetchTangoFeaturesData(
        feature_ids: list[int] = None,
        projection_attrs: list[str] = ["id", "agent_name", "feature_name", "section", "subsection", "level", "created_at"],
        agent_name: str = None,
        feature_name: str = None,
        section: str = None,
        subsection: str = None,
        level: str = None,
        created_after: str = None,
        created_before: str = None,
        limit: int = 5
    ):
        """
        Dynamically fetch data from tango_features table based on filters and projection attributes.
        """
        # print("\n\n--debug feature-agent,section,subsection in fetchTangoFeaturesData---",agent_name,feature_name,section,subsection)
        try:
            FEATURE_MAP = {
                "id": {"table": "f", "column": "id"},
                "agent_name": {"table": "f", "column": "agent_name"},
                "feature_name": {"table": "f", "column": "feature_name"},
                "section": {"table": "f", "column": "section"},
                "subsection": {"table": "f", "column": "subsection"},
                "level": {"table": "f", "column": "level"},
                "created_at": {"table": "f", "column": "created_at"},
                "updated_at": {"table": "f", "column": "updated_at"},
            }

            select_clauses = []
            where_conditions = []

            # SELECT clause
            for attr in projection_attrs:
                mapping = FEATURE_MAP.get(attr)
                if not mapping:
                    continue
                select_clauses.append(f"{mapping['table']}.{mapping['column']} AS {attr}")

            # WHERE clause
            if feature_ids:
                feature_ids_str = f"({', '.join(map(str, feature_ids))})"
                where_conditions.append(f"f.id IN {feature_ids_str}")
            if agent_name:
                where_conditions.append(f"f.agent_name ILIKE '{agent_name}%'")
            if feature_name:
                where_conditions.append(f"f.feature_name ILIKE '{feature_name}%'")
            if section:
                where_conditions.append(f"f.section ILIKE '{section}%'")
            if subsection:
                where_conditions.append(f"f.subsection ILIKE '{subsection}%'")
            if level:
                where_conditions.append(f"f.level = '{level}'")
            if created_after:
                where_conditions.append(f"f.created_at >= '{created_after}'")
            if created_before:
                where_conditions.append(f"f.created_at <= '{created_before}'")

            select_clause = ",\n                ".join(select_clauses) if select_clauses else "f.id"
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

            query = f"""
                SELECT 
                    {select_clause}
                FROM tango_features AS f
                WHERE {where_clause}
                ORDER BY f.created_at DESC
                LIMIT {limit};
            """
            # print("Generated fetchTangoFeaturesData query:\n", query)
            return db_instance.retrieveSQLQueryOld(query)

        except Exception as e:
            return []



    @staticmethod
    def fetchTangoReinforcementData(
        reinforcement_ids: list[int] = None,
        projection_attrs: list[str] = ["id", "sentiment", "comment", "tenant_id", "user_id", "feature_id", "created_at"],
        sentiment: int = None,
        tenant_id: int = None,
        user_id: int = None,
        feature_id: int = None,
        created_after: str = None,
        created_before: str = None,
        limit: int = 500
    ):
        """
        Dynamically fetch data from tango_reinforcement table based on filters and projection attributes.
        """
        try:
            REINFORCEMENT_MAP = {
                "id": {"table": "r", "column": "id"},
                "sentiment": {"table": "r", "column": "sentiment"},
                "comment": {"table": "r", "column": "comment"},
                "feedback_metadata": {"table": "r", "column": "feedback_metadata"},
                "tenant_id": {"table": "r", "column": "tenant_id"},
                "user_id": {"table": "r", "column": "user_id"},
                "feature_id": {"table": "r", "column": "feature_id"},
                "created_at": {"table": "r", "column": "created_at"},
                "updated_at": {"table": "r", "column": "updated_at"},
            }

            select_clauses = []
            where_conditions = []

            # SELECT clause
            for attr in projection_attrs:
                mapping = REINFORCEMENT_MAP.get(attr)
                if not mapping:
                    continue
                select_clauses.append(f"{mapping['table']}.{mapping['column']} AS {attr}")

            # WHERE clause
            if reinforcement_ids:
                reinforcement_ids_str = f"({', '.join(map(str, reinforcement_ids))})"
                where_conditions.append(f"r.id IN {reinforcement_ids_str}")
            if sentiment is not None:
                where_conditions.append(f"r.sentiment = {sentiment}")
            if tenant_id is not None:
                where_conditions.append(f"r.tenant_id = {tenant_id}")
            if user_id is not None:
                where_conditions.append(f"r.user_id = {user_id}")
            if feature_id is not None:
                where_conditions.append(f"r.feature_id = {feature_id}")
            if created_after:
                where_conditions.append(f"r.created_at >= '{created_after}'")
            if created_before:
                where_conditions.append(f"r.created_at <= '{created_before}'")

            select_clause = ",\n                ".join(select_clauses) if select_clauses else "r.id"
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

            query = f"""
                SELECT 
                    {select_clause}
                FROM tango_reinforcement AS r
                WHERE {where_clause}
                ORDER BY r.created_at DESC
                LIMIT {limit};
            """

            # print("Generated fetchTangoReinforcementData query:\n", query)
            return db_instance.retrieveSQLQueryOld(query)

        except Exception as e:
            return []


    @staticmethod
    def fetchReinforcementDeltaPrompts(tenant_id: int,feature_id: int,user_id:int = None,limit: int = 10):
        """
        Fetch delta prompts from tango_reinforcementlearning table.
        """
        condition = ''
        if user_id:
            condition = f"\n   AND user_id = {user_id}"
        query = f"""
            SELECT delta_prompt, metadata FROM tango_reinforcementlearning
            WHERE tenant_id = {tenant_id} AND feature_id = {feature_id}
            {condition}
            ORDER BY updated_at DESC
            LIMIT {limit}
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            return []

    @staticmethod
    def insertTangoReinforcementData(sentiment: int,comment: str,feedback_metadata: dict,tenant_id: int,user_id: int,feature_id: int):

        query = f"""
            INSERT INTO tango_reinforcement (
                sentiment, comment, feedback_metadata, created_at, updated_at, tenant_id, user_id, feature_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        now = datetime.datetime.now()
        params = (sentiment, comment, feedback_metadata,now,now, tenant_id, user_id, feature_id)
        try:
            db_instance.executeSQLQuery(query, params)
            return {"status": "success", "message": "Reinforcement data inserted successfully"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        

    @staticmethod
    def upsertTangoReinforcementLearning(
        tenant_id: int,
        user_id: int,
        feature_id: str,
        delta_prompt: str,
        metadata: dict = None
    ):
        """
        Upserts a delta prompt entry in tango_reinforcementlearning table.
        If a record exists for (feature_id, tenant_id), it updates delta_prompt and metadata.
        Otherwise, it inserts a new record.
        """
        try:
            user_id_condition = ''
            if user_id:
                user_id_condition = f"\n   AND user_id = {user_id}"
            select_query = f"""
                SELECT id FROM tango_reinforcementlearning
                WHERE feature_id = {feature_id}
                AND tenant_id = {tenant_id}
                {user_id_condition}
                LIMIT 1
            """
            existing = db_instance.retrieveSQLQueryOld(select_query)
            print("--debug existing reinforcement entry--",existing)

            now = datetime.datetime.now()
            metadata_json = json.dumps(metadata or {})

            if existing and len(existing) > 0:
                existing_id = existing[0]['id']
                update_query = """
                    UPDATE tango_reinforcementlearning
                    SET delta_prompt = %s,
                        metadata = %s,
                        updated_at = %s
                    WHERE id = %s
                """
                params = (delta_prompt, metadata_json, now, existing_id)
                db_instance.executeSQLQuery(update_query, params)
                print("Reinforcement state updated successfully",feature_id, tenant_id)

            else:
                insert_query = """
                    INSERT INTO tango_reinforcementlearning (
                        delta_prompt, metadata, created_at, updated_at, feature_id, tenant_id, user_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                params = (delta_prompt,metadata_json,now,now,feature_id,tenant_id,user_id)
                db_instance.executeSQLQuery(insert_query, params)
                print("Reinforcement state created successfully",feature_id, tenant_id)

        except Exception as e:
            print("Error in upsertTangoReinforcementLearning:", str(e))
            return {"status": "error", "message": str(e)}

 