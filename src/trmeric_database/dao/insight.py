import json
from datetime import datetime, timezone
from src.trmeric_database.dao.projects import ProjectsDao
from src.trmeric_database.Database import db_instance
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_database.models.insight import InsightModel, Insights




class InsightDao():

    ATTRIBUTE_MAP: dict[str, dict] = {
        "id": {"table": "ai", "column": "ai.id"},
        "user_id": {"table": "ai", "column": "ai.user_id_id"},
        "tenant_id": {"table": "ai", "column": "ai.tenant_id_id"},
        "type": {"table": "ai", "column": "ai.type"},
        "tag": {"table": "ai", "column": "ai.tag"},
        "state": {"table": "ai", "column": "ai.state"},

        # === UI text ===
        "head_text": {"table": "ai", "column": "ai.head_text"},
        "label_text": {"table": "ai", "column": "ai.label_text"},
        "details_text": {"table": "ai", "column": "ai.details_text"},
        "details_highlight_text": {"table": "ai", "column": "ai.details_highlight_text"},

        "created_date": {"table": "ai", "column": "ai.created_date"},
        "update_date": {"table": "ai", "column": "ai.update_date"},
        "snooze_date": {"table": "ai", "column": "ai.snooze_date"},
        "cron_expiry_date": {"table": "ai", "column": "ai.cron_expiry_date"},
    }

    @staticmethod
    def fetchSignalsWithProjectionAttrs(
        tenant_id: int,
        projection_attrs: list[str] = ["id","type","state","head_text"],
        user_id: int | None = None,
        type_: str | None = None,
        tag: str | None = None,
        head_text: str | None = None,
        state: int | None = 1,
        created_after: datetime | None = None,
    ):
        try:
            select_clauses = []
            where_conditions = [f"ai.tenant_id_id = {tenant_id}"]

            for attr in projection_attrs:
                mapping = InsightDao.ATTRIBUTE_MAP.get(attr)
                if mapping:
                    select_clauses.append(mapping["column"])

            if user_id is not None:
                where_conditions.append(f"ai.user_id_id = {user_id}")
            if type_ is not None:
                where_conditions.append(f"ai.type = '{type_}'")
            if tag is not None:
                where_conditions.append(f"ai.tag = '{tag}'")
            if head_text is not None:
                where_conditions.append(f"ai.head_text ilike '%{head_text}%'")
            if state is not None:
                where_conditions.append(f"ai.state = {state}")
            if created_after:
                where_conditions.append(f"ai.created_date >= '{created_after.isoformat()}'")

            query = f"""
                SELECT
                    {", ".join(select_clauses)}
                FROM actions_insights ai
                WHERE {" AND ".join(where_conditions)}
                ORDER BY ai.update_date DESC;
            """
            print("Debug - fetchSignalsWithProjectionAttrs Query:", query)
            return db_instance.retrieveSQLQueryOld(query)

        except Exception as e:
            print("Error in fetchSignalsWithProjectionAttrs:", str(e))
            return []



    @staticmethod
    def insert_signal(
        user_id: int,
        tenant_id: int,
        type_: str,
        tag: str,
        head_text: str,
        label_text: str,
        details_text: str,
        details_highlight_text: str,
        state: int = 1,
    ):
        try:
            now = datetime.now(timezone.utc)
            query = """
                INSERT INTO actions_insights (
                    user_id_id,type,tag,head_text,label_text,
                    details_text,details_highlight_text,
                    state,created_date,update_date,tenant_id_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            params = (
                user_id,
                type_,
                tag,
                head_text,
                label_text,
                details_text,
                details_highlight_text,
                state,
                now,
                now,
                tenant_id,
            )
            db_instance.executeSQLQuery(query, params)
            return True
        except Exception as e:
            print("Error inserting signal:", str(e))
            return False



    @staticmethod
    def insertInsight(project_id, _type, insight_string, meta_id):
        print("debug ----**** ", project_id, _type, meta_id, insight_string)
        project_info = ProjectsDao.FetchProjectDetails(project_id)
        # print("debug --- ", project_info)
        insight_json = extract_json_after_llm(insight_string)
        created_date = datetime.now()
        tenant_id = int(project_info[0]["tenant_id_id"])
        
        # cust_ = project_info[0]["customer_id_id"]
        
        # customer_id = int(cust_) if cust_ else tenant_id 
        insight_type = _type
        insight_text = insight_json["insight"]

        print("debug insertInsight ", project_id, _type, meta_id, insight_text)

        existing_insight = InsightModel.get_or_none(
            tenant_id = tenant_id,
            # customer_id=customer_id,
            meta_id=meta_id,
            insight_type=insight_type
        )

        if existing_insight:
            existing_insight.updated_on = created_date
            existing_insight.tenant_id = tenant_id
            existing_insight.details_text = insight_text
            existing_insight.save()
            print("Insight updated successfully. ", _type)
        else:
            new_insight = InsightModel(
                updated_on=created_date,
                tenant_id=tenant_id,
                # customer_id=customer_id,
                insight_type=insight_type,
                meta_id=meta_id,
                details_text=insight_text
            )
            is_saved = new_insight.save(force_insert=True)
            print("Insight created successfully", is_saved, _type)
            
            
    @staticmethod
    def save_daily_summary(tenant_id, header, label, _type='Daily Digest'):
        # Creating the Insights object with the provided data
        today_date = datetime.now().strftime('%d %b %y')
        current_datetime = datetime.now()
        insight = Insights.create(
            tenant_id_id=tenant_id,
            tag=today_date,
            type=_type,
            head_text=header,
            label_text=label,
            state=1,
            created_date=current_datetime,
            update_date=current_datetime
        )
        insight.save()
        return insight
