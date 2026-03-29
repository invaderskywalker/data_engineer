

class TrmericIntegration:
    """
    This is a class to represent the integration of Trmeric with other services.
    Some of them include Github, Jira, Google Docs, etc.
    
    For each function, we will store the appropriate integration, as well as whether that integatation has been enabled for the user or not.
    """
    def __init__(self, name: str):
        self.name = name


class TangoFunction:
    """
    This is a class to represent the building block functions to our very rudimentary language
    TCL (Tango Command Language).

    Attributes:
        name (str): The name of the function.
        description (str): A description of what the function does.
        args (list): A list of dictionaries where each dictionary contains the following keys:
            - name (str): The name of the argument.
            - type (str): The type of the argument.
            - description (str): A description of the argument.
            - options (list): A list of options to choose from for this parameter.
        return_description (str): A description of the return value of the function.
        function (callable): The function that the TangoFunction will actually call real-time
        func_type (str): The type of the function. This can be either "sql", "api", or "knowledge"
    """

    def __init__(
        self,
        name: str,
        description: str,
        args: list,
        return_description: str,
        function: callable,
        func_type: str,
        integration: TrmericIntegration,
        active: bool = False,
    ):
        self.name = name
        self.description = description
        self.args = args
        self.return_description = return_description
        self.function = function
        self.func_type = func_type
        self.integration = integration
        self.active = active

    def format_function(self):
        """
        Returns a string representation of the function that can be shown to the model
        """
        new_line = "\n"

        formatted = f'''
def {self.name}({", ".join([f"{arg['name']}: {arg['type']}" for arg in self.args])}):
    """{self.description}

    Args:
        {new_line.join([f"{arg['name']}: {arg['description']}. {'The options to choose from for this parameter (besides none) are: ' + ', '.join(arg['options']) if 'options' in arg else ''}" for arg in self.args])}

    Returns:
        {self.return_description}
    """
        '''
        return formatted


class ApiMetadata:

    def __init__(self, accessToken: str, refreshToken: str):
        self.accessToken = accessToken
        self.refreshToken = refreshToken