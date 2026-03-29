from src.api.logging.AppLogger import appLogger
import traceback
from src.database.Redis import RedClient


class ContextBuilder:
    """Builds enterprise context using automated research and user inputs."""

    def __init__(self, tenant_id: int, user_id: int, session_id=None):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_id = session_id or None

    def build_context(self, agent_name: str) -> str:
        """Builds context string from company info, social media, industry trends, etc."""
        from datetime import datetime, timedelta, timezone
        ist_time = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
        print("Incoming build_context (IST):", ist_time.strftime("%Y-%m-%d %H:%M:%S.%f"))
        print("building context -- ", agent_name)

        # ✅ Create Redis cache key
        cache_key = RedClient.create_key([
            "context_agent",
            # agent_name,
            str(self.tenant_id),
            str(self.user_id)
        ])

        # ✅ Define builder function (excluding `current_session_uploaded_files`)
        def _build_context():
            print(f"🔄 Building fresh context for {cache_key}")
            context = []
            context_sections = []
            try:
                context_sections = [
                    # "org_role_user",
                    # "info_about_user",
                    # # "accessible_portfolios",
                    # "company_basic_info",
                    # "company_industry_info",
                    # "company_enterprise_info",
                    # "company_competitors_info",
                    # "company_enterprise_strategies",
                    # "integration_info_string",
                    # "project_and_roadmap_context_string",
                    # "program_list",
                    # "providers_list"
                ]

                # Loop over sections and fetch data
                for section in context_sections:
                    data_text = ""
                    if data_text:
                        context.append(f"=== {section} ===\n{data_text}")
                        
                print(f"🔄 Building fresh context done for {cache_key}")

                return "\n-----\n".join(context) if context else "No context available."

            except Exception as e:
                appLogger.error({
                    "function": "ContextBuilder.build_context_error",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "tenant_id": self.tenant_id
                })
                return f"Error building context: {str(e)}"

        cached_context = RedClient.execute(_build_context, cache_key, expire=300)
        fresh_files_section = ""

        # ✅ Append fresh section at end
        if fresh_files_section:
            cached_context += f"\n-----\n=== current_session_uploaded_files ===\n{fresh_files_section}"


        print("done fetching context -- ")
        return cached_context

