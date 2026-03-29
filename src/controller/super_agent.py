from src.services.super_agent_v1.session_manager import AgentSessionManager
import traceback

class SuperAgentController:
    def __init__(self):
        self.session_manager = AgentSessionManager()

    def handle_super_agent(self, tenant_id, user_id, socketio, client_id, requestBody, session_id):
        try:
            print("--debug requestBody", tenant_id, user_id, client_id, session_id, requestBody)

            agent_name = requestBody.get("mode")
            message = requestBody.get("message", "")
            meta = requestBody.get("metadata")

            # ✅ Build metadata and get/create session handler
            metadata = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "session_id": session_id,
                "file_uploaded_info": meta
            }

            handler = self.session_manager.get_instance(
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                metadata=metadata,
                agent=agent_name,
                socketio=socketio,
                client_id=client_id,
            )

            # ✅ Now call handler logic
            handler.runner.run(agent_name, message, meta)

        except Exception as e:
            print("❌ Error in handle_general_agent_2:", e)
            traceback.print_exc()
            socketio.emit("general_agent_v2", {"status": "error", "error": str(e)}, room=client_id)

