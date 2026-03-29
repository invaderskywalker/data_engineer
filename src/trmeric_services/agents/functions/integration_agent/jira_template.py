from typing import List, Dict

JIRA_MANAGEMENT_METHODS: List[Dict[str, any]] = [
    {
        "id": "standard_agile",
        "name": "Standard Agile Hierarchy",
        "description": "A Jira project represents a major initiative, with epics grouping related work and issues (stories, tasks, bugs) as the smallest units.",
        "hierarchy": ["Project", "Epic", "Issue"],
        "use_case": "Software development teams using Scrum or Kanban, where epics represent features or sprints, and issues are tasks.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project returns multiple projects",
            "epics": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20issuetype=Epic returns multiple epics per project",
            "issues": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=\"Epic%20Link\"=<epicKey> shows issues linked to epics",
            "notes": "Check for 'Epic Link' field (customfield_XXXX) via GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/field"
        },
        "questions_to_ask": [
            "Do you use Jira projects for major initiatives, with epics for features and issues for tasks?",
            "Should each epic in a project become a project in our platform, or should the Jira project be one project?"
        ]
    },
    {
        "id": "epics_as_projects",
        "name": "Epics as Projects",
        "description": "One Jira project contains all work, with epics treated as the main 'projects' and issues as tasks within them.",
        "hierarchy": ["Project", "Epic", "Issue"],
        "use_case": "Small teams or centralized workflows where epics represent distinct initiatives within a single project.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project returns one or few projects",
            "epics": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20issuetype=Epic returns many epics",
            "issues": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=\"Epic%20Link\"=<epicKey> shows issues linked to epics",
            "notes": "High epic-to-issue ratio; check 'Epic Link' via GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/field"
        },
        "questions_to_ask": [
            "Do you treat epics in your Jira project as separate projects (e.g., 'Mobile App' as a project)?",
            "Should each epic become a project in our platform, or should the Jira project be one project with epics as tasks?"
        ]
    },
    {
        "id": "issues_as_projects",
        "name": "Issues as Projects",
        "description": "Individual issues represent 'projects,' often grouped by epics, labels, or custom fields within a Jira project.",
        "hierarchy": ["Project", "Issue"],
        "use_case": "Non-Agile teams where each issue is a significant deliverable, like marketing campaigns or events.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project returns one or few projects",
            "epics": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20issuetype=Epic returns few or no epics",
            "issues": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20\"Epic%20Link\"%20is%20EMPTY shows standalone issues",
            "notes": "Check labels or custom fields via GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/field"
        },
        "questions_to_ask": [
            "Do you treat individual issues, like campaigns or tasks, as your main projects in Jira?",
            "How do you group these issues (e.g., by epics, labels, or a custom field like 'Campaign Type')?"
        ]
    },
    {
        "id": "flat_structure",
        "name": "Flat Structure (No Epics)",
        "description": "A Jira project contains issues without epics, organized by labels, components, or custom fields.",
        "hierarchy": ["Project", "Issue"],
        "use_case": "Support or IT operations teams where epics are unnecessary, and issues are grouped dynamically.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project returns projects",
            "epics": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20issuetype=Epic returns empty",
            "issues": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key> shows issues with labels or components",
            "notes": "Check components via GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project/<key>/components; custom fields via GET /field"
        },
        "questions_to_ask": [
            "Do you organize work in Jira without epics, using issues grouped by labels or components?",
            "Should issues be projects in our platform, or grouped by something like labels or components?"
        ]
    },
    {
        "id": "multiple_projects",
        "name": "Multiple Projects as Initiatives",
        "description": "Each Jira project represents a distinct initiative, product, or team, with its own epics and issues.",
        "hierarchy": ["Project", "Epic", "Issue"],
        "use_case": "Large organizations with multiple products or teams needing separate workflows.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project returns several projects",
            "epics": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20issuetype=Epic shows epics per project",
            "issues": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=\"Epic%20Link\"=<epicKey> shows linked issues",
            "notes": "Check project types via GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project/<key>"
        },
        "questions_to_ask": [
            "Do you use separate Jira projects for different initiatives, like 'Web App' and 'Mobile App'?",
            "Should each Jira project become a project in our platform, or only specific ones?"
        ]
    },
    {
        "id": "cross_project_epics",
        "name": "Cross-Project Epics",
        "description": "Epics in one project link to issues in other projects, creating a shared hierarchy.",
        "hierarchy": ["Epic (in one project)", "Issue (in other projects)"],
        "use_case": "Organizations with shared goals across teams, where epics represent cross-team initiatives.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project returns multiple projects",
            "epics": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=\"Epic%20Link\"=<epicKey>%20AND%20project!=<epicProjectKey> shows issues from other projects",
            "issues": "Issues with 'Epic Link' pointing to another project’s epic",
            "notes": "Use JQL to detect cross-project 'Epic Link' relationships"
        },
        "questions_to_ask": [
            "Do you have epics in one project that link to issues in other projects?",
            "Should each cross-project epic be a project in our platform, or group them differently?"
        ]
    },
    {
        "id": "team_managed",
        "name": "Team-Managed Projects",
        "description": "Simplified projects with 'Parent' fields instead of 'Epic Link,' used by small or non-technical teams.",
        "hierarchy": ["Project", "Epic", "Issue"],
        "use_case": "Marketing, HR, or small teams needing lightweight Agile boards.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project/<key> shows 'style': 'next-gen'",
            "epics": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20issuetype=Epic",
            "issues": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20parent=<epicKey> shows issues linked via 'Parent'",
            "notes": "Check for 'Parent' field via GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/field"
        },
        "questions_to_ask": [
            "Do you use team-managed Jira projects with epics and issues, like for marketing campaigns?",
            "Should each epic in your team-managed project be a project in our platform?"
        ]
    },
    {
        "id": "custom_issue_types",
        "name": "Custom Issue Types as Primary Units",
        "description": "Custom issue types (e.g., 'Feature', 'Campaign') represent main units, replacing or supplementing standard types.",
        "hierarchy": ["Project", "Custom Issue Type", "Issue"],
        "use_case": "Industries with specific needs, like ITIL for IT or marketing for campaigns.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project returns projects",
            "custom_issue_types": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/issue/createmeta shows non-standard issue types (e.g., 'Feature')",
            "issues": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20issuetype=<customType>",
            "notes": "Verify custom issue types in createmeta response"
        },
        "questions_to_ask": [
            "Do you use custom issue types, like 'Feature' or 'Campaign,' as your main units in Jira?",
            "Should each custom issue type instance be a project in our platform?"
        ]
    },
    {
        "id": "custom_fields",
        "name": "Custom Fields for Grouping",
        "description": "Custom fields (e.g., 'Department', 'Client') group issues or epics, defining projects or categories.",
        "hierarchy": ["Project", "Issue (grouped by custom field)"],
        "use_case": "Organizations needing flexible categorization without multiple projects.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project returns projects",
            "custom_fields": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/field shows custom fields (e.g., 'Department')",
            "issues": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20customfield_XXXX=<value>",
            "notes": "Include custom fields in search via fields=customfield_*"
        },
        "questions_to_ask": [
            "Do you group work in Jira using custom fields, like 'Department' or 'Client'?",
            "Should we create projects in our platform based on custom field values, like 'Marketing'?"
        ]
    },
    {
        "id": "advanced_hierarchies",
        "name": "Advanced Hierarchies (Initiatives)",
        "description": "Higher-level hierarchies with initiatives or portfolios above epics, using apps like Advanced Roadmaps.",
        "hierarchy": ["Initiative", "Epic", "Issue"],
        "use_case": "Large enterprises managing complex programs across teams.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project returns projects",
            "custom_issue_types": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/issue/createmeta shows initiative-like issue types",
            "issues": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20issuetype=<initiativeType>",
            "notes": "May require app-specific APIs; approximate with custom issue types"
        },
        "questions_to_ask": [
            "Do you use initiatives or portfolios above epics, possibly with tools like Advanced Roadmaps?",
            "Should each initiative or epic be a project in our platform?"
        ]
    },
    {
        "id": "subtasks",
        "name": "Subtasks for Granular Work",
        "description": "Issues have subtasks to break down work, creating a deeper hierarchy within projects or epics.",
        "hierarchy": ["Project", "Epic", "Issue", "Subtask"],
        "use_case": "Teams needing detailed task breakdowns, like development or QA.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project returns projects",
            "issues": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20issuetype!=Sub-task shows parent issues",
            "subtasks": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=parent=<issueKey> shows subtasks",
            "notes": "Check 'subtasks' field in issue response"
        },
        "questions_to_ask": [
            "Do you use subtasks to break down larger issues in Jira?",
            "Should subtasks be included as tasks in our platform projects, or only parent issues?"
        ]
    },
    {
        "id": "components",
        "name": "Component-Based Organization",
        "description": "Projects use components (e.g., 'Database', 'UI') to group issues, instead of or alongside epics.",
        "hierarchy": ["Project", "Component", "Issue"],
        "use_case": "Teams managing modular systems where components reflect architecture or responsibility.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project returns projects",
            "components": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project/<key>/components returns components",
            "issues": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20component=<componentName>",
            "notes": "Check component assignments in issues"
        },
        "questions_to_ask": [
            "Do you group issues in Jira by components, like 'Database' or 'Frontend'?",
            "Should each component be a project in our platform, or group issues differently?"
        ]
    },
    {
        "id": "labels",
        "name": "Labels for Ad-Hoc Grouping",
        "description": "Issues are tagged with labels to create flexible, non-hierarchical groupings, often across projects.",
        "hierarchy": ["Project", "Issue (grouped by labels)"],
        "use_case": "Dynamic workflows where rigid hierarchies are impractical.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project returns projects",
            "issues": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20labels=<label>",
            "labels": "Check 'labels' field in issue response",
            "notes": "Identify common labels across issues"
        },
        "questions_to_ask": [
            "Do you use labels, like 'urgent' or 'feature,' to group issues in Jira?",
            "Should we create projects in our platform based on specific labels?"
        ]
    },
    {
        "id": "portfolio_management",
        "name": "Portfolio or Program Management",
        "description": "Jira projects represent programs or portfolios, with issues or epics as projects, often using apps.",
        "hierarchy": ["Project", "Epic/Issue"],
        "use_case": "Executives or PMOs tracking high-level initiatives across teams.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project returns projects",
            "epics": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key>%20AND%20issuetype=Epic shows high-level epics",
            "issues": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=\"Epic%20Link\"=<epicKey>",
            "notes": "Check for app-specific issue types or fields"
        },
        "questions_to_ask": [
            "Do you use Jira projects to manage programs or portfolios, with epics or issues as projects?",
            "Should each program or epic be a project in our platform?"
        ]
    },
    {
        "id": "hybrid_non_standard",
        "name": "Hybrid or Non-Standard Setups",
        "description": "Custom combinations of projects, epics, issues, custom fields, or apps, tailored to unique workflows.",
        "hierarchy": ["Custom"],
        "use_case": "Specialized teams (e.g., legal, R&D) with unique workflows.",
        "api_clues": {
            "projects": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/project returns projects",
            "custom_fields": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/field shows custom fields or issue types",
            "issues": "GET https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/search?jql=project=<key> with fields=customfield_*",
            "notes": "Look for unusual configurations or app-specific data"
        },
        "questions_to_ask": [
            "Do you use a unique setup in Jira, like custom issue types or fields, to organize work?",
            "Can you describe how you group your work, or should I check for custom fields or issue types?"
        ]
    }
]
