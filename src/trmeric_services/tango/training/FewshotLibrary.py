from src.trmeric_services.tango.training.TangoFewshot import TangoFewshot
import typing as t

budget_growth = TangoFewshot(
    query="What % of my budgeted project spend impacts growth?",
    prev=[],
    thought="There are 3 types of project: Innovate, Run, and Transform. I can compare projects by project_type, which will show me the amount spent by each project type. Since Innovate projects are the ones that impact growth, I can compare the spend of Innovate projects to the total spend to get the percentage of budgeted project spend that impacts growth.",
    functions_called="compare_projects_by(compare_by='project_type')",
    integrations_used=["general"],
    data_summary="<A table showing the logistics/details of projects by their type>",
    output_format="Around <percentage> of your budgeted project spend impacts growth. Would you like to know more about the projects that are impacting growth?",
)

green_projects = TangoFewshot(
    query="How many projects are green?",
    prev=[],
    thought="This is a very basic question. I can simply check whihc projects are on track in terms of spend, scope, and delivery status. ",
    functions_called=f"""view_projects(delivery_status=['on_track'], scope_status=['on_track'], spend_status=['on_track'])""",
    integrations_used=["general"],
    data_summary="<A table showing a list of projects whose scopes are all on track, along with information about their summary and most recent updates.",
    output_format="""We looked at all the projects that were on track in all dimensions and found that there are <number> projects that are green.
Overall, these projects are budgetted to be <budgetted_spend>, but the actual spend is <actual_spend>. 

Some of the key projects in this bunch are <list 3,4 projects>. 
<summarize overall status>
<highlight recent updates>

Would you like to know more about these projects?""",
)

my_top_projects = TangoFewshot(
    query="What are my top projects?",
    prev=[],
    thought="I am just going to do view_projects and see which projects have the most spend/impact.",
    functions_called="view_projects()",
    integrations_used=["general"],
    data_summary="<A table showing the top projects by spend/impact>",
    output_format="""I found your top projects by spend and did some analysis on them.
<table with columns: project name, project managers, projected spend, actual spend, statuses>

<chart of actual, budgetted spend of these 5 projects>

Here is a summary of what is going on in them (bullet points)
<summary of the updates in the top 5 projects>""",
)

prev_projects = TangoFewshot(
    query="What are the projects that have been started in the last 30 days?",
    prev=[],
    thought="The current date is July 19, 2024, so I am going to use the view_projects function and filter by the start date being after June 19, 2024 and before July 20, 2024.",
    functions_called="""view_projects(start_date={ 'lower_bound': '2024-06-19', 'upper_bound': '2024-07-20'})""",
    integrations_used=["general"],
    data_summary="<A table showing the projects that have been started in the last 30 days>",
    output_format="TODO",
)

milestone_statuses = TangoFewshot(
    query="List all the milestone status and comments across projects.",
    prev=[],
    thought="Since the view projects function shows the status and milestones of projects, I am going to use that and then observe the milestones from that table.",
    functions_called="view_projects()",
    integrations_used=["general"],
    data_summary="<A table showing the status and milestones of projects>",
    output_format="TODO",
)

provider_most_projects = TangoFewshot(
    query = "Which providers is doing the most projects for us?",
    prev = [],
    thought="We can do a commparison between providers, which will show us the number of projects each provider is working on.",
    functions_called="compare_projects_by(compare_by='provider_id')",
    integrations_used=["general"],
    data_summary="<A table showing the statistics of projects by provider>",
    output_format="TODO",
)

provider_staff_on_projects = TangoFewshot(
    query = "How much of my actual spend is on cloud projects.",
    thought="I can use the view_projects function and filter by project_category being on cloud.",
    functions_called="view_projects(project_category=['Cloud', 'cloud', 'CLOUD'])",
    integrations_used=["general"],
    data_summary="<A table showing the statistics of cloud projects>",
    output_format="TODO",
)

compare_actual_vs_budgetted_spend = TangoFewshot(
    query = "Compare actual spend vs budgeted spend for top 5 projects.",
    thought="I can use the view_projects function and this will show all the projects along with their budgetted and planned spend. I will then determine from there which are the top highest budgetted project spend.",
    functions_called="view_projects()",
    integrations_used=["general"],
    data_summary="<A table showing the statistics of projects by spend>",
    output_format="TODO",
)

objectives_key_results = TangoFewshot(
    query = "Show the objectives and key results of the top 5 projects.",
    thought = "I can use the view_projects function and this will show all the projects along with their objectives and key results. I will then determine from there which are the top 5 projects.",
    functions_called = "view_projects()",
    integrations_used = ["general"],
    data_summary = "<A table showing the objectives and key results of projects>",
    output_format = "TODO",
)

early_stages_execution = TangoFewshot(
    query = "What % of my projects are in the early stages of execution?",
    thought = "I can use the compare_projects_by function and compare projects by their different project state",
    functions_called = "compare_projects_by(compare_by='project_state')",
    integrations_used = ["general"],
    data_summary = "<A table showing the statistics of projects by project state>",
    output_format = "TODO",
)

'''
Question: Which projects have had a red or amber status for the longest time?
Thought: Red and amber refers to compromised or at risk. I can use the view_projects function. However, since it doesn't mention what kind of scope or spend status, and the function does AND filtering, I'll just write view_projects and manually view the projects.
```
view_projects()
```

Question: How many projects are in red status?
Thought: I can use the view_projects function and just observe the number of projects that are in red status.
I'm not going to say add the arguments of all the status types because it's an AND so it will only find projects who are red for all scopes.
This is asking what is red for any scope, so I'll just do a simple view_projects.
```
view_projects()
```

Question: Typically after how many days of project start do projects go amber or red?
Thought: I don't really have an explicit function for this, so I'll just have to manually check the project status and the date it started. This will require me to do do view_projects.
```
view_projects()
```

Question: Which portfolio has the weakest performance on projects.
Thought: I can use the compare_projects_by function and compare projects by their portfolio.
```
compare_projects_by(compare_by='portfolio_id')
```

Question: Which project managers are doing well?
Thought: I can use the compare projects function and compre by project manager id.
```
compare_projects_by(compare_by='project_manager_id')
```

Question: Which projects are doing well? These are projects which are in green or projects that are turning green on any dimension.
Thought: I can use the view_projects function and filter by delivery_status being on_track. I will also look at at_risk projects and see if their updates are hinting towards them turning green.
```
view_projects(delivery_status=['at_risk', 'on_track'])
```

Question: What key results do my projects need to move the needle on.
Thought: I can use the view_projects function and this will show all the projects along with their key results. I will then analyze the result and determine which key results are needed to move the needle.
```
view_projects()
```

Question: What is the sum of all the project spend overruns?
Thought: I can use the view_projects function and this will show all the projects along with their budgetted and planned spend. I will then determine the sum of all the project spend overruns.
```
view_projects()
```

Question: Which provider has the best execution status right now?
Thought: I can use the compare_projects_by function and compare by provider.
```
compare_projects_by(compare_by='provider_id')
```

Question: Why are my projects delayed?
Thought: I can use the view_projects function and filter by delivery_status being at risk or compromised.
```
view_projects(delivery_status=['at_risk', 'compromised'])
```

Question: What are the risks associated with my projects?
Thought: I can use the view_projects function and to see all projects and then I will look at their updates and see what risks are associated with them.
```
view_projects()
```

Question: What can I tell our CMO about the status of our initiatives?
Thought: I'm going to need a complete overview of all the projects. I can use the view_projects, the get_actions command, the view_roadmaps command, and the get_jira_data command.
```
view_projects()
get_actions()
view_roadmaps()
```

Question: On which technology do we have the largest number of team members?
Thought: I can use the compare_projects_by function and compare by technology.
```
compare_projects_by(compare_by='tech_stack')
```

Question: What are the main reasons for project overruns?
Thought: I can use the view_projects function and filter by spend_status being at_risk or compromised.
```
view_projects(spend_status=['at_risk', 'compromised'])
```

Question: Which project has the highest cost overrun?
Thought: I can use the view_projects function and just analyze which project had the highest cost overrun.
```
view_projects()
```

Question: Which projects have the highest risk of spend overrun before completion?
Thought: I can use the view_projects function and filter by spend_status being at_risk or compromised.
```
view_projects(spend_status=['at_risk', 'compromised'])
```

Question: How are my engineering efforts going?
Thought: I can use the Github function to get the engineering efforts.
```
get_github_information()
```

Question: Which projects are in red status?
Thought: I can use the view_projects function and just count which projects are in red status.
```
view_projects()
```

Question: Tell me about the risks in my projects
Thought: I'm going to need a complete overview of all the projects. I can use the view_projects and the view_projects_risks command.
```
view_projects()
view_projects_risks()
```

Question: Which projects need my attention?
Thought: I can use the view_projects function without any arguments, because instead of seeing projects that are at risk/compromised in ALL dimensions, I want to see projects that are at risk/compromised in ANY dimension.
```
view_projects()
```
"""'''

red_amber_longest = TangoFewshot(
    query = "Which projects have had a red or amber status for the longest time?",
    thought = "I can use the view_projects function and then manually view the projects.",
    functions_called = "view_projects()",
    integrations_used = ["general"],
    data_summary = "<A table showing the statistics of projects by status>",
    output_format = "TODO",
)

projects_red = TangoFewshot(
    query = "How many projects are in red status?",
    thought = "I can use the view_projects function and just observe the number of projects that are in red status.",
    functions_called = "view_projects()",
    integrations_used = ["general"],
    data_summary = "<A table showing the statistics of projects by status>",
    output_format = "TODO",
)

days_to_amber_red = TangoFewshot(
    query = "Typically after how many days of project start do projects go amber or red?",
    thought = "I'll just have to manually check the project status and the date it started. This will require me to do do view_projects.",
    functions_called = "view_projects()",
    integrations_used = ["general"],
    data_summary = "<A table showing the statistics of projects by status and start date>",
    output_format = "TODO",
)

weakest_portfolio = TangoFewshot(
    query = "Which portfolio has the weakest performance on projects?",
    thought = "I can use the compare_projects_by function and compare projects by their portfolio.",
    functions_called = "compare_projects_by(compare_by='portfolio_id')",
    integrations_used = ["general"],
    data_summary = "<A table showing the statistics of projects by portfolio>",
    output_format = "TODO",
)

active_project_managers = TangoFewshot(
    query = "Which project managers are doing well?",
    thought = "I can use the compare projects function and compre by project manager id.",
    functions_called = "compare_projects_by(compare_by='project_manager_id')",
    integrations_used = ["general"],
    data_summary = "<A table showing the statistics of projects by project manager>",
    output_format = "TODO",
)

overrun_reasons = TangoFewshot(
    query = "What is the main reason for project overruns?",
    thought = "I can use the view_projects function and filter by spend_status being at_risk or compromised.",
    functions_called = "view_projects(spend_status=['at_risk', 'compromised'])",
    integrations_used = ["general"],
    data_summary = "<A table showing the statistics of projects by spend status>",
    output_format = "TODO",
)

spend_overrun_risks = TangoFewshot(
    query = "Which projects have the highest risk of spend overrun before completion?",
    thought = "I can use the view_projects function and filter by spend_status being at_risk or compromised.",
    functions_called = "view_projects(spend_status=['at_risk', 'compromised'])",
    integrations_used = ["general"],
    data_summary = "<A table showing the statistics of projects by spend status>",
    output_format = "TODO",
)

project_risks = TangoFewshot(
    query = "Tell me about the risks in my projects",
    thought = "I'm going to need a complete overview of all the projects. I can use the view_projects and the view_projects_risks command.",
    functions_called = "view_projects()",
    integrations_used = ["general"],
    data_summary = "<A table showing the statistics of projects by risks>",
    output_format = "TODO",
)

technology_largest = TangoFewshot(
    query = "On which technology do we have the largest number of team members?",
    thought = "I can use the compare_projects_by function and compare by technology.",
    functions_called = "compare_projects_by(compare_by='tech_stack')",
    integrations_used = ["general"],
    data_summary = "<A table showing the statistics of projects by technology stack>",
    output_format = "TODO",
)

cmo = TangoFewshot(
    query = "What can I tell our CMO about the status of our initiatives?",
    thought = "I'm going to need a complete overview of all the projects. I can use the view_projects, the get_actions command, the view_roadmaps command, and the get_jira_data command.",
    functions_called = "view_projects()\nget_actions()\nview_roadmaps()\nget_jira_issues()",
    integrations_used = ["general", "?jira"],
    data_summary = "<A table showing the statistics of projects by status>",
    output_format = "TODO",
)


falling_behind = TangoFewshot(
    query = "Where am I falling behind on my projects?",
    thought = "I can use the view_projects function and filter by delivery_status being at_risk or compromised.",
    functions_called = "view_projects(delivery_status=['at_risk', 'compromised'])\nview_projects_risks()",
    integrations_used = ["general"],
    data_summary = "<A table showing the statistics of projects by status>",
    output_format = "TODO",
)



project_sentiment = TangoFewshot(
    query = "What is the sentiment of my initiative with <provider_415> on the <xyz> initiative. Is there any disagreement or something I should be aware of.",
    prev = [],
    thought = "I see that there is a slack channel called <provider_415>-<xyx>, and I am going to read that. Also, I see that there is a Jira project, specifically 2 sprints, that seem to be documenting this initiative along with a Excel sheet as well. I will use access all of these using different functions.",
    functions_called=
    """
    read_slack_channel_history(channel_id_1),
    get_jira_data([project_id, sprint_id_1])
    get_jira_data([project_id, sprint_id_2])
    read_excel_book(workbook_id)
    """,
    integrations_used = ["slack"],
    data_summary="<A compilation of the chats derived from multiple separate slack channels>",
    output_format=""" 
    The below information is extracted from your slack channels titled <channel_name>.
    <Paragraph contain analysis of general sentiment from Slack Channels>
    
    The below data is from your jira <project> and its sprints <sprint1> and <sprint2>. 
    
    <Table containing information from Jira project, separated and designated by sprint>
    
    Below, we have the data from the excel sheet titled <Excel_Sheet_Name>
    
    <Table containing the data from Excel sheet>.
    """
)

project_progress = TangoFewshot(
    query = "Can you provide an update on the progress of our team's work on the <Project_Alpha> during the last sprint?",
    prev = [],
    thought = "To gather the necessary information, since sprint was explicitly mentioned, I will access the Jira project <Project_Alpha> and retrieve data from the most recent sprint. I will analyze the completion status, identify any blockers, and summarize key metrics.",
    functions_called=
    """
    get_jira_data([project_id_alpha, latest_sprint_id])
    """,
    integrations_used = ["jira"],
    data_summary="<A summary of sprint completion status, blocker issues, and key metrics from the latest sprint>",
    output_format=""" 
    The following information is extracted from the Jira project <Project_Alpha> for the most recent sprint <latest_sprint_id>.
    
    <Paragraph analyzing sprint completion, blockers, and key metrics>
    
    The data suggests that the team has completed X% of the planned work, with Y% of tasks remaining open due to blockers. Below is a table summarizing the key metrics.
    
    <Table containing key sprint metrics>
    """
)

sprint_breakdown = TangoFewshot(
    query = "I need a detailed breakdown of the tasks completed in sprints 1 and 2 of the <Project_Beta>.",
    prev = [],
    thought = "I will access the Jira project <Project_Beta> and retrieve detailed data from both sprints 1 and 2. I will identify the tasks completed, which team members worked on them, and any significant observations.",
    functions_called=
    """
    get_jira_data([project_id_beta, sprint_id_1])
    get_jira_data([project_id_beta, sprint_id_2])
    """,
    integrations_used = ["jira"],
    data_summary="<A compilation of tasks completed and team members involved in sprints 1 and 2>",
    output_format=""" 
    The following information is extracted from the Jira project <Project_Beta> for sprints 1 and 2.
    
    <Paragraph summarizing tasks completed and team members involved in each sprint>

    """
)

project_overview = TangoFewshot(
    query = "Can you give me an overview of the <Project_Gamma> in Azure DevOps? I'm particularly interested in the epics and sprints associated with it.",
    prev = [],
    thought = "To gather this information, since ADO was mentioned, I will access the Azure DevOps project <Project_Gamma> and retrieve details about the epics and sprints. I will then summarize the key points and any significant observations.",
    functions_called=
    """
    get_ado_project_data([project_id_gamma])
    """,
    integrations_used = ["ado"],
    data_summary="<A summary of epics and sprints within the project>",
    output_format=""" 
    The following information is extracted from the Azure DevOps project <Project_Gamma>.
    
    <Paragraph summarizing the key epics and associated sprints>

    Below is a table listing the epics and their corresponding sprints:

    <Table containing epics and sprints>
    """
)

project_issues = TangoFewshot(
    query = "I need a detailed report on the issues tracked under <Project_Delta> in Azure DevOps. What epics and sprints are they associated with?",
    prev = [],
    thought = "To provide the necessary details, since ADO was mentioned, I will access the Azure DevOps project <Project_Delta> and retrieve all issues, along with their associated epics and sprints.",
    functions_called=
    """
    get_ado_project_data([project_id_delta])
    """,
    integrations_used = ["ado"],
    data_summary="<A report of issues, along with their associated epics and sprints>",
    output_format=""" 
    The following information is extracted from the Azure DevOps project <Project_Delta>.
    
    <Paragraph providing a detailed report on the issues, including their epics and sprints>

    Below is a table summarizing the issues, epics, and associated sprints:

    <Table containing issues, epics, and sprints>
    """
)

channel_sentiment = TangoFewshot(
    query = "What's the overall sentiment in the customer feedback Slack channel? Have there been any major concerns raised?",
    prev = [],
    thought = "To analyze the sentiment, I will read the message history of the <#customer_feedback> Slack channel and identify any major concerns or patterns in the conversations.",
    functions_called=
    """
    read_slack_channel_history(channel_id_customer_feedback)
    """,
    integrations_used = ["slack"],
    data_summary="<A sentiment analysis of the channel's message history>",
    output_format=""" 
    The following information is extracted from the Slack channel <#customer_feedback>.
    
    <Paragraph summarizing the overall sentiment and any major concerns raised>

    Below is a table of key messages or concerns from the channel:

    <Table containing key messages or concerns>
    """
)

project_discussion = TangoFewshot(
    query = "Can you provide a summary of the discussions in the <#project_alpha> Slack channel over the past month?",
    prev = [],
    thought = "To create this summary, I will read the message history of the <#project_alpha> Slack channel and compile the key points and decisions made during the discussions.",
    functions_called=
    """
    read_slack_channel_history(channel_id_project_alpha)
    """,
    integrations_used = ["slack"],
    data_summary="<A summary of discussions from the channel's message history>",
    output_format=""" 
    The following information is extracted from the Slack channel <#project_alpha>.
    <Paragraph summarizing the key points and decisions made in the discussions>

    Below is a table of important messages and decisions:

    <Table containing key messages and decisions>
    """
)

user_notification = TangoFewshot(
    query = "Please notify <user_A> about the upcoming project deadline on Slack.",
    prev = [],
    thought = "To ensure that <user_A> is aware of the upcoming deadline, I will send them a direct message on Slack with the necessary details.",
    functions_called=
    """
    send_slack_dm(user_id_A, "Reminder: The project deadline is approaching. Please ensure all tasks are completed by the due date.")
    """,
    integrations_used = ["slack"],
    data_summary="<Confirmation that the direct message has been sent>",
    output_format=""" 
    The following direct message has been sent to <user_A> on Slack:

    "Reminder: The project deadline is approaching. Please ensure all tasks are completed by the due date."

    <Confirmation of the message sent>
    """
)

team_lead_request = TangoFewshot(
    query = "Can you send a direct message to <user_B> asking for an update on their task?",
    prev = [],
    thought = "To request an update from <user_B>, I will send them a direct message on Slack, asking for the status of their task.",
    functions_called=
    """
    send_slack_dm(user_id_B, "Could you please provide an update on your task? The team is awaiting your input.")
    """,
    integrations_used = ["slack"],
    data_summary="<Confirmation that the direct message has been sent>",
    output_format=""" 
    The following direct message has been sent to <user_B> on Slack:

    "Could you please provide an update on your task? The team is awaiting your input."

    <Confirmation of the message sent>
    """
)

dm_conversation_review = TangoFewshot(
    query = "I need to review the conversation with <user_C> in our Slack direct messages.",
    prev = [],
    thought = "To review the conversation, since Slack was mentioned, I will retrieve the message history from the direct message channel with <user_C> on Slack.",
    functions_called=
    """
    read_slack_dm_history(dm_channel_id_C)
    """,
    integrations_used = ["slack"],
    data_summary="<A summary of the DM conversation history with <user_C>>",
    output_format=""" 
    The following is a summary of the conversation with <user_C> from our Slack direct messages:

    <Paragraph summarizing key points of the conversation>

    Below is a table of important messages from the DM history:

    <Table containing key messages>
    """
)

issue_discussion_review = TangoFewshot(
    query = "Can you pull up the message history from my direct messages with <user_D> regarding the issue they raised last week?",
    prev = [],
    thought = "To review the discussion about the issue, I will retrieve the message history from the direct message channel with <user_D> on Slack.",
    functions_called=
    """
    read_slack_dm_history(dm_channel_id_D)
    """,
    integrations_used = ["slack"],
    data_summary="<A summary of the issue discussion from the DM history>",
    output_format=""" 
    The following is a summary of the discussion with <user_D> regarding the issue they raised last week:

    <Paragraph summarizing the key points of the discussion>

    Below is a table of important messages from the DM history:

    <Table containing key messages>
    """
)

project_update_announcement = TangoFewshot(
    query = "Please announce the completion of <Project_Zeta> in the <#project_updates> Slack channel.",
    prev = [],
    thought = "To inform the team about the completion of <Project_Zeta>, I will send a message to the <#project_updates> Slack channel with the announcement.",
    functions_called=
    """
    send_slack_channel_message(channel_id_project_updates, "Project Zeta has been successfully completed. Great work, everyone!")
    """,
    integrations_used = ["slack"],
    data_summary="<Confirmation that the channel message has been sent>",
    output_format=""" 
    The following announcement has been sent to the <#project_updates> Slack channel:

    "Project Zeta has been successfully completed. Great work, everyone!"

    <Confirmation of the message sent>
    """
)

team_meeting_reminder = TangoFewshot(
    query = "Can you remind the team about tomorrow's meeting in the <#general> Slack channel?",
    prev = [],
    thought = "To ensure the team is reminded about tomorrow's meeting, I will send a message to the <#general> Slack channel with the meeting details.",
    functions_called=
    """
    send_slack_channel_message(channel_id_general, "Reminder: Our team meeting is scheduled for tomorrow at 10 AM. Please be on time.")
    """,
    integrations_used = ["slack"],
    data_summary="<Confirmation that the channel message has been sent>",
    output_format=""" 
    The following reminder has been sent to the <#general> Slack channel:

    "Reminder: Our team meeting is scheduled for tomorrow at 10 AM. Please be on time."

    <Confirmation of the message sent>
    """
)

financial_report_analysis = TangoFewshot(
    query = "Can you analyze the financial data from the latest <Q2_Financials> Excel workbook?",
    prev = [],
    thought = "To provide this analysis, I will read the <Q2_Financials> Excel workbook and extract the relevant data from its sheets.",
    functions_called=
    """
    read_excel_book(workbook_id_Q2_Financials)
    """,
    integrations_used = ["office"],
    data_summary="<Summary of the financial data extracted from the workbook>",
    output_format=""" 
    The following information is extracted from the Excel workbook <Q2_Financials>:

    <Paragraph summarizing the key financial data from the workbook>

    Below is a table of the extracted data:

    <Table containing key financial metrics from the workbook>
    """
)

sales_data_review = TangoFewshot(
    query = "Please review the sales data from the <Annual_Sales_2023> Excel workbook. Focus on the <Sales by Region> sheet.",
    prev = [],
    thought = "To review the sales data, I will read the <Annual_Sales_2023> Excel workbook and extract the relevant data, especially from the <Sales by Region> sheet.",
    functions_called=
    """
    read_excel_book(workbook_id_Annual_Sales_2023)
    """,
    integrations_used = ["office"],
    data_summary="<Summary of the sales data with a focus on the Sales by Region sheet>",
    output_format=""" 
    The following information is extracted from the Excel workbook <Annual_Sales_2023>, specifically from the <Sales by Region> sheet:

    <Paragraph summarizing the regional sales data>

    Below is a table of the extracted sales data:

    <Table containing sales data by region>
    """
)

proposal_review = TangoFewshot(
    query = "Can you review the content of the <Project_Proposal_2024> Word document?",
    prev = [],
    thought = "To perform this review, I will read the <Project_Proposal_2024> Word document and summarize its key points.",
    functions_called=
    """
    read_word_doc(document_id_Project_Proposal_2024)
    """,
    integrations_used = ["office"],
    data_summary="<Summary of the key points from the Word document>",
    output_format=""" 
    The following information is extracted from the Word document <Project_Proposal_2024>:

    <Paragraph summarizing the key points of the proposal>

    """
)

policy_document_review = TangoFewshot(
    query = "Please review the <HR_Policies_2024> Word document and highlight any significant changes from last year.",
    prev = [],
    thought = "To highlight the changes, I will read the <HR_Policies_2024> Word document and compare its content to last year's policies.",
    functions_called=
    """
    read_word_doc(document_id_HR_Policies_2024)
    """,
    integrations_used = ["office"],
    data_summary="<Summary of significant changes in the HR Policies document>",
    output_format=""" 
    The following information is extracted from the Word document <HR_Policies_2024>:

    <Paragraph summarizing significant changes in the HR policies>
    """
)

budget_update = TangoFewshot(
    query = "Please update the <Budget_2024> Excel workbook with the new expense data.",
    prev = [],
    thought = "To update the budget, I will write the new expense data to the <Budget_2024> Excel workbook, creating the workbook if it does not exist.",
    functions_called=
    """
    write_to_excel_sheet(workbook_name_Budget_2024, new_expense_data)
    """,
    integrations_used = ["office"],
    data_summary="<Confirmation of the budget update with the new expense data>",
    output_format=""" 
    The following data has been successfully written to the <Budget_2024> Excel workbook:

    <Table containing the new expense data>

    <Confirmation of the successful operation>
    """
)

sales_forecast_update = TangoFewshot(
    query = "Can you add the latest sales forecast data to the <Sales_Forecast_2024> Excel workbook?",
    prev = [],
    thought = "To add the sales forecast data, I will write the data to the <Sales_Forecast_2024> Excel workbook, creating the workbook or sheet if it does not exist.",
    functions_called=
    """
    write_to_excel_sheet(workbook_name_Sales_Forecast_2024, forecast_data)
    """,
    integrations_used = ["office"],
    data_summary="<Confirmation of the sales forecast update in the Excel workbook>",
    output_format=""" 
    The following sales forecast data has been successfully written to the <Sales_Forecast_2024> Excel workbook:

    <Table containing the sales forecast data>

    <Confirmation of the successful operation>
    """
)

project_summary_creation = TangoFewshot(
    query = "Please create a new Word document titled <Project_Summary_2024> and add the project summary text.",
    prev = [],
    thought = "To create the project summary document, I will write the provided text to a new Word document titled <Project_Summary_2024>.",
    functions_called=
    """
    write_to_word_doc(document_name_Project_Summary_2024, project_summary_text)
    """,
    integrations_used = ["office"],
    data_summary="<Confirmation of the document creation and content addition>",
    output_format=""" 
    The following text has been successfully written to the Word document <Project_Summary_2024>:

    <Paragraph containing the project summary text>

    <Confirmation of the successful operation>
    """
)

policy_document_update = TangoFewshot(
    query = "Can you update the <Employee_Handbook_2024> Word document with the new policy changes?",
    prev = [],
    thought = "To update the employee handbook, I will write the new policy changes to the <Employee_Handbook_2024> Word document, creating the document if it does not exist.",
    functions_called=
    """
    write_to_word_doc(document_name_Employee_Handbook_2024, policy_changes_text)
    """,
    integrations_used = ["office"],
    data_summary="<Confirmation of the policy updates in the Word document>",
    output_format=""" 
    The following policy changes have been successfully written to the Word document <Employee_Handbook_2024>:

    <Paragraph summarizing the new policy changes>

    <Confirmation of the successful operation>
    """
)

marketing_campaign_analysis = TangoFewshot(
    query = "Can you analyze the data from the <Q3_Marketing_Campaign> Google Sheet workbook?",
    prev = [],
    thought = "To provide this analysis, I will read the <Q3_Marketing_Campaign> Google Sheet workbook and extract the relevant data from its sheets.",
    functions_called=
    """
    read_google_sheet(workbook_id_Q3_Marketing_Campaign)
    """,
    integrations_used = ["drive"],
    data_summary="<Summary of the marketing campaign data extracted from the Google Sheets workbook>",
    output_format=""" 
    The following information is extracted from the Google Sheets workbook <Q3_Marketing_Campaign>:

    <Paragraph summarizing the key marketing data from the workbook>

    Below is a table of the extracted data:

    <Table containing key marketing metrics from the workbook>
    """
)

employee_performance_review = TangoFewshot(
    query = "Please review the performance data from the <Annual_Performance_Review> Google Sheet workbook.",
    prev = [],
    thought = "To review the performance data, I will read the <Annual_Performance_Review> Google Sheet workbook and extract the relevant data from its sheets.",
    functions_called=
    """
    read_google_sheet(workbook_id_Annual_Performance_Review)
    """,
    integrations_used = ["drive"],
    data_summary="<Summary of the employee performance data extracted from the Google Sheets workbook>",
    output_format=""" 
    The following information is extracted from the Google Sheets workbook <Annual_Performance_Review>:

    <Paragraph summarizing the key employee performance data>

    Below is a table of the extracted performance data:

    <Table containing key performance metrics from the workbook>
    """
)

project_proposal_review = TangoFewshot(
    query = "Can you review the content of the <New_Project_Proposal> Google Docs document?",
    prev = [],
    thought = "To perform this review, I will read the <New_Project_Proposal> Google Docs document and summarize its key points.",
    functions_called=
    """
    read_google_doc(document_id_New_Project_Proposal)
    """,
    integrations_used = ["drive"],
    data_summary="<Summary of the key points from the Google Docs document>",
    output_format=""" 
    The following information is extracted from the Google Docs document <New_Project_Proposal>:

    <Paragraph summarizing the key points of the proposal>
    """
)

policy_document_update = TangoFewshot(
    query = "Please review the <Company_Policies_2024> Google Docs document and highlight any significant changes.",
    prev = [],
    thought = "To highlight the changes, I will read the <Company_Policies_2024> Google Docs document and summarize any significant updates.",
    functions_called=
    """
    read_google_doc(document_id_Company_Policies_2024)
    """,
    integrations_used = ["drive"],
    data_summary="<Summary of significant changes in the Google Docs document>",
    output_format=""" 
    The following information is extracted from the Google Docs document <Company_Policies_2024>:

    <Paragraph summarizing significant changes in the company policies>
    """
)

sales_data_update = TangoFewshot(
    query = "Please update the <Sales_Data_2024> Google Sheet with the new quarterly sales data.",
    prev = [],
    thought = "To update the sales data, I will write the new quarterly sales data to the <Sales_Data_2024> Google Sheet, creating the sheet if it does not exist.",
    functions_called=
    """
    write_to_google_sheet(workbook_name_Sales_Data_2024, quarterly_sales_data)
    """,
    integrations_used = ["drive"],
    data_summary="<Confirmation of the sales data update in the Google Sheets workbook>",
    output_format=""" 
    The following data has been successfully written to the <Sales_Data_2024> Google Sheets workbook:

    <Table containing the new quarterly sales data>

    <Confirmation of the successful operation>
    """
)

budget_forecast_update = TangoFewshot(
    query = "Can you add the latest budget forecast data to the <Budget_Forecast_2024> Google Sheet?",
    prev = [],
    thought = "To add the budget forecast data, I will write the data to the <Budget_Forecast_2024> Google Sheet, creating the sheet if it does not exist.",
    functions_called=
    """
    write_to_google_sheet(workbook_name_Budget_Forecast_2024, forecast_data)
    """,
    integrations_used = ["drive"],
    data_summary="<Confirmation of the budget forecast update in the Google Sheets workbook>",
    output_format=""" 
    The following budget forecast data has been successfully written to the <Budget_Forecast_2024> Google Sheets workbook:

    <Table containing the budget forecast data>

    <Confirmation of the successful operation>
    """
)

meeting_minutes_creation = TangoFewshot(
    query = "Please create a new Google Docs document titled <Meeting_Minutes_2024> and add the minutes from today's meeting.",
    prev = [],
    thought = "To create the meeting minutes document, I will write the provided text to a new Google Docs document titled <Meeting_Minutes_2024>.",
    functions_called=
    """
    write_to_google_doc(document_name_Meeting_Minutes_2024, meeting_minutes_text)
    """,
    integrations_used = ["drive"],
    data_summary="<Confirmation of the document creation and content addition>",
    output_format=""" 
    The following text has been successfully written to the Google Docs document <Meeting_Minutes_2024>:

    <Paragraph containing the meeting minutes>

    <Confirmation of the successful operation>
    """
)

project_outline_creation = TangoFewshot(
    query = "Can you create a new Google Docs document titled <Project_Outline_2024> and add the project outline text?",
    prev = [],
    thought = "To create the project outline document, I will write the provided text to a new Google Docs document titled <Project_Outline_2024>.",
    functions_called=
    """
    write_to_google_doc(document_name_Project_Outline_2024, project_outline_text)
    """,
    integrations_used = ["drive"],
    data_summary="<Confirmation of the document creation and content addition>",
    output_format=""" 
    The following text has been successfully written to the Google Docs document <Project_Outline_2024>:

    <Paragraph containing the project outline text>

    <Confirmation of the successful operation>
    """
)

fewshots: t.List[TangoFewshot] = [budget_growth, green_projects, my_top_projects, prev_projects, milestone_statuses, provider_most_projects, provider_staff_on_projects, compare_actual_vs_budgetted_spend, objectives_key_results, early_stages_execution, red_amber_longest, projects_red, days_to_amber_red, weakest_portfolio, active_project_managers, overrun_reasons, spend_overrun_risks, project_risks, technology_largest, cmo, falling_behind]