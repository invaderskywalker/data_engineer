from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat


milestones_and_task_breakdown_data_format = """
{{
                "milestones": [
                    {{
                        "milestone_id": "[Milestone ID]",
                        "milestone_name": "[Milestone Name]",
                        "description": "[Brief description of the milestone]",
                        "completion_criteria": "[What success looks like for this milestone]",
                        "role_workload_distribution": {{
                            "[Role Name]": "[Total workload days for this role]"
                        }},
                        "deliverables": [
                            {{
                                "deliverable_id": "[Deliverable ID]",
                                "deliverable_name": "[Deliverable Name]",
                                "description": "[Brief description of the deliverable]",
                                "tasks": [
                                    {{
                                        "task_id": "[Task ID]",
                                        "task_description": "[Task Description]",
                                        "estimated_duration_days": "[Duration in days]",
                                        "assigned_role": "[Assigned Role]",
                                        "dependencies": ["[Task ID(s) this task depends on, if any]"],
                                        "can_be_done_in_parallel_with": ["[Task ID(s) that can be done in parallel, if any]"],
                                        "priority": "[High/Medium/Low]",
                                        "risk_assessment": "[Risk or challenge, if any]",
                                        "risk_mitigation_plan": "[Plan to mitigate the risk]",
                                        "buffer_time_days": "[Optional: Buffer time in days]"
                                    }},
                                    ...
                                ]
                            }},
                            ...
                        ]
                    }},
                    ...
                ]
            }}
"""


def MilestonesAndTasksBreakdownPrompt(project_data) -> ChatCompletion:
    prompt = f"""
        You are given a project description that includes objectives and key results.

        ### Your Task:
        Break down the project into:
        1. Major milestones, each representing a key project phase.
        2. Clear deliverables under each milestone, which show the expected outcomes.
        3. Specific, actionable tasks under each deliverable.

        ### Milestone Requirements:
        - Milestones should represent high-level project phases or goals.
        - Each milestone should have a clear, short description explaining its purpose.
        - Milestones should have at least one deliverable.
        - Include **completion criteria** to define what success looks like for each milestone.
        - Include **workload distribution** across assigned roles, calculating the total days for each role.

        ### Deliverable Requirements:
        - Each deliverable should be a concrete, measurable outcome (e.g., "API Integration Completed").
        - Provide a short description for each deliverable.

        ### Task Requirements:
        - Each task should be clearly actionable, with a detailed description of what needs to be done. and they should be divided into tasks for frontend developers, backend developers, qa engineers , UX devs etc.
        - Include the estimated time duration (in days) to complete the task.
        - Assign a specific role responsible for completing the task.
        - Specify task dependencies (if any) and identify which tasks can be done in parallel.
        - Include any relevant risk assessment or testing tasks for each milestone.
        - If possible, add a buffer time for tasks that involve high complexity or external dependencies.
        - Assign a **priority level** (High, Medium, Low) for each task based on its criticality.
        - Add a **risk mitigation plan** where needed for tasks with significant risks.

        ### Output Format (JSON):
        ```json
            {milestones_and_task_breakdown_data_format}
        ```

        ### Input Data:
        {project_data}
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def UpdateMilestonesAndTasksBreakdownPrompt(milestones_and_tasks_breakdown, user_input) -> ChatCompletion:
    prompt = f"""
        For the 
        Milestones and Task Breakdown: {milestones_and_tasks_breakdown}
        
        user has requested you to mnake some changes - {user_input}
        
        You have to carefully think and properly update the milestones, deliverables and tasks breakdown and make changes as per user request
        ### Output Format (JSON):
        ```json
            {milestones_and_task_breakdown_data_format}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


JiraOutputFormat = """
{{
    "jira_tasks": [
        {{
            "issue_type": "[Task/Story/Subtask]",
            "summary": "[Smaller Task Description]",
            "assignee": "[Assigned Role]",
            "due_date": "[Calculated End Date]",
            "priority": "[High/Medium/Low]",
            "task_id": "[Original Task ID]",
            "dependencies": "[List of Task IDs or Issue IDs this issue depends on]",
            "acceptance_criteria": "[Criteria for completion]",
            "story_points": "",
            "category": "[Backend/Frontend]"  // Add this field
        }},
        ...
    ]
}}
"""


def CreateJiraIssuesPrompt(
    milestones_and_tasks_breakdown
) -> ChatCompletion:
    prompt = f"""
        You are given a set of prioritized and sequenced tasks with timelines. Your task is to break down these tasks into as many smaller, actionable Jira issues as possible for integration via OAuth. Each issue should focus on a specific work item and include the issue type, summary, assignee, due date, priority, dependencies, and acceptance criteria.

        ### Input:
        Milestones and Task Breakdown: {milestones_and_tasks_breakdown}

        ### Steps:
        1. For each task, split it into the smallest actionable Jira issues based on specific work items. Consider all roles needed (e.g., frontend, backend, AI development, testing) to ensure comprehensive coverage of each aspect of the task.
        2. For tasks involving Developers/Software Developers, categorize or split them into `Backend` and `Frontend` tasks. Specify the type of work like frontend dev, backend dev.
        3. For each issue, determine the due date by considering estimated duration and dependencies.
        4. Create a Jira issue for each smaller task or subtask, specifying the issue type (e.g., Task, Subtask, Story), summary, assignee, due date, priority, and task ID.
        5. Specify which task this Jira issue represents, so it's clear how the issue connects to the original task breakdown.
        6. Ensure each task is divided into multiple issues where applicable. For example, a task like "Finalize AI model integration and conduct thorough testing" should be broken down into specific steps like "Tune AI model LLM to create Jira issues" and "Conduct thorough testing of AI model integration."
        7. Format the issues in a Jira-compatible JSON structure.
        
        
        Also include <changes_suggessted_by_user> which wil be string. 
        but add that into your task/subtask list
        for appropraite task item using your understanding.

        ### Always Output in JSON Format (JSON):
        ```json
            {JiraOutputFormat}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def UpdateJiraIssuesPrompt(
    milestones_and_tasks_breakdown, jira_issues, user_changes
) -> ChatCompletion:
    prompt = f"""
        For the 
        Milestones and Task Breakdown: {milestones_and_tasks_breakdown}
        a set of jira issues/tasks/subtasks are alreadty created - {jira_issues}
        but the user wants you to update the jira issues/tasks/subtasks as per user request - {user_changes} 
        
        Think carefully on what task to create and update the current tasks/issues.
        And output all issues/tasks.

        ### Always Output in JSON Format (JSON):
        ```json
            {JiraOutputFormat}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def CreateEpicsPrompt(milestones_and_tasks_breakdown, jira_issues) -> ChatCompletion:
    prompt = f"""
        You are given a detailed breakdown of tasks derived from milestones within a project. Your task is to group these tasks into coherent epics that capture related work items, ensuring that each epic aligns with the project’s objectives and facilitates organized progress tracking.

        For the
        Milestones and Task Breakdown: {milestones_and_tasks_breakdown}
        
        A list of jira Issues are created:
        {jira_issues}
        
        

        ### Steps:
        1. Analyze the provided tasks and identify common themes, objectives, or functionalities that can be grouped together.
        2. For each group of related tasks, create an epic that summarizes the overarching goal, including a title and description.
        3. Ensure that each epic captures all relevant tasks, indicating how they contribute to the epic's completion.
        4. Clearly specify the tasks that belong to each epic, including their IDs for easy reference.
        5. Consider prioritization and dependencies among tasks to ensure effective organization of epics.

        ### Output Format (JSON):
        ```json
        {{
            "epics": [
                {{
                    "epic_title": "[Epic Title]",
                    "epic_description": "[Epic Description]",
                    "tasks": [
                        {{
                            "task_id": "[Task ID]",
                            "summary": "[Task Summary]"
                        }},
                        ...
                    ]
                }},
                ...
            ]
        }}
        ```

        Ensure that the epics are actionable and provide a clear framework for managing the associated tasks.
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )
