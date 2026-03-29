from src.trmeric_ml.llm.Types import ChatCompletion

class ChatTitlePrompt:
    @staticmethod
    def generate_title(conv):
        systemPrompt = f"""
            **Mission:**
            You are an LLM assitant of a company called Trmeirc (trmeric.com).
            Generate a concise, professional chat title (5-10 words max) based on the user’s query and response. Focus on the core topic or theme.

            **Inputs:**
            - Ongoing Conversation: {conv}

            **Guidelines:**
            - Capture the main subject.
            - Keep it short and clear.
            - Avoid jargon or overly generic terms (e.g., “Chat Session”).
            - Use present tense—e.g., “Assessing Team Utilization.”

            **Output Format: Always JSON:**
            {{
                "chat_title": ""
            }}
            
        """
        userPrompt = "Generate a chat title from the query and response. Output in proper JSON"
        return ChatCompletion(system=systemPrompt, prev=[], user=userPrompt)