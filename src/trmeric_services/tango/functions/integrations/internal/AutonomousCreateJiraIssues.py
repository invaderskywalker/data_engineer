from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.tango.functions.integrations.general.ClarifyingQuestionFunction import ask_clarifying_question
from src.trmeric_services.autonomous_agents.JiraIssuesCreator import JiraIssuesCreatorService


def autonomous_create_jira_issues(
    eligibleProjects: list[int],
    tenantID: int,
    userID: int,
    project_id=None,
    feedback_provided_for_milestone=False,
    feedback_provided_for_jira_tasks_created=False,
    user_confirmation_of_satisfaction_milestone_and_task_breakdown=False,
    changes_suggested_by_user_for_milestones_and_tasks_breakdown=None,
    user_confirmation_of_satisfaction_for_jira_tasks_created=False,
    changes_suggested_by_user_for_jira_tasks=None,
    **kwargs
):
    if project_id is None:
        return ask_clarifying_question("Which project you want me to create jira issues?")

    if len(project_id) > 1:
        return ask_clarifying_question("Currently I can only accept one project. Please only tell one project to process")

    jira_issues_creator_service = JiraIssuesCreatorService(
        tenant_id=tenantID,
        user_id=userID
    )
    # milestones_and_tasks_breakdown = None
    if not user_confirmation_of_satisfaction_for_jira_tasks_created and not feedback_provided_for_jira_tasks_created:
        if not feedback_provided_for_milestone and not user_confirmation_of_satisfaction_milestone_and_task_breakdown:
            print("autonomous_create_jira_issues debug --- 1")
            milestones_and_tasks_breakdown = jira_issues_creator_service.startProcess(
                project_ids=project_id)
            return ask_clarifying_question(f"I've broken down the milestones and deliverables and tasks for your project: `milestones_and_tasks_breakdown` - {milestones_and_tasks_breakdown}. Do you have any feedback or changes?. Present this in markdown format nested by bullets")

        if feedback_provided_for_milestone and not user_confirmation_of_satisfaction_milestone_and_task_breakdown:
            print("autonomous_create_jira_issues debug --- 2")
            data = jira_issues_creator_service.updateMilestoneAndTaskBreakDown(
                user_input=changes_suggested_by_user_for_milestones_and_tasks_breakdown)
            return ask_clarifying_question(f"I have made changes as per your instruction:  {data}. Do you think any more changes you want or proceed to jira tasks creation?")

        if user_confirmation_of_satisfaction_milestone_and_task_breakdown:
            print("autonomous_create_jira_issues debug --- 3")
            jira_issues_breakdown = jira_issues_creator_service.createIssuesData(
                milestones_and_tasks_breakdown=changes_suggested_by_user_for_milestones_and_tasks_breakdown
            )
            return ask_clarifying_question(f"The Jira issues/tasks have been generated: `jira_tasks` - {jira_issues_breakdown}. Do you want to finalize and create epics for these issues?")

    if not user_confirmation_of_satisfaction_for_jira_tasks_created:
        # update tasks with user request
        print("autonomous_create_jira_issues debug --- 4")
        jira_issues_list = jira_issues_creator_service.updateIssuesData(
            user_changes=changes_suggested_by_user_for_jira_tasks
        )
        return ask_clarifying_question(f"The Jira issues/tasks have been updated: `jira_tasks` - {jira_issues_list}. Do you want to finalize and create Epics for these?")

    if user_confirmation_of_satisfaction_for_jira_tasks_created:
        print("autonomous_create_jira_issues debug --- 5")
        # go ahead with current jira issues
        epics_data = jira_issues_creator_service.createEpicsAndSave()
        return ask_clarifying_question(f"The Jira epics have been generated: {epics_data}. Do you want to finalize and create these issues in Jira?")

    print("autonomous_create_jira_issues debug --- 6")
    # if feedback_provided_for_jira_tasks_created:

    # # @TODO: later need to confirm the project/epic level issue creation
    # if feedback_provided_for_milestone:
    # return JiraIssuesCreatorService(tenant_id=tenantID, user_id=userID).startProcess(project_ids=project_id)


AUTONOMOUS_CREATE_JIRA_ISSUES = TangoFunction(
    name="autonomous_create_jira_issues",
    description="""
        When the user wants you to create jira issues/tasks for a project for him/her.
        
        ## INSTRUCTIONS
        Never assume project IDs or Jira project IDs. Always confirm them with the user.
        The flow involves gathering user feedback on milestones and task breakdowns before proceeding to Jira issue creation.
        After creating Jira tasks, gather user feedback on the tasks and explicitly confirm satisfaction before marking the task creation process complete.
    """,
    args=[
        {
            "name": "project_id",
            "type": "int[]",
            "description": "The specific project ID(s) that the user is interested in.",
            "conditional": "in",
        },
        {
            "name": "feedback_provided_for_milestone",
            "type": "bool",
            "description": """
                Set this to `True` when the user provides feedback on the presented milestones and tasks breakdown. 
                Do not assume that the user is satisfied with the breakdown at this stage.
            """,
        },
        {
            "name": "changes_suggested_by_user_for_milestones_and_tasks_breakdown",
            "type": "str",
            "description": """
                After receiving feedback, update the `milestones_and_tasks_breakdown` with all changes clearly specified.
                This field should reflect any adjustments the user requests.
            """,
        },
        {
            "name": "user_confirmation_of_satisfaction_milestone_and_task_breakdown",
            "type": "bool",
            "description": """
                This should remain `False` unless the user **explicitly confirms** satisfaction with the milestones_and_tasks_breakdown.
                Example - if the user says that he is satisfied or move forward then only make this to True
                The agent should ask for explicit confirmation after feedback is given. Do not assume the user is satisfied just 
                because they requested Jira issues/tasks to be created.
            """,
        },
        {
            "name": "user_confirmation_of_satisfaction_for_jira_tasks_created",
            "type": "bool",
            "description": """
                This should remain `False` unless the user **explicitly confirms** satisfaction with the jira_issues.
                Example - if the user says that he is satisfied or move forward then only make this to True
                The agent should ask for explicit confirmation after feedback is given. Do not assume the user is satisfied.
            """,
        },
        {
            "name": "changes_suggested_by_user_for_jira_tasks",
            "type": "str",
            "description": """
                After receiving feedback, update the `jira_tasks` with all changes clearly specified.
                This field should reflect any adjustments the user requests.
            """,
        },
        {
            "name": "feedback_provided_for_jira_tasks_created",
            "type": "bool",
            "description": "The specific project ID(s) that the user is interested in.",
        },
    ],
    return_description="A function to use when user wants to create Jira issues/tasks for a project.",
    func_type="general",
    function=autonomous_create_jira_issues,
    integration="trmeric"
)
