from peewee import (
    CharField,
    TextField,
    IntegerField,
    DateTimeField,
    SmallIntegerField,
)
from src.trmeric_database.models.tango import UserCache, Stats, TangoStates, TangoIntegrationSummary
from src.trmeric_database.Database import db_instance
from datetime import datetime, timedelta
import json
import traceback
import re
import ast
from src.trmeric_api.logging.AppLogger import appLogger
import uuid


class TangoDao:

    @staticmethod
    def createEntryInStats(
        tenant_id,
        user_id,
        function_name,
        model_name,
        total_tokens,
        prompt_tokens,
        completion_tokens
    ):
        now = datetime.now()
        query = """
            INSERT INTO tango_stats(
                id,user_id,tenant_id,function,model,total_tokens,prompt_tokens,completion_tokens,created_date
            ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        params = (  
            str(uuid.uuid4()),user_id,tenant_id,function_name,model_name,
            total_tokens,prompt_tokens,completion_tokens,now
        )
        try:
            db_instance.executeSQLQuery(query, params)
            return {"status": "success", "message": "Reinforcement data inserted successfully"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

        # new_stats = Stats.create(
        #     user_id=user_id,
        #     tenant_id=tenant_id,
        #     function=function_name,
        #     model=model_name,
        #     total_tokens=total_tokens,
        #     prompt_tokens=prompt_tokens,
        #     completion_tokens=completion_tokens
        # )
        # new_stats.save()
        # return

    @staticmethod
    def fetchCacheByUserId(userId):
        pass
        # one_day_ago = datetime.now() - timedelta(days=1)
        # result = UserCache.get_or_none(
        #     (UserCache.user_id == userId) & (UserCache.tenant_id == tenantId)
        # )
        # if result:
        #     if result.updated_date < one_day_ago:
        #         # gather data to update - new_cache_data
        #         result.cache = new_cache_data
        #         result.updated_date = datetime.now()
        #         result.save()
        #         print(f"Cache for user {userId} updated.")
        #         return result
        #     else:
        #         print(f"Record {result.id} is not more than one day old.")
        #         return result
        # else:
        #     # gather data to update - new_cache_data
        #     new_record = UserCache.create(
        #         user_id=userId,
        #         tenant_id=tenantId,
        #         cache=new_cache_data,
        #         created_date=datetime.now(),
        #         updated_date=datetime.now()
        #     )
        #     return new_record
    
    @staticmethod
    def fetchTangoStatesForSessionId(session_id):
        query = f"""
            SELECT * FROM tango_states where session_id = '{session_id}'
            ORDER BY created_date ASC
        """
        
        states = db_instance.retrieveSQLQueryOld(query)
        ONBOARDING_PROJECT_STATES = ['ONBOARDING_PROJECT_CLARIFYING_QUESTION', 'ONBOARDING_PROJECT_SYNC', 'ONBOARDING_PROJECT_SHOW_INTEGRATION', 'ONBOARDING_PROJECT_FINISHED', 'ONBOARDING_PROJECT_INTEGRATIONS_CONFIRMED', 'ONBOARDING_PROJECT_SOURCE_INFORMATION']
        ONBOARDING_ROADMAP_STATES = ['ONBOARDING_ROADMAP_CLARIFYING_QUESTION', 'ONBOARDING_ROADMAP_SYNC', 'ONBOARDING_ROADMAP_SHOW_INTEGRATION', 'ONBOARDING_ROADMAP_FINISHED', 'ONBOARDING_ROADMAP_INTEGRATIONS_CONFIRMED', 'ONBOARDING_ROADMAP_SOURCE_INFORMATION']
        ONBOARDING_PROFILE_STATES = ['ONBOARDING_PROFILE_SHOW_SOURCE', 'ONBOARDING_PROFILE_CLARIFYING_QUESTION', 'ONBOARDING_PROFILE_FINISHED', 'ONBOARDING_PROFILE_SOURCE_INFORMATION']
        
        ONBOARDING_CAPACITY_STATES = [
            'ONBOARDING_CAPACITY_SHOW_SOURCE_INTERNAL','ONBOARDING_CAPACITY_SHOW_SOURCE_PROVIDER',
            'ONBOARDING_CAPACITY_LOOKS_GOOD_INTERNAL','ONBOARDING_CAPACITY_LOOKS_GOOD_PROVIDER',
            'ONBOARDING_CAPACITY_SOURCE_INFORMATION_PROVIDER','ONBOARDING_CAPACITY_SOURCE_INFORMATION_INTERNAL',
            'ONBOARDING_CAPACITY_CLARIFYING_QUESTION','ONBOARDING_CAPACITY_FINISHED'
        ]

        final_states = []
        for state in states:
            if state['key'] == "ONBOARDING_PROJECT_CANCEL":
                state_copy = []
                for final_state in final_states:
                    if final_state['key'] not in ONBOARDING_PROJECT_STATES:
                        state_copy.append(final_state)
                final_states = state_copy
            elif state['key'] == "ONBOARDING_ROADMAP_CANCEL":
                state_copy = []
                for final_state in final_states:
                    if final_state['key'] not in ONBOARDING_ROADMAP_STATES:
                        state_copy.append(final_state)
                final_states = state_copy
            elif state['key'] == "ONBOARDING_PROFILE_CANCEL":
                state_copy = []
                for final_state in final_states:
                    if final_state['key'] not in ONBOARDING_PROFILE_STATES:
                        state_copy.append(final_state)
                final_states = state_copy
            elif state['key'] == "ONBOARDING_CAPACITY_CANCEL":
                state_copy = []
                for final_state in final_states:
                    if final_state['key'] not in ONBOARDING_CAPACITY_STATES:
                        state_copy.append(final_state)
                final_states = state_copy
            else:
                final_states.append(state)
        
        return final_states
    
    @staticmethod            
    def fetchTangoStatesForUserIdbyKey(user_id, key):
        query = f"""
            SELECT * FROM tango_states 
            WHERE user_id = {user_id} 
            AND key = '{key}'
            ORDER BY created_date DESC
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def insertTangoState(tenant_id, user_id, key, value, session_id):
        """
        Updates the value in TangoStates if it exists; otherwise, creates a new row.
        """
        try:
            query = f"""
                INSERT INTO tango_states (id, tenant_id, user_id, key, value, session_id, created_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            params = (str(uuid.uuid4()), tenant_id, user_id, key, value, session_id, datetime.now())
            db_instance.executeSQLQuery(query, params)
            
            # new_state = TangoStates.create(
            #     tenant_id=tenant_id,
            #     user_id=user_id,
            #     key=key,
            #     value=value,
            #     session_id=session_id
            # )
            # new_state.save()
            print("Tango state created successfully ", key)
            appLogger.info({"function":"insertTangoState","event":"DB_ENTRY","key":key,"tenant_id":tenant_id,"user_id":user_id,"session_id":session_id})
            
        except Exception as e:
            print("Error in upserting Tango state:", e)
            appLogger.error({"function": "insertTangoState", "event": "DB_ENTRY", "error": str(e)})
            
    @staticmethod
    def upsertTangoState(tenant_id, user_id, key, value, session_id):
        """
        Updates the value in TangoStates if it exists; otherwise, creates a new row.
        """
        try:
            # Check for existing record
            conditional = f" AND user_id = {user_id}"
            session_id_condition = f" AND session_id like '{session_id}'"
            
            if user_id is None:
                conditional = ""
            if session_id is None:
                session_id_condition = ""
            
            select_query = f"""
                SELECT id FROM tango_states
                WHERE tenant_id = {tenant_id}
                {conditional}
                AND key like '{key}'
                {session_id_condition}
            """
            state_result = db_instance.retrieveSQLQueryOld(select_query)

            if len(state_result)>0:
                # Update existing record
                update_query = """
                    UPDATE tango_states
                    SET value = %s,
                        created_date = %s
                    WHERE id = %s
                """
                update_params = (value, datetime.now(), state_result[0]['id'])
                db_instance.executeSQLQuery(update_query, update_params)
                print("Tango state updated successfully",key)
            else:
                # Insert new record
                appLogger.info({"function":"upsertTangoState","event":"DB_NEW_ENTRY","key":key,"tenant_id":tenant_id,"user_id":user_id,"session_id":session_id})
                return TangoDao.insertTangoState(tenant_id, user_id, key, value, session_id)

        except Exception as e:
            print(f"Error upserting Tango state: {e}")
            appLogger.error({"function": "upsertTangoState","event": "DB_UPSERT","error": str(e)})
            
        # try:
        #     # Try to fetch the existing record
        #     tango_state = TangoStates.get_or_none(
        #         TangoStates.tenant_id == tenant_id,
        #         TangoStates.user_id == user_id,
        #         TangoStates.key == key,
        #         TangoStates.session_id == session_id
        #     )

        #     if tango_state:
        #         # Update the existing record
        #         tango_state.value = value
        #         tango_state.created_date = datetime.now()
        #         tango_state.save()
        #         print("Tango state updated successfully")
        #     else:
        #         new_state = TangoStates.create(
        #             tenant_id=tenant_id,
        #             user_id=user_id,
        #             key=key,
        #             value=value,
        #             session_id=session_id
        #         )
        #         new_state.save()
        #         print("Tango state created successfully")
        # except Exception as e:
        #     print("Error in upserting Tango state:", e)   

    @staticmethod
    def updateJiraIntegrationSummary(tenant_id, user_id, key, value):
        """
        Updates the value in TangoStates if it exists; otherwise, creates a new row.
        """
        try:
            tango_state = TangoIntegrationSummary.get_or_none(
                TangoIntegrationSummary.tenant_id == tenant_id,
                TangoIntegrationSummary.user_id == user_id,
                TangoIntegrationSummary.key == key,
            )
            if tango_state:
                tango_state.value = value
                tango_state.save()
                print("Tango updateJiraIntegrationSummary updated successfully")
            else:
                new_state = TangoIntegrationSummary.create(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    key=key,
                    value=value
                )
                new_state.save()
                print("Tango updateJiraIntegrationSummary created successfully")
        except Exception as e:
            print("Error in upserting Tango updateJiraIntegrationSummary:", e)

    @staticmethod
    def fetchTangoIntegrationAnalysisDataForTenant(tenant_id):
        query = f"""
            SELECT * FROM tango_integrationsummary where tenant_id = {tenant_id}
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchTangoIntegrationAnalysisDataForTenantForProject(tenant_id, key):
        query = f"""
            SELECT * FROM tango_integrationsummary where tenant_id = {tenant_id} and key='{key}'
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    
    @staticmethod
    def fetchTangoIntegrationKeyAnalysisDataForTenant(tenant_id):
        query = f"""
            SELECT key FROM tango_integrationsummary where tenant_id = {tenant_id}
        """
        result = db_instance.retrieveSQLQueryOld(query)
        print("debug fetchTangoIntegrationKeyAnalysisDataForTenant ", result)
        nres = []
        for res in result:
            item = res["key"]
            if item.startswith("JIRA_ANALYSIS"):
                item = item[len("JIRA_ANALYSIS_"):]
            nres.append(item.strip())
        print("debug fetchTangoIntegrationKeyAnalysisDataForTenant ", nres)
        return nres
    
    @staticmethod
    def fetchTangoStates(user_id, key):
        query = f"""
        SELECT  *
            FROM tango_states
            WHERE user_id = {user_id}
            AND key = '{key}'
            ORDER BY key, created_date DESC
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchTangoStatesTenant(tenant_id, key, _limit = 100):
        query = f"""
            SELECT  *
                FROM tango_states
                WHERE tenant_id = {tenant_id}
                AND key = '{key}'
                ORDER BY key, created_date DESC
                limit {_limit}
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchLatestTangoStatesTenant(tenant_id, key):
        query = f"""
        SELECT  *
            FROM tango_states
            WHERE tenant_id = {tenant_id}
            AND key = '{key}'
            ORDER BY created_date DESC
            limit 1
        """
        return db_instance.retrieveSQLQueryWithPool(query)
    
    
    @staticmethod
    def fetchLatestTangoStatesForTenant(tenant_id, key):
        query = f"""
        SELECT  *
            FROM tango_states
            WHERE tenant_id = {int(tenant_id)}
                AND key ilike '{key}%'
                ORDER BY created_date DESC
                LIMIT 1
        """
        result = db_instance.retrieveSQLQueryWithPool(query)
        return result[0] if result else None
    
    @staticmethod
    def fetchLatestTangoStatesTenantMultiple( keys):
        """
        Fetch the latest tango_states records for multiple keys in a single query.
        Returns the most recent record for each key.
        """
        if not keys:
            return []
        
        quoted_keys = []
        for key in keys:
            escaped_key = key.replace("'", "''")  # escape single quotes
            quoted_keys.append(f"'{escaped_key}'")
            
        # keys_str = f"({', '.join(key_str_arr)})"
        keys_str = f"({', '.join(quoted_keys)})"

            
        

        query = f"""
            WITH RankedStates AS (
                SELECT *,
                    ROW_NUMBER() OVER (PARTITION BY key ORDER BY created_date DESC) as rn
                FROM tango_states
                WHERE key IN {keys_str}
            )
            SELECT *
            FROM RankedStates
            WHERE rn = 1
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchLatestTangoStateForKeyForTenantAndUser(tenant_id, user_id, key):
        query = f"""
            SELECT DISTINCT ON (key) value,created_date FROM tango_states 
            WHERE key like '%{key}%'
            AND tenant_id = {tenant_id} 
            AND user_id = {user_id}
            ORDER BY key, created_date DESC
            LIMIT 1
        """
        try:
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e: 
            return []
    
    @staticmethod
    def fetchTangoStatesForUserForProjectStatusUpdate(user_id, tenant_id):
        query = f"""
            SELECT DISTINCT ON (key) value
            FROM tango_states
            -- WHERE user_id = {user_id}
            where tenant_id = {tenant_id}
            AND key LIKE 'SERVICE_ASSURANCE_AGENT_UPDATE_STATUS_DATA_FOR_PROJECT_%'
            ORDER BY key, created_date DESC
        """
        
        def fix_unescaped_quotes(json_string):
            # Use regex to escape unescaped quotes inside the string
            # return re.sub(r'(?<!\\)"', r'\\"', json_string)
            # return json_string.replace(r'\"', '"')
            return re.sub(r'(?<!\\)"', r'\\"', json_string)
        
    
        def convert_single_to_double_quotes(json_string):
            # Replace single quotes with double quotes
            return json_string.replace("'", '"')
        
        data =  db_instance.retrieveSQLQueryOld(query)
        ndata = []
        for d in data:
            try :
                
                formatted_value = d['value'].strip()
                # print("Debug Original Data:", formatted_value)
                
                # Reformat the dictionary string into a real dictionary using ast.literal_eval
                dict_value = ast.literal_eval(formatted_value)
                
                # Convert the dictionary back to a JSON string
                formatted_json_string = json.dumps(dict_value)
                # print("Debug Formatted JSON String:", formatted_json_string)
            
                # # formatted_value = d["value"].replace("'", "\"")
                # print("debug 1111--- ", d["value"])
                # # Get the value and convert single quotes to double quotes
                # formatted_value = convert_single_to_double_quotes(d["value"])
                
                # # Optional: Escape unescaped quotes
                # formatted_value = fix_unescaped_quotes(formatted_value)
                
                
                # # formatted_value = fix_unescaped_quotes(d["value"])
                # print("debug 2222--- ", formatted_value, type(formatted_value))
                json_data = json.loads(formatted_json_string)
                ndata.append(json_data)
            except Exception as e:
                print("error here ... ", e, traceback.format_exc() )
            # ndata.append(json.loads(d["value"]))
        
        return ndata
    
    
    @staticmethod
    def fetchLatestTangoStateForProjectForTenant(tenant_id, project_id):
        query = f"""
            SELECT DISTINCT ON (key) value
            FROM tango_states
            WHERE tenant_id = {tenant_id}
            AND key='SERVICE_ASSURANCE_AGENT_UPDATE_STATUS_DATA_FOR_PROJECT_{project_id}'
            ORDER BY key, created_date DESC
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    
    @staticmethod
    def checkIfTangoLockedStateForConversation(user_id, session_id):
        query = f"""
        SELECT  *
            FROM tango_states
            WHERE user_id = {user_id}
            AND session_id = '{session_id}'
            ORDER BY created_date DESC
        """
        all_data = db_instance.retrieveSQLQueryOld(query)
        locked = None
        for d in all_data:
            if d["key"] == "STATE_UNLOCKED":
                break
            if d["key"] == "STATE_LOCKED":
                locked = json.loads(d["value"])
                break
        return locked
        
        
    @staticmethod
    def fetchTangoStatesForSessionIdAndUserAndKey(session_id, user_id, key):
        query = f"""
            SELECT * FROM tango_states where session_id = '{session_id}' and user_id = {user_id} and key='{key}'
            ORDER BY created_date desc
            limit 1
        """
        # print("query --- ", query)
        return db_instance.retrieveSQLQueryOld(query)
    
    
    @staticmethod
    def deleteTangoStatesForSessionIdAndUserAndKey(session_id, user_id, key):
        query = """
            DELETE FROM tango_states 
            WHERE session_id = %s 
            AND user_id = %s 
            AND key = %s
        """
        params = (session_id, user_id, key)
        return db_instance.executeSQLQuery(query, params)
    
    
    @staticmethod
    def deleteTangoStatesForSessionIdAndTenantAndKey(session_id, tenant_id, key):
        query = """
            DELETE FROM tango_states 
            WHERE session_id = %s 
            AND tenant_id = %s 
            AND key = %s
        """
        params = (session_id, tenant_id, key)
        return db_instance.executeSQLQuery(query, params)



    @staticmethod
    def fetchTangoStatesForSessionIdAndUserAndKeyAll(session_id, user_id, key):
        query = f"""
            SELECT * FROM tango_states where session_id = '{session_id}' and user_id = {user_id} and key='{key}'
            ORDER BY created_date desc
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchTangoStatesForUserAndKeyAll(user_id, key):
        query = f"""
            SELECT * FROM tango_states where user_id = {user_id} and key='{key}'
            ORDER BY created_date desc
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchTangoStatesForSessionIdAndUserAndKeyAllValue(session_id, user_id, key):
        query = f"""
            SELECT value FROM tango_states where session_id = '{session_id}' and user_id = {user_id} and key='{key}'
            ORDER BY created_date desc
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchChatsForSessionAndTypes(session_id, types=[1,3,5,6,7]):
        types_str = f"({', '.join(map(str, types))})" 
        query = f"""
            SELECT * FROM tango_tangoconversations
            where session_id = '{session_id}' 
            and type in {types_str}
            ORDER BY created_date asc
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchLatestQuestionId(user_id, session_id):
        session_id = session_id + 'combined'
        query = f"""
            SELECT id FROM tango_tangoconversations
            where session_id = '{session_id}' 
            and type = 1
            and created_by_id = {user_id}
            ORDER BY created_date asc
        """
        res = db_instance.retrieveSQLQueryOld(query)
        if len(res) >0:
            return res[0].get("id")
        return None

    @staticmethod
    def handleEditOrRegenerateMsg(user_id:int,session_id:str,metadata:dict):

        if not metadata or (metadata.get('event',None) != 'edit_or_regenerate'):
            return {"msg": f"Error in payload: {metadata}", 'user_id': user_id,'session_id': session_id}
        
        message_id = metadata.get('message_id',None) or None
        if not message_id:
            return {"msg": f"No msg_id: {message_id} in {metadata}", 'user_id': user_id,'session_id': session_id}

        response_id = message_id + 1 ####delete the message_id and next id i.e. tango's response
        placeholders = ', '.join(['%s'] * 2)
        query = f"""
            DELETE FROM public.tango_tangoconversations
            WHERE id IN ({placeholders})
            AND session_id = %s
            AND created_by_id = %s
        """
        params = (message_id, response_id, f"{session_id}combined", user_id)
        try:
            res = db_instance.executeSQLQuery(query, params)
            appLogger.info({'event':'handleEditOrRegenerateMsg','result': res,'user_id':user_id,'metadata': metadata,'session_id': session_id})
        except Exception as e:
            appLogger.error({'event':'handleEditOrRegenerateMsg','error': str(e),'traceback': traceback.format_exc(),'user_id':user_id,'session_id': session_id})

    
    @staticmethod
    def fetchChatTitlesForUser(user_id):
        query = f"""
            SELECT * FROM public.tango_chattitles
            where user_id = {user_id}
            ORDER BY id desc 
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    @staticmethod
    def fetchChatTitleForSession(session_id):
        query = f"""
            SELECT * FROM public.tango_chattitles
            where session_id = '{session_id}'
            ORDER BY id desc 
        """
        result = db_instance.retrieveSQLQueryOld(query)
        if (len(result) > 0):
            result[0]["title"]
        else:
            return None
        
    @staticmethod
    def insert_chat_title(session_id, title, tenant_id, user_id, agent_name='tango'):
        query = """
            INSERT INTO public.tango_chattitles (
                session_id, created_at, updated_at, title, tenant_id, user_id, agent_name
            ) VALUES (%s, NOW(), NOW(), %s, %s, %s, %s)
            ON CONFLICT (session_id)
            DO UPDATE SET
                title = EXCLUDED.title,
                tenant_id = EXCLUDED.tenant_id,
                user_id = EXCLUDED.user_id,
                agent_name = EXCLUDED.agent_name,
                updated_at = NOW()
        """
        db_instance.executeSQLQuery(
            query,
            (session_id, title, tenant_id, user_id, agent_name)
        )

        
    @staticmethod
    def insertToCollaborativeChat(params):
        insert_query = """
            INSERT INTO tango_collaborativechat (
                tenant_id, created_by_id, message, session_id, step, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id, created_at;
        """
        return db_instance.executeSQLQuery(insert_query, params)
        
    @staticmethod
    def fetchCollaborativeChat(session_id, tenant_id):
        fetch_query = f"""
            SELECT *
            FROM tango_collaborativechat
            WHERE session_id = '{session_id}' AND tenant_id = {tenant_id}
            ORDER BY created_at ASC;
        """
        return db_instance.retrieveSQLQueryOld(fetch_query)
    
    @staticmethod
    def fetchCollaborativeChatAndFormat(session_id, tenant_id):
        chats = TangoDao.fetchCollaborativeChat(session_id=session_id, tenant_id=tenant_id)
        res = []
        for chat in chats:
            if chat.get("step") == 1:
                res.append(f'User: {chat.get("message")}')
            if chat.get("step") == 2:
                res.append(f'Agent Thoughts: {chat.get("message")}')
            if chat.get("step") == 3:
                res.append(f'Agent Final Response: {chat.get("message")}')
                
        return res
    
    
    @staticmethod
    def fetchCollaborativeChatsForClient(session_id, tenant_id):
        fetch_query = f"""
            SELECT *
            FROM tango_collaborativechat
            WHERE session_id = '{session_id}' AND tenant_id = {tenant_id} and step in (1,3)
            ORDER BY created_at ASC;
        """
        return db_instance.retrieveSQLQueryOld(fetch_query)
    
    @staticmethod
    def fetchCollaborativeChatsForClientSaved(session_id, tenant_id):
        fetch_query = f"""
            SELECT c.*, s.saved
            FROM tango_collaborativechat c
            INNER JOIN tango_onboardingv2step s ON c.session_id = s.session_id
            WHERE c.session_id = {session_id}
            AND c.tenant_id = {tenant_id}
            AND c.step IN (1, 3)
            AND s.saved = TRUE
            ORDER BY c.created_at ASC;
        """
        # params = (session_id, tenant_id)
        return db_instance.retrieveSQLQueryOld(fetch_query)
    
    
    @staticmethod
    def fetchTangoStatesForTenantAndKey(tenant_id, key):
        query = f"""
            SELECT * FROM tango_states where tenant_id = {tenant_id} and key='{key}'
            ORDER BY created_date desc
            limit 1
        """
        result = db_instance.retrieveSQLQueryOld(query)
        if len(result) > 0:
            return result[0]["value"]
        else:
            return None

    @staticmethod
    def insertTangoActivity(socket_id, tenant_id, user_id, agent_or_workflow_name,
                            input_data, output_data, status, metrics, description=""):
        try:
            agent_or_workflow_name_truncated = (agent_or_workflow_name[:50]) if agent_or_workflow_name else None
            status_truncated = (status[:50]) if status else None

            query = """
                    INSERT INTO tango_activitylog (
                        id, session_id, tenant_id, user_id,
                        agent_or_workflow_name, input_data, output_data,
                        created_date, status, metrics
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
            id = uuid.uuid4()
            db_instance.executeSQLQuery(query, (id, socket_id, tenant_id, user_id,
                                                 agent_or_workflow_name_truncated, input_data, output_data,
                                                 datetime.now(), status_truncated, metrics))

            TangoDao.insertActivityLogDetailed(activity_name=agent_or_workflow_name_truncated, activity_description=description, status=status_truncated, enhancement_id=id, socket_id=socket_id, tenant_id=tenant_id, user_id=user_id)
        except Exception as e:
            appLogger.error({
                "function": "insertTangoActivity",
                "event": "DB_INSERT_ERROR",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "socket_id": socket_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "agent_or_workflow_name": agent_or_workflow_name
            })

    @staticmethod
    def fetchTangoActivityForIDs(ids: list):
        # Properly quote each ID for SQL
        ids_str = ','.join([f"'{id}'" for id in ids])
        try:
            query = f"""
                SELECT id, input_data, output_data
                FROM tango_activitylog
                WHERE id IN ({ids_str})
                ORDER BY created_date ASC
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            print(f"Error fetching activity log for IDs {ids}: {e}")
            appLogger.error({
                "function": "fetchTangoActivityForIDs",
                "event": "DB_FETCH_ERROR",
                "ids": ids,
                "error": str(e)
            })
            return []
        
    @staticmethod
    def fetchTangoActivityDetailedForSession(socket_id):
        try:
            query = f"""
                SELECT id, activity_name, activity_description, enhancement_id, user_id, tenant_id
                FROM tango_activitylogdetailed
                WHERE session_id = '{socket_id}'
                ORDER BY created_date ASC
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            print(f"Error fetching activity log for session {socket_id}: {e}")
            appLogger.error({
                "function": "fetchTangoActivityForSession",
                "event": "DB_FETCH_ERROR",
                "socket_id": socket_id,
                "error": str(e)
            })
            return []
    
    @staticmethod
    def insertActivityLogDetailed(activity_name, activity_description, status, socket_id, tenant_id, user_id, enhancement_id=None):
        """
        Insert a new record into the ActivityLogDetailed table.
        enhancement_id can be None.
        """
        try:
            query = """
                INSERT INTO tango_activitylogdetailed (
                    id, activity_name, activity_description, status, enhancement_id, session_id, tenant_id, created_date, user_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                uuid.uuid4(),
                activity_name,
                activity_description,
                status,
                enhancement_id,
                socket_id,
                tenant_id,
                datetime.now(),
                user_id
            )
            db_instance.executeSQLQuery(query, params)
        except Exception as e:
            appLogger.error({
                "function": "insertActivityLogDetailed",
                "event": "DB_INSERT_ERROR",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "activity_name": activity_name,
                "socket_id": socket_id,
                "tenant_id": tenant_id,
                "user_id": user_id
            })
        
    @staticmethod
    def deleteChatTitle(user_id, chat_id):
        query = """
            DELETE FROM public.tango_chattitles
            WHERE id = %s AND user_id = %s
        """
        return db_instance.executeSQLQuery(query, (chat_id, user_id))
    
    

    @staticmethod
    def insertTangoActivity(socket_id, tenant_id, user_id, agent_or_workflow_name,
                            input_data, output_data, status, metrics, description=""):
        try:
            agent_or_workflow_name_truncated = (agent_or_workflow_name[:50]) if agent_or_workflow_name else None
            status_truncated = (status[:50]) if status else None

            query = """
                    INSERT INTO tango_activitylog (
                        id, session_id, tenant_id, user_id,
                        agent_or_workflow_name, input_data, output_data,
                        created_date, status, metrics
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
            id = uuid.uuid4()
            db_instance.executeSQLQuery(query, (id, socket_id, tenant_id, user_id,
                                                 agent_or_workflow_name_truncated, input_data, output_data,
                                                 datetime.now(), status_truncated, metrics))

            TangoDao.insertActivityLogDetailed(activity_name=agent_or_workflow_name_truncated, activity_description=description, status=status_truncated, enhancement_id=id, socket_id=socket_id, tenant_id=tenant_id, user_id=user_id)
        except Exception as e:
            appLogger.error({
                "function": "insertTangoActivity",
                "event": "DB_INSERT_ERROR",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "socket_id": socket_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "agent_or_workflow_name": agent_or_workflow_name
            })

    @staticmethod
    def fetchTangoActivityForIDs(ids: list):
        # Properly quote each ID for SQL
        ids_str = ','.join([f"'{id}'" for id in ids])
        try:
            query = f"""
                SELECT id, input_data, output_data
                FROM tango_activitylog
                WHERE id IN ({ids_str})
                ORDER BY created_date ASC
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            print(f"Error fetching activity log for IDs {ids}: {e}")
            appLogger.error({
                "function": "fetchTangoActivityForIDs",
                "event": "DB_FETCH_ERROR",
                "ids": ids,
                "error": str(e)
            })
            return []
        
    @staticmethod
    def fetchTangoActivityDetailedForSession(socket_id):
        try:
            query = f"""
                SELECT id, activity_name, activity_description, enhancement_id, user_id, tenant_id
                FROM tango_activitylogdetailed
                WHERE session_id = '{socket_id}'
                ORDER BY created_date ASC
            """
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            print(f"Error fetching activity log for session {socket_id}: {e}")
            appLogger.error({
                "function": "fetchTangoActivityForSession",
                "event": "DB_FETCH_ERROR",
                "socket_id": socket_id,
                "error": str(e)
            })
            return []
    
    @staticmethod
    def insertActivityLogDetailed(activity_name, activity_description, status, socket_id, tenant_id, user_id, enhancement_id=None):
        """
        Insert a new record into the ActivityLogDetailed table.
        enhancement_id can be None.
        """
        try:
            query = """
                INSERT INTO tango_activitylogdetailed (
                    id, activity_name, activity_description, status, enhancement_id, session_id, tenant_id, created_date, user_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                uuid.uuid4(),
                activity_name,
                activity_description,
                status,
                enhancement_id,
                socket_id,
                tenant_id,
                datetime.now(),
                user_id
            )
            db_instance.executeSQLQuery(query, params)
        except Exception as e:
            appLogger.error({
                "function": "insertActivityLogDetailed",
                "event": "DB_INSERT_ERROR",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "activity_name": activity_name,
                "socket_id": socket_id,
                "tenant_id": tenant_id,
                "user_id": user_id
            })
            
    @staticmethod            
    def fetchTangoStatesForUserIdKeyandSession(user_id, key, session_id):
        query = f"""
            SELECT * FROM tango_states 
            WHERE user_id = {user_id} 
            AND key = '{key}'
            and session_id = '{session_id}'
            ORDER BY created_date DESC
        """
        return db_instance.retrieveSQLQueryOld(query)
