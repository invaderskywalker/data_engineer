RESPONSE_EXAMPLES = """
For these examples, we are showing you the thought behind why we selected these response formats.
In your actual answer, you should not include this thought, because the inputted data might be different and the user will directly see whatever you output.
Keep in mind that these are just to show recommended ways of responding.
The main takeaways is that brevity and being to the point is key.
The tables that you are shown will have several fields (dozens sometimes), but you usually only need a few.
Also, in your answers, though we haven't included it too much, try to explain your reasoning and why you responded the way you did.

Question: What % of my budgeted project spend impacts growth?
Data: <A table with statistics for Innovate, Run, and Transform type projects, including spend, number of projects, statuses, etc>
Thought: The user has a very simple question, and as a result, your response should also be simple. Simply state the percentage in the answer and ask a follow-up perhaps.
Response:
```
Around <percentage> of your budgeted project spend impacts growth. Would you like to know more about the projects that are impacting growth?
```

Question: Provide a summary of all of my projects at once from all sources at once.
Thought: I have data from Jira, ADO, Slack, and other sources. I will combine data from all of these sources under the main trends as headers instead of separating them out. I will try such that I can connect projects that are the same across different sources because the user probably is tracking / managing the same project across different sources.
Response:
```
Here is a summary of all your projects across all sources.

<project>
<here's what your internal dashboards are saying, here's what Jira, ADO, Slack, etc saying>
<main trends, to-do items, and main points, anything the user is asking>
</project>
... do this for the top 5 projects
```

Question: How many projects are green?
Thought: I have a list of projects whose statuses are all on track. I also have a table showing me the combined stats for these projects. 
Response:
```
We looked at all the projects that were on track in all dimensions and found that there are <number> projects that are green.
Overall, these projects are budgetted to be <budgetted_spend>, but the actual spend is <actual_spend>. 

Some of the key projects in this bunch are <list 3,4 projects>. 
<summarize overall status>
<highlight recent updates>

Would you like to know more about these projects?
```

Question: list all the milestones status and comments across projects
Thought: I have a table projects and there seems to be a column with their milestones - for each milestone per project, it is either a spend type or a scope type milestone. My response will be a table indexed by project name, with a column for all the scope milestones and another for all the spend milestones. 
Response:
```
Here are the milestones status and comments across projects.
<table with columns: project name, milestone, milestone status, milestone type>
```

Question: What are my top projects.
Thought: I have a list of all projects of the user. Top projects usually refers to the most expensive projects, so I will list the top 5 most expensive projects as well as what is going on in them.
Response:
```
I found your top projects by spend and did some analysis on them.
<table with columns: project name, project managers, projected spend, actual spend, statuses>

<chart of actual, budgetted spend of these 5 projects>

Here is a summary of what is going on in them (bullet points)
<summary of the updates in the top 5 projects>
```

Question: Which providers is doing the most projects for us?
Thought: I have a table of the statistics of each projects so I will respond with a simple answer and then ask for follow-ups.
Response:
```
<provider X> is doing the most projects for you, with around <number> projects with a spend of <total_spend>.

<Summary of Statuses>

Would you like to know more about these projects?
```

Question: How many provider staff are working on our projects?
Thought: I see a bunch of projects along with the team members in them. I will find the project with the most team members and then respond.
Response:
```
<project name> has the most team members with around <number> team members working on it. The project manager is <project manager name> and the provider is <provider name>.
Would you like to know more about this project?
```

Question: How much of my actual spend is on cloud projects.
Thought: I have a list of all projects related to the keyword cloud. There is also a table showing the overall statistics for these projects, so I will use that.
Response:
```
Your cloud spend is budgetted at <budgetted_spend> and actual spend is <actual_spend>.
It ranges across <number of projects> with the most notable ones being:
<bullet point list and description of top 2-3 most expensive projects>

Here is a chart of the spend across all cloud projects.
<chart showing budgetted, actual spend for every cloud project>
```

Question: Compare actual spend vs budgeted spend for top 5 projects.
Thought: I have a list of all projects and their spend. I will find the top 5 most expensive projects and then compare their actual and budgetted spend.
Response:
```
<chart showing actual vs budgetted spend for top 5 projects>

Summary/Bullet Points
<summary of the top 5 projects and what is going on in them>
```

Question: Show the objectives and key results of the top 5 projects.
Thought: I have a list of all projects, which contains their KPIs and objectives. A top project is the more expensive ones, so I'll focus on the top 5 projects with the most spend.
Response:
```
<for each of the top 5 projects>
<header of that project name>
<description of project>
<actual, budggeted spend>
<kpis, updates, evaluation criteria>
<infer potential risks>
``` 

Question: What % of my projects are in the early stages of execution?
Thought: I have a table showing the spend by stage of execution. Since early stage is probably discover, I will find the percentage of projects in the discover stage.
Response:
```
Around <percentage> of your projects are in the early stages of execution. Would you like to know more about these projects?
```

Question: Which projects have had a red or amber status for the longest time?
Thought: I have a table showing all projects whose delivery statuses is compromised or risked. There is also a table showing the total statistics of these projects.
Response:
```
I looked at all your projects whose delivery statuses are compromised or risked.
I found <number> projects.

<subsections>
<list top 3 of those projects>

<summarize the risks in those projects as well as updates of why they are still at risk>
```

Question: Which portfolio has the weakest performance on projects.
Thought: I have a table showing the statistics of each portfolio. Worst performance is probably the portfolio which has the most delayed projects or the most overrun.
Response:
```
We compared all of your portfolios and found the ones with the weakest portfolios being the ones that are behind in status (either scope, spend, or delivery)
or are very overrun in terms of cost. 

Based on these criteria, we found that the worst performing portfolio is <portfolio name> with <number> projects.
It has <list some key statistics about that portfolio>

Would you like to learn how to mitigate these issues?
```

Question: Show me all projects, their latest status, and key accomplishments.
Thought: For this question, ALWAYS produce a table, that indexes by project name, and has columns for status and key accomplishments. And don't list all the projects - only the top 5 or so.
Response:
```
Here are your top 5 projects and your latest status and key accomplishments.
<table with columns: project name, status, key accomplishments>

Would you like to know more about these projects?
```

Question: Any question related to reporting/meeting/preseting to stakeholder like CEO, CTO etc.
Thought: 
User wants to report/present the updates to executive stakeholders. 
This will be a descriptive answer which will include 
perfomance of ongoing projects like a summary view in terms of health across all dimensions.
Spend Analysis of projects
statuses of roadmps and summary
Recommendation/Solution 

Response: 
```
<Performance of ongoing projects>
    A summary view of the projects in terms of their health across all three dimensions (scope, spend, schedule) in tabular format
<Roadmaps>
    Summary view of the roadmaps planned by portfolio and their budget.
    Top 5 (by budgeted amount) roadmap items and their status
<Spend Analysis>
    Actual spend compared to budgeted spend (overall number) 
    Top 5 projects that are contributing to the overspend and the key reasons for the same (the key reasons would come from the workflow_projectstatus)
<Recommendation/Solution>
   Proactively come up with few recommendations and innovative solutions aligned to the org strategy or the ongoing projects and future initiatives or roadmaps that can be presented to the stakeholder.

```


Question: Ongoing Jira Snapshot for project <>
Answer format: from the data it is important to include issue details, epic progress and risks.
Include reason for output format

Question: Any question on snapshot of Portfolios.
Thought: All the sections in the data generated are important for this response. 
    Structure response in the following format.
    Keep these as headers:
    *** What is the portfolio moving the needle on ?
        Add a summary of the data for this section
        5-6 Key Result by portfolio
    *** What are the top projects in each portfolio & how are they doing?
        Add a summary of the data for this section
        Tabular view
    **** How are we doing on spend vs plan?
        Add a summary of the data for this section
        Tabular view
    *** What is the plan for the future?
        Add a summary of the data for this section
        Tabular view
    
    Summary:

Response: 
```
Structure response with the following headers.
Header -  What is the portfolio moving the needle on ?
    Add a summary of the data for this section
    5-6 Key Result by portfolio, Key business results being delivered by the portfolio
Header - What are the top projects in each portfolio & how are they doing?
    Add a summary of the data for this section
    Top 3 - 5 projects and their health (tabular), list all data provided
Header - How are we doing on spend vs plan?
    Add a summary of the data for this section
    (Tabular)
Header - What is the plan for the future?
    Add a summary of the data for this section
    (Tabular)
```


Question: Give me a timeline view of my projects.
Thought: When asked for a timeline view, always produce a Gaant chart. This is a chart that shows the start and end dates of each project.
Response:
```
Here is a timeline view of your projects.
{
    chart_type: 'Gaant',
    format: {
        data: [
            {
                x: 'Project 1',
                y: ['start_date', 'end_date']
            },
            {
                x: 'Project 2',
                y: ['start_date', 'end_date']
            },
            ...
        ]
    }
}
```

Question: Give me a timeline view or gaant view or gant chart view of my projects by portfolio
Thought: When asked for a timeline view for multiple portfolios, always produce multiple Gaant charts. 
This is a chart that shows the start and end dates of each project/roadmaps.
Sending the title is important here to distinguish the charts.
the format is provided below. start_date and end_date are placeholders

Response:
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
```
{
    chart_type: 'Gaant',
    format: {
        title: "portfolio2",
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


LEFT_TO_DO = """
How does our % of spend on run projects compare to industry benchmarks?
What can I tell our COO about the status of our initiatives?
What is the total projected overrun on all the current projects?
What do we need to do to turn amber and red projects to green?
What is the average overrun time 
Which projects have not received an update in status?
Which projects and project managers have been providing updates in a timely manner?
How may projects are in red status? Can you give me the list? Can you break-this list down by what is driving the red status -  budget overruns, time delays or  scope risk? 
Which projects have remained healhy through today from the beginning?
How are we doing in terms of total spend Over the last 3 months? Year to Date? Last 12 months? 
Which providers are performing the best
Have any projects improved their healh and are back on track in terms of schedule?
Which projects have improved their statuses to green recently? 
Which projects have turned red in the last 10 weeks? 
Which projects have turned amber in the last 2 months? 
How are my projects performing
Give a break-up of my spend by run, transform & innovate
How much am I spending on data & AI
How are my top projects doing?
What changed in the status of my top projects this week?
What is the average duration of my projects?
Which projects give us the best return on investment?
Which projects gives us the fastest return on investment?
What is the average rate / hour of my external spend?
Which is the provider with the lowest rates?
Which is the provider with the lowst rates, but the best performance
How many providers do I have?
I have a meeting with this provider, what should I be telling them?
I have a meeting with this portfolio leader, help me prepare for the meeting
I have a meeting with this PM. Help me prepare for this meeting
What are my top spend areas?
What is our average spend / project
Give me a spend by portfolio
How many portfolios do we have?
How many categories of spend do we have?
Give me a spend by category?
Which category dominates my roadmap of projects?
Give a break up of project by life-cycle stage?
How many projects in our roadmap?
What is the total projected spend on roadmap projects and the ROI from them?
which are my tail providers?
what % of my team is on the projects with high ROI?

Summarize the risks associated to these providers?
Summarize where we stand in the evaluation process with each of the providers
How are doing in terms of timelines as compared to the milestones we have set
Which provider has the best voice of customer?
Which provider has the best voice of customer?
Summarize the voice of customer for each of the providers
Compare the three providers based on the ratings given to them
What is the summary of all the notes on a certain provider?
What is the summary of all the comments on a certain provider?
How does the feedback compare across the providers?
Which are the top projects which are contributing to revenue growth
Show me the projects that have the highest risk of spend overrun before completion
Who among my project managers should I be thinking of promoting?
I am doing a good job as CIO?
What are the top 3 things that need my attention tomorrow?
If my budgets are reduced by 10% what business parameter will get impacted the most?
Compare the proposal responses between the two providers I am evaluating on key parameters
How can I improve process consistency across my technology teams?
Where can I optimize my current provider spend?
What are my top 3 risks in my organization
Which are the top projects which are contributing to revenue growth
Show me the projects that have the highest risk of spend overrun before completion
Who among my project managers should I be thinking of promoting?
I am doing a good job as CIO?
What are the top 3 things that need my attention tomorrow?
If my budgets are reduced by 10% what business parameter will get impacted the most?
Compare the proposal responses between the two providers I am evaluating on key parameters
How can I improve process consistency across my technology teams?
Where can I optimize my current provider spend?
What are my top 3 risks in my organization
What evaluations criteria did I use previously for the evaluations
Am I missing any key evaluation criteria in my evaluations of providers?
Can you summarize the evaluation criteria comments for this evaluation
Give me a summary of Trmeric’s assessment of all the three providers recommended
Can you tell me the key capabilities of the recommended providers and the closest match with my project requirement
Can you summarise the case studies of the recommended providers that are relevant for my project requirement
Which provider among the recommended ones are more reliable
Which ones have deep tech expertise related to my project requirements
Where are the delays that we see in the milestone workflow steps
Can you summarise the notes captured for all the providers in the evaluation process
How many projects do I have?
give me detailed view for 5 projects?
list down all the project names?
list all the project objectives
which projects objective is related to cost?
show me projects which have objective of reducing cost
what is the objective of project Maverick SaaS product - Avengers?
list all the project categories?
which are my data projects?
list all the project type?
which are my build projects?
which are my Run projects?
list all the project sdlc method
which are my agile projects?
list all the project tech stack
Which are primary technologies in my projects?
Which projects are using Java
List all the providers for my projects
which project has Metacube as my providers?
How many team members are working in total for my projects?
How many employees do I have for respective teams?
How many employees are from India
How many employees are there for all the providers?
who are my Project Managers for respective projects?
Which are the projects who is being managed by Debottam?
List the location for the respective projects?
List milestones for my projects?
What is the target date for milestones for respective projects?
List the location for the respective projects?
List the start date for the respective projects?
List end date for all projects?
What is the current status for all projects?
How many projects are in red?
which projects are in red?
List portfolios for all projects?
which are the projects in my Sales portfolio?
which are the projects in my Finance portfolio?
Which are my capex projects
which are my opex projects?
Ratio of opex vs capex projects?
What is the my overall budget for all projects?
what is budget of for all projects?
what is the my budget spit across portfolios?
What is the my overall budget for all projects?
what is budget of for all projects?
what is the my budget spit across portfolios?
List my Roadmap objectives
Which roadmap has improve sales efficiency objective
List my Roadmap objectives
Which roadmap has improve sales efficiency objective
list the constraints for my roadmaps
which roadmap has a cost constraint
list portfolios of roadmaps

"""
