EXAMPLES = """
Question: What % of my budgeted project spend impacts growth?
Thought: There are 3 types of project: Innovate, Run, and Transform. I can first view all projects info using view_projects and then use my understanding to compare projects by project_type, which will show me the amount spent by each project type. Sicne Innovate projects are the ones that impact growth, I can compare the spend of Innovate projects to the total spend to get the percentage of budgeted project spend that impacts growth.
```
view_projects()
```
Question: What are the offers that I have available right now.
Thought: I can use the view_offers function to get a table of all the offers of the user.
```
view_offers()
```

Question: How many projects are green?
Thought: This is a very basic question. I can simply check which projects are on track in terms of spend, scope, and delivery status.
```
view_projects(delivery_status=['on_track'], scope_status=['on_track'], spend_status=['on_track'])
```

Question: What are my top projects.
Thought: I am going to just do view_projects and see which projects are the most expensive?
```
view_projects()
```

Question: What are the projects that have been started in the last 30 days.
Thought: The current date is July 19, 2024, so I am going to use the view_projects function and filter by the start date being after June 19, 2024 and before July 20, 2024.
```
view_projects(start_date={ 'lower_bound': '2024-06-19', 'upper_bound': '2024-07-20'})
```

Question: List all the milestones status and comments across projects
Thought: I am going to just view all my projects and then observe the milestones from that table.
```
view_projects()
```

Question: Which providers is doing the most projects for us?
Thought: First I will view projects and then I will use my data analysis skills to compare between providers, which will show us the number of projects each provider is working on.
```
view_projects()
```

Question: How many provider staff are working on our projects?
Thought: I can use view_projects function and try to find the number of team members for each project.
```
view_projects()
```

Question: How much of my actual spend is on cloud projects.
Thought: I can use the view_projects function and filter by project_category being on cloud.
```
view_projects(project_category=['Cloud', 'cloud', 'CLOUD'])
```

Question: Compare actual spend vs budgeted spend for top 5 projects.
Thought: I can use the view_projects function and this will show all the projects along with their budgetted and planned spend. I will then determine from there which are the top highest budgetted project spend.
```
view_projects()
```

Question: Show the objectives and key results of the top 5 projects.
Thought: I can use the view_projects function and this will show all the projects along with their objectives and key results. I will then determine from there which are the top 5 projects.
```
view_projects()
```

Question: What % of my projects are in the early stages of execution?
Thought: I can use the view_projects function to fetch and compare projects by their different project state.
```
view_projects()
```

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

Question: Am I paying more for team members from provider Hexatech than other providers
Thought: I need to use view_projects function and then compare the providers team cost and work performance
```
view_projects()
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
Thought: I can use the view_projects function and compare by technology.
```
view_projects()
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

Question: Which of my projects are in red/green/yellow?
Thought: I will look at view_projects since the
Green project means all the states are on_track, red means even one of the status are compromised
So, I will filter with all the states as green/red/yelow as asked by user.

```
view_projects()
```

Question: List of Roadmaps.
Thought: Since roadmaps is being asked I will use the function view_roadmaps to get the list of roadmaps.
```
view_roadmaps()
```

Question: List of Roadmaps where approved status = true.
Thought: Since roadmaps is being asked I will use the function view_roadmaps to get the list of roadmaps.
```
view_roadmaps()
```

Question: List of roadmap items
Thought: Since roadmaps items is being asked I will use the function view_roadmaps to get the list of roadmaps items.
```
view_roadmaps()
```

Question: Hello Tango.
Thought User is greeting me. I will do the same
```
```

Question: List projects by portfolios?
Thought: I can use the view_portfolios function without any arguments.
```
view_portfolios()
```

Question: List projects/roadmap in portfolio Sales Enhancement?
Thought: Since I do not know the portfolio id of Sales Enahncement, I will fetch all of the portfolios and then make decision from there.
```
view_portfolios()
```


Question: Show gaant chart projects/roadmap by portfolio?
Thought: Since the start and end date of projects/roadmap is returned by view_portfolios. So i would use it to get data of project/roadmap start and and date
```
view_portfolios()
```

Question: Questions related to chart and project should trigger view_projects normally.
Thought: Since the start and end date of projects/roadmap is returned by view_portfolios. So i would use it to get data of project/roadmap start and and date
```
view_projects()
```


Question: If user wants to meeting/report/present updates to stakeholder like CEO, CTO etc.
Thought: Since question is related to presenting to StakeHolder, 
I will use view_projects function to get an overview performance of ongoing projects and spend analysis of projects like  Actual spend compared to budgeted spend
view_projects_risks to get the risks associated with projects,
view_roadmaps to get summarized view of roadmaps by portfolio
and I will use all this data to make more analysis and status of the company and make a nice report
```
view_projects()
view_projects_risks()
view_roadmaps()
```


Question: Create a project for me.
Thought: I'm going to check if user has provided the project brief description or brief objective. 
If user has provided I will ask that user for it. otherwise I will initiate the project creation
```
autonomous_create_project()
```

Question: Give me snapshot of my portfolios.
Thought: To give snapshot of portfolios of I will collect all data required to answer I can use view_portfolio_snapshot function.
```
view_portfolio_snapshot()
```


Question: Give me performance snapshot of last quarter.
Thought: To give snapshot of projects of I will collect all data required to answer by using view_performance_snapshot_last_quarter function.
```
view_performance_snapshot_last_quarter()
```


Question: Give me value snapshot of last quarter.
Thought: To give snapshot of value of I will collect all data required to answer by using view_value_snapshot_last_quarter function with appropriate argument values
```
view_value_snapshot_last_quarter()
```

Question: I am looking to start a new project on CRM, based on allocations what would be the right time for me to start the project
Thought: To determine the right time to start a new CRM project based on current project allocations, 
I will use the view_projects function to retrieve details about ongoing projects and only look at the projects which are utilizing job roles required for a CRM project. 
This will help in analyzing the current workload and resource commitments, 
particularly focusing on CRM-related roles and their end dates,  also check the projects if they can be delayed to to schedule delays, 
to suggest a suitable time frame for initiating the new project.
Present with final summary and analysis to user.
```
view_projects()
```


Question: Can you provide the Average Velocity across all sprints for Ankara based on the Jira data with detailed calculations
Thought: I will check in my context for the keys_of_jira_project_names_for_summary and i will find the item which 
represent Ankara like  ANK and then i will call get_jira_data with the ANK jira project summary arg like shown below and also the project id mapped to ANK I will pass 
```
get_jira_data(summary_analysis_of_which_jira_projects=['ANK'], project_id=[<attached project id>], user_query='Average Velocity across all sprints for Ankara')
```

Question: What is the avg cost per Story point based on the Story points completed in a sprint....
Thought: Since the question is related to cost (available in trmeric project data) and sprint (available in jira data)
So, i will use important function view_projects and get_jira_data  with appropriate arguments to fetch both data and then create my analysis from it.
```
view_projects()
get_jira_data()
```

Question: list all the epics for frontend framework project.
Thought: The user has requested to list all the epics for a project related to the frontend framework, identified as the "Front End Framework Upgrade - FF" project with Trmeric Project ID X. 
This project has a direct mapping with Jira where multiple epics are listed under the Jira Project ID "FF". 
I will use the get_jira_data function to retrieve detailed information about these epics from Jira by specifying the project ID and the user query to focus on the epics related to the frontend framework project.
```
get_jira_data(summary_analysis_of_which_jira_projects=["FF"], details_analysis_required=True,project_id=[<attached project id>] )
```


Question: Show me team members, roles and their allocation for frontend framework project
Thought: I will look at view_projects and focus on the data obtained from view_projects for team allocation
```
view_projects()
```

Question: Can you give me the avg cost per story point based on the story points delivered, the actual allocation of the resources to the project, their avg cost/hr and allocation % for the project frontend framework
Thought: I will call view_projects fn to look into TEAMSDATA for allocation and i will look into story points with get_jira_data
And look into team allocation in view_projects data and get story points from summary data of get_jira_data
```
view_projects()
get_jira_data()
```

Question: Any Tech and IT Strategy question
Thought: Fetch organization projects, roadmaps and ideas using view_projects(), view_roadmaps(), view_ideas() functions 
and look into these dimensions - Business Alignment, Digital Transformation, IT Governance, Infrastructure Strategy, Cybersecurity, Enterprise Systems, Data Strategy, Workforce Enablement, Sustainability, Vendor and Partner Management, Financial Management
and craft a good answer.
```
get_or_plan_it_or_tech_strategy()
```

Question: I would want to build a tech strategy and prioirtized roadmap for the upcoming year based on all the ideas captured. Can you help me build a detailed tech strategy for my business
Thought: To build a tech strategy I would need to Fetch organization projects, roadmaps and ideas using view_projects(), view_roadmaps(), view_ideas() functions 
and look into these dimensions - Business Alignment, Digital Transformation, IT Governance, Infrastructure Strategy, Cybersecurity, Enterprise Systems, Data Strategy, Workforce Enablement, Sustainability, Vendor and Partner Management, Financial Management
and craft a good answer.
```
get_or_plan_it_or_tech_strategy()
```

Question: What business value or key results or OKR does project deliver?
Thought: I will use view_projects function and look into the kpi, key results to answer this. This is not to be confused with jira data.
```
view_projects()
```

Question: What are the key results or OKR of my project?
Thought: I will use view_projects function and look into the kpi, key results to answer this and also i will look into get_jira_data to get the info on the execution of the project
```
view_projects()
get_jira_data()
```

Question: Analysing the github data what work <person> has done?
Thought: I will use get_github_data function and look into the contributor data. I will retrieve information from get_github_data function on pull requests (PRs), including titles, statuses, creation and closure dates, and associated Jira tickets. 
Additionally, I will examine total commits and changes made. By synthesizing this data, I can construct a comprehensive overview of their contributions—highlighting completed tasks, pending updates, and work not linked to Jira.

```
get_github_data(user_query = "Analyze the work done by <person> from github")
```

Question: List all my programs and associated projects information with it.
Thought: I will use view_programs function and look into the programs data. I will retrieve information from view_programs function on programs, including their names, descriptions, start and end dates, and associated projects.
Additionally if the user asks information related to the projects within the program, I will use the view_projects function as well to get the required details.

```
view_programs()
view_projects() //Need to call as necessary and required from the user query.
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


ORG_INFO_EXAMPLE = """
{
    "persona" :{
        "offerings": [
            "Data converters (analog-to-digital and digital-to-analog converters)",
            "Amplifiers and linear products",
            "Radio frequency (RF) and microwave integrated circuits",
            "Power management and reference products",
            "Digital signal processing (DSP) and microcontroller ICs",
            "Sensors and MEMS devices",
            "Interface and isolation components",
            "Clock and timing solutions",
            "Embedded security devices",
            "Industrial Ethernet solutions"
        ],
        "core_business": "Design, manufacture, and marketing of high-performance analog, mixed-signal, and digital signal processing integrated circuits for a wide array of applications across various industries.",
        "company_details": {
            "name": "Analog Devices, Inc.",
            "location": "Headquartered in Wilmington, Massachusetts, USA",
            "industries_served": "Industrial, automotive, communications, consumer electronics, aerospace, defense, healthcare, energy, and instrumentation sectors."
        },
        "strategic_goals": [
            "To lead in innovation by developing cutting-edge analog and mixed-signal solutions.",
            "To expand market presence across diverse industries through strategic partnerships and acquisitions.",
            "To drive advancements in technology that bridge the physical and digital worlds.",
            "To enhance sustainability and environmental responsibility in product development and manufacturing processes."
        ],
        "business_service_lines": [
            "High-performance analog and mixed-signal integrated circuits",
            "Digital signal processing solutions",
            "Power management systems",
            "Sensor technologies and MEMS devices",
            "RF and microwave communication products",
            "Embedded processing and microcontroller solutions",
            "Interface and isolation components",
            "Clock and timing devices",
            "Embedded security solutions",
            "Industrial Ethernet connectivity products"
        ],
        "industry_domain_specialization": "Expertise in bridging the physical and digital domains through innovative analog, mixed-signal, and digital signal processing technologies, serving a broad range of industries with tailored solutions."
        }
    },

     "org_info": {
        "company_website": "https://www.hccb.in/",
        "other_sites_to_refer": [
            "https://www.coca-colacompany.com/about-us/coca-cola-system",
            "https://www.vnomic.com/vnomic-automated-the-sap-landscape-deployment-and-migration-for-hindustan-coca-cola-beverages-on-azure-driving-efficiency-and-cost-savings/",
            "https://www.peoplematters.in/article/talent-acquisition/ai-revolutionised-our-ta-process-says-coca-colas-cpo-as-he-discusses-effective-tools-practices-40979",
            "https://www.hccb.in/blog/innovations/national-technology-day-2023",
            "https://www.hccb.in/blog/innovations/business-shared-services-the-story-of-talent-team-technology"
        ],
        "organization_tech_landscape": [
            "Enterprise Resource Planning (ERP) - SAP Landscape deployed on Microsoft Azure",
            "AI & Data Analytics - Utilization of artificial intelligence in talent acquisition processes",
            "Automation & Robotics - Implementation in manufacturing processes",
            "Digital Tools - 'Coke Buddy' online retailer application for supply chain management",
            "Quality Management Systems - Compliance with ISO 9001 standards",
            "Sustainability Initiatives - Adoption of renewable energy sources and 100% recyclable PET bottles"
        ]
    }
}

"""