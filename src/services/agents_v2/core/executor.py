

from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.trmeric_api.logging.AppLogger import appLogger

# Constants
MAX_WORKERS = 4

class Executor:
    """Executes data sources, actions, and sub-agents based on the query plan."""
    def __init__(self, data_sources: Dict, actions: Dict, socket_sender):
        self.data_sources = data_sources
        self.actions = actions
        self.socket_sender = socket_sender
        self.results = {"action_results": []}

    def execute_plan(self, plan: Dict):
        """Executes the plan by running data sources, actions, and sub-agents."""
        

        self.results = {"action_results": []}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Run data sources
            source_futures = {
                executor.submit(self.run_data_source, name, plan["data_source_params"].get(name, {})): name
                for name in plan["data_sources_to_trigger"]
            }
            for future in as_completed(source_futures):
                name = source_futures[future]
                try:
                    self.results[name] = future.result()
                    self.socket_sender.sendSteps(f"Retrieving {name.replace('_', ' ').title()} Data", True)
                except Exception as e:
                    return f"Error processing {name}: {str(e)}"

            # Run actions
            for action in plan["actions_to_trigger"]:
                self.socket_sender.sendSteps(f"Executing action {action.replace('_', ' ').title()}", False)
                params = plan["action_params"].get(action, {})
                try:
                    self.results["action_results"].append(self.actions[action](**params))
                    self.socket_sender.sendSteps(f"Executing action {action.replace('_', ' ').title()}", True)
                except Exception as e:
                    return f"Error executing {action}: {str(e)}"

            # # Run sub-agents
            # agent_futures = {
            #     executor.submit(self.run_agent, sub_agents[name], plan.get(f"{name}_query", ""), {}): name
            #     for name in plan["agents_to_trigger"] if name in sub_agents
            # }
            # for future in as_completed(agent_futures):
            #     name = agent_futures[future]
            #     try:
            #         self.results[name] = list(future.result())
            #         self.socket_sender.sendSteps(f"📊 Retrieving {name.title()} Data", True)
            #     except Exception as e:
            #         return f"Error processing {name} agent: {str(e)}"


    def run_data_source(self, source_name: str, params: Dict) -> Dict:
        """Executes a data source function with given parameters."""
        from src.trmeric_api.logging.AppLogger import debugLogger
        debugLogger.info({"function": "run_data_source", "source_name": source_name, "params": params})
        try:
            source = self.data_sources.get(source_name)
            if not source:
                raise ValueError(f"Data source {source_name} not found")
            return source(**params)
        except Exception as e:
            appLogger.error({"function": "run_data_source_error", "source_name": source_name, "error": str(e)})
            raise

    def run_agent(self, agent, query: str, filters: Dict) -> List[str]:
        """Runs a sub-agent with the given query and filters."""
        try:
            return list(agent.process_query(query=query, filters=filters))
        except Exception as e:
            appLogger.error({"function": "run_agent_error", "agent_type": agent.__class__.__name__, "error": str(e)})
            raise
        
        