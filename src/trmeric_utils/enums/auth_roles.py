
from enum import Enum

class AuthRoles(Enum):
    ORG_ADMIN = "org_admin"
    ORG_LEADER = "org_leader"
    PORTFOLIO_LEADER = "org_portfolio_leader"
    ORG_PROJECT_MANAGER = "org_project_manager"
    ORG_MEMBER = "org_member"
    ORG_DEMAND_REQUESTOR = "org_demand_requestor"
    ORG_DEMAND_MANAGER = "org_demand_manager"

    ORG_RESOURCE_MANAGER = "org_resource_manager"
    ORG_SOLUTION_LEADER = "org_solution_leader"
    ORG_SPONSOR_APPROVER = "org_sponsor_approver"
    ORG_ONLY_DISCOVERY = "org_only_discovery"
    EXTERNAL_CUSTOMER = "external_customer"
    PROVIDER_ORG_ADMIN = "provider_org_admin"

    @classmethod
    def has_role(cls, role):
        return role in cls._value2member_map_


ALL_ROLES = [
    AuthRoles.ORG_ADMIN.name,
    AuthRoles.ORG_LEADER.name,
    AuthRoles.PORTFOLIO_LEADER.name,
    AuthRoles.ORG_PROJECT_MANAGER.name,
    AuthRoles.ORG_MEMBER.name,
    AuthRoles.ORG_DEMAND_REQUESTOR.name,
    AuthRoles.ORG_DEMAND_MANAGER.name,
    AuthRoles.ORG_RESOURCE_MANAGER.name,
    AuthRoles.ORG_SOLUTION_LEADER.name,
    AuthRoles.ORG_SPONSOR_APPROVER.name,
    AuthRoles.ORG_ONLY_DISCOVERY.name,
    AuthRoles.EXTERNAL_CUSTOMER.name,
    AuthRoles.PROVIDER_ORG_ADMIN.name,
]
