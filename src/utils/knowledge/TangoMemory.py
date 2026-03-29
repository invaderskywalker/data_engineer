import json
from src.trmeric_database.Redis import RedClient
from datetime import datetime, timedelta, timezone
from src.trmeric_database.Database import db_instance
from src.trmeric_utils.fuzzySearch import squeeze_text
from src.trmeric_database.dao import TangoDao, UsersDao
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_services.tango.sessions.TangoConversationRetriever import TangoConversationRetriever

INTENT_HINTS = {
    "Goal": "(directional focus – may influence prioritization and reflection)",
    "Worry": "(risk sensitivity – may influence framing and caution)",
    "Preference": "(interaction style – may influence tone and depth)",
    "Pain Point": "(friction area – may influence recommendations if relevant)",
    "Budget Constraint": "(hard constraint – internal only, do not surface)",
    "Timeline": "(urgency signal – internal unless strongly relevant)",
    "Technical Requirement": "(solution constraint – internal only)",
    "Business Value": "(outcome lens – may influence framing and reflection)",
    "Priority": "(ordering signal – internal only)",
    "User Feedback": "(quality signal – internal tuning only)",
    "User Company Role": "(perspective context – internal framing only)",
    "Frequently Asked Question": "(anticipatory guidance – internal only)",
}


class TangoMem:
    INSIGHT_TYPES = [
        "Goal", "Worry", "Preference", "Pain Point", "Budget Constraint", 
        "Timeline", "Technical Requirement", "Business Value", "Priority",
        "User Feedback", "User Company Role", "Frequently Asked Question",
    ]
    REFLECTION_ELIGIBLE_TYPES = {"Goal","Worry","Preference","Business Value",}
    
    def __init__(self, user_id, tenant_id=None):
        self.user_id = user_id
        self.tenant_id = tenant_id or UsersDao.fetchUserTenantID(user_id)
        self.llm = ChatGPTClient(user_id=self.user_id, tenant_id=self.tenant_id)
        self.loginDB = {
            "tenant_id" : self.tenant_id,
            "user_id" : self.user_id
        }
        self.modelOptions = ModelOptions(
            model="gpt-4o",
            max_tokens=8096,
            temperature=0
        )
        
        # Add the loginDB attribute for logging purposes
        self.loginDB = {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id
        }
        
    def get_user_conversation(self, N):
        """Retrieve user conversations with pagination support"""
        try:
            
            chats = TangoConversationRetriever.fetchLastNMessagesByUserID(
                self.user_id, N
            )
            if chats:
                conv = chats.format_conversation_simple()
                return conv
            return None
        except Exception as e:
            print(f"Error fetching user conversation: {str(e)}")
            return None

    def get_user_conversation_by_session(self, session_id):
        """Retrieve user conversations by session ID"""
        try:
            chats = TangoConversationRetriever.fetchMessagesByUserIDAndSessionID(
                self.user_id, session_id
            )
            if chats:
                conv = chats.format_conversation_simple()
                return conv
            return None
        except Exception as e:
            print(f"Error fetching user conversation by session: {str(e)}")
            return None


    def create_insights(self, N=None, session_id=None):
        """Create insights from user conversations"""
        try:
            if self.tenant_id is None:
                print("Tenant ID not provided - cannot create insights")
                raise Exception("Tenant ID not provided, needed to create insights")
            
            conv = None
            if N and not session_id:
                conv = self.get_user_conversation(N)
            elif session_id:
                conv = self.get_user_conversation_by_session(session_id)
            else:
                print("Neither N nor session_id provided - cannot fetch conversation")
                return None
                
            if not conv:
                print(f"No previous conversation found for user {self.user_id}")
                return None
        
            user_prompt = "Here are some of your chats with the user: \n\n" + conv
            
            response = self.llm.run(
                ChatCompletion(system=self.system_prompt(), prev=[], user=user_prompt),
                self.modelOptions,
                "create_insights_tango_memory",
                self.loginDB
            )

            parsed_json = extract_json_after_llm(response)
            
            # Validate and enrich insights
            if "insights" in parsed_json:
                for insight in parsed_json["insights"]:
                    # Ensure type is valid
                    if insight["type"] not in self.INSIGHT_TYPES:
                        insight["type"] = "General"

            current_message =TangoConversationRetriever.fetchLastMessageIDByUserID(self.user_id)
            TangoDao.upsertTangoState(self.tenant_id, self.user_id, "memory_message", current_message, "")
            print(f"Created {len(parsed_json['insights'])} insights for user {self.user_id}")
            return parsed_json
        except Exception as e:
            print(f"Error creating insights: {str(e)}")
            return {"insights": []}
    
    def _analyze_sentiment(self, text):
        """Simple sentiment analysis for insights - utility function not stored in DB"""
        # This could be enhanced with a real sentiment analysis API
        positive_words = ["increase", "improve", "enhance", "grow", "better", "success"]
        negative_words = ["reduce", "decrease", "cut", "loss", "problem", "issue", "worry"]
        
        text = text.lower()
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def compile_insights(self):
        """Retrieve existing insights from database"""
        try:
            query = f"""
                SELECT id, created_at, updated_at, description, type 
                FROM tango_memory 
                WHERE user_id = {self.user_id}
            """
            data = db_instance.retrieveSQLQueryOld(query)
            
            formatted_data = {"insights": []}
            
            if isinstance(data, list) and len(data) > 0:
                for row in data:
                    formatted_data["insights"].append({
                        "id": row['id'],
                        "created_at": row['created_at'],
                        "updated_at": row['updated_at'],
                        "description": row['description'],
                        "type": row['type']
                    })
                # print(f"Found {len(formatted_data['insights'])} insights in database")
            else:
                print(f"No insights found in database (got response: {type(data)}, value: {data})")
            
            return formatted_data
        except Exception as e:
            # If the exception is just '0', handle gracefully
            if str(e) == "0":
                print("No insights found (caught exception with value 0)")
                return {"insights": []}
            print(f"Error compiling insights: {str(e)}")
            return {"insights": []}

    def update_insights(self, N=None, session_id=None):
        """Update insights with smart reconciliation"""
        try:
            new_insights = self.create_insights(N=N, session_id=session_id)
            if not new_insights: 
                return None
            existing_data = self.compile_insights()
            
            user_prompt = f"Here are the insights that have been newly created by the system: \n\n {json.dumps(new_insights, indent=4)}"
            
            response = self.llm.run(
                ChatCompletion(system=self.system_prompt_reconcile(existing_data), prev=[], user=user_prompt),
                self.modelOptions,
                "reconcile_insights_tango_memory",
                self.loginDB
            )
            
            reconciled_insights = extract_json_after_llm(response)
            
            # Print reconciliation results
            # print(f"\n===== INSIGHTS AFTER RECONCILIATION =====")
            if "insights" in reconciled_insights and reconciled_insights["insights"]:
                for idx, insight in enumerate(reconciled_insights["insights"]):
                    print(f"{idx+1}. [{insight['type']}] {insight['description']}")
                
                # Calculate filtered out insights
                if "insights" in new_insights:
                    filtered_count = len(new_insights["insights"]) - len(reconciled_insights["insights"])
                    if filtered_count > 0:
                        print(f"\n{filtered_count} insights were filtered out during reconciliation")
            else:
                print("No insights remained after reconciliation")
            
            # Store the reconciled insights in the database
            self._store_insights_in_db(reconciled_insights)
            
            return reconciled_insights
        except Exception as e:
            if str(e) == "0":
                print("No insights found (caught exception with value 0 in update_insights)")
                return {"insights": []}
            print(f"Error updating insights: {str(e)}")
            return {"insights": []}
    
    def _store_insights_in_db(self, insights_data):
        """Store insights in the database - check for existing insights before inserting"""
        try:
            if "insights" not in insights_data or not insights_data["insights"]:
                # print("No insights to store")
                return
            existing_query = f"""
                SELECT description FROM tango_memory 
                WHERE user_id = {self.user_id}
            """
            print(f"Checking existing insights with query: {existing_query}")
            existing_data = db_instance.retrieveSQLQueryOld(existing_query)
            
            existing_descriptions = set()
            if isinstance(existing_data, list) and len(existing_data) > 0:
                for row in existing_data:
                    if isinstance(row, dict):
                        desc = row.get("description", "")
                    else:
                        try:
                            desc = row[0]
                        except Exception as ex:
                            print("Error extracting description from row:", ex)
                            desc = ""
                    if desc:
                        existing_descriptions.add(desc)
                print(f"Found {len(existing_descriptions)} existing descriptions in database")
            else:
                print(f"No existing descriptions found (got response: {type(existing_data)}, value: {existing_data})")
            
            # Track new insights added
            new_insights_count = 0
            stored_insights = []
            skipped_insights = []
                    
            for insight in insights_data["insights"]:
                # Only insert if the description doesn't already exist
                if insight["description"] not in existing_descriptions:
                    current_time = datetime.now().isoformat()
                    
                    # Insert new insight
                    insert_query = """
                        INSERT INTO tango_memory (created_at, updated_at, description, type, user_id)
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    insert_params = (current_time, current_time, insight["description"], insight["type"], self.user_id)
                    
                    try:
                        result = db_instance.executeSQLQuery(insert_query, insert_params)
                        print(f"Insert result: {result}")
                        
                        # Add to our set to prevent duplicates within this batch
                        existing_descriptions.add(insight["description"])
                        new_insights_count += 1
                        stored_insights.append(insight)
                    except Exception as insert_error:
                        print(f"Error inserting insight: {str(insert_error)}")
                else:
                    skipped_insights.append(insight)
            
            # Print stored insights
            print(f"\n===== INSIGHTS STORED IN DATABASE =====")
            if new_insights_count > 0:
                for idx, insight in enumerate(stored_insights):
                    print(f"{idx+1}. [{insight['type']}] {insight['description']}")
                print(f"\nSuccessfully stored {new_insights_count} new insights for user {self.user_id}")
            else:
                print("No new insights were stored (all already existed in database)")
                
            if skipped_insights:
                print(f"\n===== INSIGHTS SKIPPED (ALREADY EXIST) =====")
                for idx, insight in enumerate(skipped_insights):
                    print(f"{idx+1}. [{insight['type']}] {insight['description']}")
                
        except Exception as e:
            print(f"Error storing insights in database: {str(e)}")
            import traceback
            print(traceback.format_exc())
    
    def get_insights_by_type(self, insight_type):
        """Get insights by type"""
        try:
            escaped_type = insight_type.replace("'", "''")
            query = f"""
                SELECT id, created_at, updated_at, description, type 
                FROM tango_memory 
                WHERE user_id = {self.user_id} AND type = '{escaped_type}'
            """
            data = db_instance.retrieveSQLQueryOld(query)
            
            # Handle case where data is 0 or None
            if data is None or data == 0:
                return {"insights": []}
            
            formatted_data = {"insights": []}
            for row in data:
                formatted_data["insights"].append({
                    "id": row['id'],
                    "created_at": row['created_at'],
                    "updated_at": row['updated_at'],
                    "description": row['description'],
                    "type": row['type']
                })
            
            return formatted_data
        except Exception as e:
            print(f"Error getting insights by type: {str(e)}")
            return {"insights": []}
    
    def get_insights_with_sentiment(self, sentiment=None):
        """Get insights with calculated sentiment (not stored in DB)"""
        try:
            # Get all insights for this user
            query = f"""
                SELECT id, created_at, updated_at, description, type 
                FROM tango_memory 
                WHERE user_id = {self.user_id}
            """
            data = db_instance.retrieveSQLQueryOld(query)
            
            # Handle case where data is 0 or None
            if data is None or data == 0:
                return {"insights": []}
            
            # Filter insights by analyzing the sentiment of each description if sentiment is provided
            formatted_data = {"insights": []}
            for row in data:
                description = row[3]
                calculated_sentiment = self._analyze_sentiment(description)
                
                insight = {
                    "id": row['id'],
                    "created_at": row['created_at'],
                    "updated_at": row['updated_at'],
                    "description": row['description'],
                    "type": row['type'],
                    "calculated_sentiment": calculated_sentiment  # Added as an extra field, not stored in DB
                }
                
                if sentiment is None or calculated_sentiment == sentiment:
                    formatted_data["insights"].append(insight)
            
            return formatted_data
        except Exception as e:
            print(f"Error getting insights with sentiment: {str(e)}")
            return {"insights": []}
    
    def get_insights(self,limit=5):
        """Get all insights for this user without any filtering"""
        try:
            query = f"""
                SELECT id, created_at, description, type 
                FROM tango_memory 
                WHERE user_id = {self.user_id}
                ORDER BY created_at DESC
                LIMIT {limit}
            """
            data = db_instance.retrieveSQLQueryOld(query)
            
            
            # Better handling of database response
            formatted_data = []
            
            if isinstance(data, list) and len(data) > 0:
                for row in data:
                    formatted_data.append({
                        "id": row['id'],
                        "created_at": row['created_at'],
                        # "updated_at": row['updated_at'],
                        "description": row['description'],
                        "type": row['type']
                    })
            else:
                return "No Tango Memory found for this user"
            
            return formatted_data
        except Exception as e:
            print(f"Error getting insights: {str(e)}")
            return []
        
    def refresh_memory(self, n):
        """Check if there are any insights for this user"""
        memory_messages = TangoDao.fetchTangoStatesForUserIdbyKey(self.user_id, "memory_message")
        if not memory_messages:
            print("No memory messages found")
            self.update_insights(N=n)
            return
        last_update = int(memory_messages[0].get("value", ""))
        val =  TangoConversationRetriever.CheckLastNmessagesByUserID(self.user_id, n*2, last_update)
        if val < 0:
            print("Updating Tango Memory")
            self.update_insights(N=n)
        else:
            value = float(((val - 1) /2))/ n * 100
            print(f"Refresh not needed yet, {value}% of the way")

    def refresh_memory_session(self, socket_id):
        """Check if there are any insights for this user"""
        self.update_insights(session_id=socket_id)
        return

    
    def system_prompt(self):
        """System prompt for creating insights"""
        return """You are an assistant for a B2B SaaS company called Trmeric. Trmeric has an assistant called Tango that provides services to companies.
Other companies use Tango to help them with their projects, roadmaps, initiatives, and actions. Your task is to carefully analyze these conversations.
Your job will be to pick out any interesting insights from conversations with users that may be useful in the future. Try to see if the user or tango mentions any general trends.

Be strategic in extracting insights that would help Trmeric better serve this user in the future. Look for:

1. Business goals and objectives
2. Pain points and challenges
3. Budget constraints and concerns
4. Timeline expectations
5. Technical requirements
6. Team structure and dynamics
7. Decision-making processes
8. Success metrics and KPIs
9. Industry-specific concerns

Do not force yourself to create insights always, be restrictive and only create insights when you see a clear trend or pattern that may be useful in the future.

Return your insights in a json format, categorizing them appropriately:

```json
{
    "insights": [
        {
            "type": "Goal",
            "description": "User is trying to increase employee productivity by 15% in Q3"
        },
        {
            "type": "Worry", 
            "description": "User is concerned about regulatory compliance in their new market expansion"
        },
        {
            "type": "Budget Constraint",
            "description": "User has mentioned a software budget cap of $50K for the year"
        },
        {
            "type": "Technical Requirement",
            "description": "User needs SSO integration with their existing Okta implementation"
        }
    ]
}
```

Possible insight types are Goal, Worry, Preference, Pain Point, Budget Constraint, Timeline, Technical Requirement, Business Value, Priority.

If you are unable to find any insights, please return an empty list.
        """
        
    def system_prompt_reconcile(self, data):
        """System prompt for reconciling insights"""
        prompt = f"""
            You are an assistant for a B2B SaaS company called Trmeric. Trmeric has an assistant called Tango that provides services to companies.
            Your task is to look at the insights that have been newly created by the system and compare them against the already existing insights.
            You will then filter out the new insights and modify them as needed to align with the existing insights.

            IMPORTANT INSTRUCTIONS:
            1. Remove exact duplicates completely
            2. Combine similar insights that express the same underlying need or concern
            3. Preserve the most detailed or specific version when combining insights
            4. Keep all genuinely new insights that don't overlap with existing ones
            5. Prioritize insights that are more strategic and actionable
            6. Ensure proper categorization of each insight based on its content

            Here are the existing insights:
            {json.dumps(data, indent=4)}

            You will return the filtered/reconciled insights in its maintained json format:

            ```json
            {{
                "insights": [
                    {{
                        "type": "Goal",
                        "description": "User is trying to increase employee productivity by 15% in Q3"
                    }},
                    {{
                        "type": "Worry",
                        "description": "User is concerned about regulatory compliance in their new market expansion"
                    }},
                    {{
                        "type": "Budget Constraint",
                        "description": "User has mentioned a software budget cap of $50K for the year"
                    }}
                ]
            }}
            ```

            If there are no new insights to add after reconciliation, you may return an empty list.
        """
        return prompt


    def tango_memory_insights_for_rl(self, last_days=5):

        # 1. Fetch only last 5 days insights from raw insights
        # 2. Prepare a nice structure for the reinforcement of tango in the user prompt as e.g. or more feedback
        # 3. Group the description by type

        raw_insights = RedClient.execute(query=lambda: self.get_insights(limit=7),key_set=f"tangoMem::userId::{self.user_id}",expire=86400)
        # print("--debug raw_insights------------", raw_insights[:3])
        cutoff = datetime.now(timezone.utc) - timedelta(days=last_days)
        filtered_insights = []

        for insight in raw_insights:
            try:
                ts = datetime.fromisoformat(insight['created_at'])
                if ts >= cutoff:
                    filtered_insights.append(insight)
            except Exception as e:
                print("Datetime error:", e, insight)

        print("--debug filtered_insights: ", filtered_insights)
        grouped_insights = {}
        for insight in filtered_insights:
            insight_type = insight.get('type', None) or None
            if not insight_type:
                continue
            if insight_type not in grouped_insights:
                grouped_insights[insight_type] = []
            description = insight.get('description', '')
            description = (description.replace("User is", "").replace("User has", "").strip().capitalize()) if description else description
            grouped_insights[insight_type].append(description)

        # Format into a structured string for prompt embedding
        eligible_types_str = ", ".join(self.REFLECTION_ELIGIBLE_TYPES)
        prompt_structure = (
            "The following are recent user context signals derived from prior interactions. Use them to guide prioritization, framing, and tone.\n"
            f"Only {eligible_types_str} may influence a single, high-level reflective line at the end."
            "All other insights are internal-only and must not be surfaced.\n"
        )

        for insight_type in self.INSIGHT_TYPES:  # Order by predefined types
            if insight_type in grouped_insights:
                prompt_structure += f"{insight_type} {INTENT_HINTS.get(insight_type, '') or ''}:\n"
                for desc in grouped_insights[insight_type]:
                    prompt_structure += f"- {desc}\n"
                prompt_structure += "\n"
            
        memory_prompt = squeeze_text(content=prompt_structure)
        # print("\n---debug tango_memory_insights---------", memory_prompt)
        return memory_prompt