

from src.trmeric_services.agents.core.agent_functions import AgentFunction

def format_data_for_graph(
    data_for_graph: str,
    tenantID: int,
    userID: int,
    **kwargs
):
    prompt = """
    
        Job of graph agent:
        To only output data in the format wheich client accepts
        the format which is a cceptable by client is given below:
        
        Formats to send data for graph.
        
        The output of your chart should be in the following format:
        ```json
        {{
            chart_type: 'Gaant' or 'Bar' or 'Line' or etc,
            format: <format>
        }}
        ```
        Gaant Chart have the following format:
        
        <format>: {{
            data:  [ 
                {{
                    x: <x_axis_name>, // string
                    y: ['date_string_begin', 'date_string_end']
                }}
            ]
        }}
        
        For Line Charts, they have the following format:

        <format> - [
            {{
                name: <name_of_param>,// string
                data: [<values_of_data>, ...],
                categories: [<categories>, ...]
            }},
            ... if more params they want for bar chart
        ]

        For Bar Chart type (the data points and categories should be of same length) - this is the applicable format <format>:
                                
        <format> - [
            {{
                name: <name_of_param>,// string
                data: [<values_of_data>, ...],
                categories: [<categories>, ...]
            }},
            ... if more params they want for bar chart
        ]

        For Donut/Gauge Chart type - this is the applicable format <format>:
        <format> - [
            {{
                data: [<values_of_data>, ...],
                categories: [<categories>, ...]
            }}
        ]
                
            
        Example -    



        ```
        {
            chart_type: 'Gaant',
            format: {
                title: "portfolio1",
                data: [
                    {
                        x: 'Project 1',
                        y: ['start_date', 'end_date']
                    },
                    ...
                ]
            }
        }
        ```


    """
    return prompt


RETURN_DESCRIPTION = """
    A data set is provided and a thought is provided.
"""

ARGUMENTS = [
    {
        "name": "data_for_graph",
        "type": "str",
        "description": "The data to be passed from previous agent(s)",
        "required": "true",
        "use_placeholder": "true"
    },
]


FORMAT_DATA_FOR_GRAPH = AgentFunction(
    name="format_data_for_graph",
    description="""
        This is responsible for formating the data provided for various visualizations based on portfolio, project details like spend, health etc.
        It supports data preparation for bar charts, line graphs, scatter plots, and other graph types.
    """,
    args=ARGUMENTS,
    return_description=RETURN_DESCRIPTION,
    function=format_data_for_graph,
)
