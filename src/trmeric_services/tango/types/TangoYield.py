class TangoYield:
    """
    The TangoYield class is responsible for yielding information to the user.
    """
    def __init__(self, return_info = "", yield_info = "", yield_now = ""):
        self.yield_info = yield_info
        self.return_info = return_info
        self.yield_now = yield_now
        
    def get_yield_info(self):
        """
        Returns the information that was yielded to the user.
        """
        return self.yield_info
    
    def get_return_info(self):
        """
        Returns the information that was returned to the user.
        """
        return self.return_info
    
    def get_yield_now(self):
        """
        Returns the information that was yielded to the user.
        """
        return self.yield_now