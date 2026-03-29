
class ActiveUserSocketMap:
    # user_id -> set(client_ids)
    _user_to_clients = {}

    @staticmethod
    def add(user_id: str, client_id: str):
        if user_id not in ActiveUserSocketMap._user_to_clients:
            ActiveUserSocketMap._user_to_clients[user_id] = set()
        ActiveUserSocketMap._user_to_clients[user_id].add(client_id)

    @staticmethod
    def remove(user_id: str, client_id: str):
        if user_id in ActiveUserSocketMap._user_to_clients:
            ActiveUserSocketMap._user_to_clients[user_id].discard(client_id)
            if not ActiveUserSocketMap._user_to_clients[user_id]:
                del ActiveUserSocketMap._user_to_clients[user_id]

    @staticmethod
    def get_all(user_id: str) -> list[str]:
        return list(ActiveUserSocketMap._user_to_clients.get(user_id, []))

    @staticmethod
    def get_latest(user_id: str) -> str | None:
        clients = ActiveUserSocketMap._user_to_clients.get(user_id)
        if clients:
            return list(clients)[-1]  # last added (approx latest)
        return None

    @staticmethod
    def debug():
        return {
            user: list(clients)
            for user, clients in ActiveUserSocketMap._user_to_clients.items()
        }
    
class UserSocketMap:
    # Static dictionary to store user_id to client_id mapping
    _user_to_client = {}

    @staticmethod
    def add_mapping(user_id: str, client_id: str) -> None:
        """Add or update a user_id to client_id mapping."""
        UserSocketMap._user_to_client[user_id] = client_id

    @staticmethod
    def get_client_id(user_id: str) -> str | None:
        """Get client_id for a given user_id."""
        return UserSocketMap._user_to_client.get(user_id)

    @staticmethod
    def remove_mapping(user_id: str) -> None:
        """Remove a user_id to client_id mapping."""
        UserSocketMap._user_to_client.pop(user_id, None)

    @staticmethod
    def get_all_mappings() -> dict:
        """Get all user_id to client_id mappings."""
        return UserSocketMap._user_to_client.copy()

    @staticmethod
    def clear_mappings() -> None:
        """Clear all mappings."""
        UserSocketMap._user_to_client.clear()
        
        
class TangoBreakMapUser:
    _user_to_break = {}
    
    @staticmethod
    def add_counter(user_id: str) -> None:
        if user_id not in TangoBreakMapUser._user_to_break:
            TangoBreakMapUser._user_to_break[user_id] = 0
        TangoBreakMapUser._user_to_break[user_id] += 1

    @staticmethod
    def get_counter(user_id: str) -> str | None:
        return TangoBreakMapUser._user_to_break.get(user_id)

    @staticmethod
    def reset_count(user_id: str) -> None:
        TangoBreakMapUser._user_to_break.pop(user_id, None)
        
    