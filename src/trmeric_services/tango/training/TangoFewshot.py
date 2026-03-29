class TangoFewshot:
    def __init__(
        self, query: str, prev: list, thought: str, functions_called: str, data_summary: str, output_format: str, integrations_used: list
    ):
        self.query = query
        self.prev = prev
        self.thought = thought
        self.functions_called = functions_called
        self.integrations_used = integrations_used
        self.data_summary = data_summary
        self.output_format = output_format

    def formatFewshotForCodeGeneration(self) -> str:
        """Formats the Tango fewshot in a human readable way.

        Returns:
            str: A formatted string.
        """
        response = ""
        for message in self.prev:
            response += 'User: ' + message['user'] + '\n'
            response += 'Data: ' + message['data'] + '\n'
            response += '\nTango: ' + message['tango'] + '\n'
        response += f"""
Question: {self.query}
Thought: {self.thought}
```
{self.functions_called}
```
    """
        return response
    