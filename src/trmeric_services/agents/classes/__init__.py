from .utility_agent import UtilityAgent
from .portfolio_manangement_agent import PortfolioManagementAgent
from .onboarding_agent import OnboardingAgent
from .service_assurance_agent import ServiceAssuranceAgent
from .value_realization import ValueRealization
from .spend_agent import SpendAgent
from .service_assurance_troubleshoot_agent import ServiceAssuranceTroubleShootAgent
from .resource_planning_agent import ResourcePlanningAgent
from .analyst_v2 import Analyst
from .analyst import RoadmapAnalyst
from .customer_success_agent import CustomerSuccessAgent
from .integration_agent import IntegrationAgent
from .knowledge import KnowledgeAgent
from .project_creation_agent import ProjectCreationAgent
from .roadmap_agent import RoadmapAgent
from .businesscasetemplateagent import BusinessCaseTemplateAgent
from .quantum_agent import QuantumAgent
# from .roadmap_solution_agent import RoadmapSolutionAgent
from .potential_agent import PotentialAgent
from .onboarding_v2 import OnboardingV2
from .integration_agent import IntegrationAgent
from .ideation_agent import IdeationAgent


ALL_AGENTS = [
    PortfolioManagementAgent,
    # UtilityAgent,
    ServiceAssuranceAgent,
    OnboardingAgent,
    ValueRealization,
    SpendAgent,
    ServiceAssuranceTroubleShootAgent,
    ResourcePlanningAgent,
    RoadmapAnalyst,
    CustomerSuccessAgent,
    IntegrationAgent,
    KnowledgeAgent,
    ProjectCreationAgent,
    RoadmapAgent,
    BusinessCaseTemplateAgent,
    QuantumAgent,
    # RoadmapSolutionAgent,
    PotentialAgent,
    OnboardingV2,
    IntegrationAgent,
    IdeationAgent,
]


NORMAL_USE_AGENTS = [
    PortfolioManagementAgent,
    # UtilityAgent,
    ServiceAssuranceAgent,
    ValueRealization,
    ResourcePlanningAgent,
    # OnboardingAgent,
    SpendAgent,
    ServiceAssuranceTroubleShootAgent,
    RoadmapAnalyst,
    CustomerSuccessAgent,
    IntegrationAgent,
    KnowledgeAgent,
    ProjectCreationAgent,
    RoadmapAgent,
    BusinessCaseTemplateAgent,
    QuantumAgent,
    # RoadmapSolutionAgent,
    PotentialAgent,
    OnboardingV2,
    IntegrationAgent,
    IdeationAgent,
]
