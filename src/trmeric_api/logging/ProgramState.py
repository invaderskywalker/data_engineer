import threading

class ProgramState:
    """
    Manages program state variables for specific users.
    Each instance represents state for a single user.
    """
    # Class-level dictionary to store instances by user_id
    _instances = {}
    _lock = threading.Lock()
    
    @classmethod
    def get_all_instances(cls):
        """
        Returns a copy of all ProgramState instances.
        
        Returns:
            dict: A copy of the _instances dictionary
        """
        with cls._lock:
            return cls._instances.copy()
    
    @classmethod
    def get_instance(cls, user_id):
        """
        Returns or creates a ProgramState instance for the specified user_id.
        
        Args:
            user_id: The user ID to retrieve state for
            
        Returns:
            ProgramState instance for the user
        """
        with cls._lock:
            if user_id not in cls._instances:
                cls._instances[user_id] = cls(user_id)
            return cls._instances[user_id]
    
    @classmethod
    def has_instance(cls, user_id):
        """
        Check if a ProgramState instance exists for the specified user_id.
        
        Args:
            user_id: The user ID to check
            
        Returns:
            bool: True if instance exists, False otherwise
        """
        with cls._lock:
            return user_id in cls._instances
    
    @classmethod
    def destroy_instance(cls, user_id):
        """
        Removes the ProgramState instance for a specific user_id.
        
        Args:
            user_id: The user ID to destroy instance for
        """
        with cls._lock:
            if user_id in cls._instances:
                del cls._instances[user_id]
    
    def __init__(self, user_id):
        """
        Initialize a new ProgramState instance for a specific user.
        
        Args:
            user_id: The user ID to associate with this state instance
        """
        self.user_id = user_id
        self._state = {'session_ids': []}
    
    def set(self, key, value):
        """
        Sets a state variable for this user.
        
        Args:
            key (str): The key to set
            value: The value to set
        """
        if key == "session_id":
            if value not in self._state["session_ids"]:
                self._state["session_ids"].append(value)
        self._state[key] = value
    
    def get(self, key, default=None):
        """
        Gets a state variable for this user.
        
        Args:
            key (str): The key to get
            default: Default value if key is not found
            
        Returns:
            The value associated with the key, or default if not found
        """
        return self._state.get(key, default)
    
    def clear(self, key=None):
        """
        Clears a state variable or all state variables for this user.
        
        Args:
            key (str, optional): The specific key to clear. If None, clears all state.
        """
        if key is None:
            # Clear all state
            self._state = {}
        else:
            # Clear specific key
            if key in self._state:
                del self._state[key]
    
    def reset(self):
        """
        Resets all state for this user and destroys the instance.
        """
        self.clear()
        print(f"############################################## Resetting state for user {self.user_id} ##############################################")
        ProgramState.destroy_instance(self.user_id)
        
    def get_all(self):
        """
        Returns all state variables for this user.
        
        Returns:
            dict: All state variables
        """
        return self._state.copy()