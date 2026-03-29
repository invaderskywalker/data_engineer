
from src.trmeric_services.agents.core import BaseAgent
class AgentRegistry:
    def __init__(self):
        self.agents = {}

    def register_agent(self, agent_class):
        """
        Registers an agent and its functions with descriptions.
        """
        if not hasattr(agent_class, 'name'):
            raise ValueError(f"Agent class '{agent_class.__name__}' must have a 'name' attribute.")
        self.agents[agent_class.name] = agent_class
        

    def get_agent(self, agent_name: str) -> BaseAgent:
        """
        Retrieves the agent by name.
        """
        return self.agents.get(agent_name)

    def refresh_agents(self, sessionID):
        """
        Refreshes the agents.
        """
        for agent_key, agent in self.agents.items():
            if hasattr(agent, 'refresh_functions'):
                self.agents[agent_key] = agent.refresh_functions(agent, sessionID)
                print("refreshed agent: ", self.agents[agent_key])

    def get_all_agents(self, sessionID = None):
        """
        Retrieves a list of all registered agents.
        """
        if sessionID:
            self.refresh_agents(sessionID)
        return self.agents
    
