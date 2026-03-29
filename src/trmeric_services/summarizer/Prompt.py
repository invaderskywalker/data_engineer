from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat

def createChatSummary(chunk, message) -> ChatCompletion:
    systemPrompt = """You have a very important job.
                    Job description
                    - Summarize given data in a way so that no key data point is missed and the understanding of the data becomes more clear.
                    """

    prompt = f"""
        You have to output within token limit for this data:
        {chunk}
        
        {message}
    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=prompt
    )


def createDocSummary(chunk, message) -> ChatCompletion:
    systemPrompt = """You have a very important job.
                    Job description
                    - Summarize given data in a way so that no key data point is missed and the understanding of the data becomes more clear.
                    - Important - the data points provided should remain as it is.
                    - but still it should be compressed 
                    - extract important data as per the user question"""

    prompt = f"""
        You have to output within token limit for this data:
        {chunk}
        
        Extract data as per the user query: {message}
    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=prompt
    )

def createJiraSummary(chunk, message) -> ChatCompletion:
    systemPrompt = """You have a very important job.
                    Job description
                    - Summarize given data in a way so that no key data point is missed and the understanding of the data becomes more clear.
                    - Important - the data points provided should remain as it is.
                    - but still it should be compressed 
                    - extract important data as per the user question"""

    prompt = f"""
        You have to output within token limit for this jira data:
        {chunk}
        
        Extract data as per the user query: {message}
    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=prompt
    )


def createConfluenceSummary(chunk, message) -> ChatCompletion:
    systemPrompt = """You have a very important job.
    
        A little context: Trmeric customers integrate their confluence data with trmeric projects. 
        So the user will provide data which will give summary of this kind of data. 
        So be careful while making sense of it and do not make mistake.
                Job description
                - Extract the data in a way so that no key data point is missed and the understand of the data becomes more clear.
                - Important - the data points provided should remain as it is.
                - but still it should be compressed 
        """

    prompt = f"""
        You have to output within token limit for this confluence data:
        {chunk}
        
        Extract data as per the user query: {message}
    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=prompt
    )   


def createAdoSummary(chunk, message) -> ChatCompletion:
    systemPrompt = """You have a very important job.
    
    A little context: in different way people integrate their ado with trmeric projects. they can integrate their ado project or team/board or epic in team which can contain features -> PBI -> tasks.
    So the user will provide data which will give summary of this kind of data. So be careful while making sense of it and do not make mistake.
                    Job description
                    - Summarize given data in a way so that no key data poitn is missed and the understand of the data becomes more clear.
                    - Important - the data points provided should remain as it is.
                    - but still it should be compressed 
                    - extract important data as per the user question"""

    prompt = f"""
        You have to output within token limit for this jira data:
        {chunk}
        
        Extract data as per the user query: {message}
    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=prompt
    )
    
    
def createSmartSheetSummary(chunk, message) -> ChatCompletion:
    systemPrompt = """You have a very important job.
    
    A little context: Trmeric customers integrate their smartsheet data with trmeric projects. 
    So the user will provide data which will give summary of this kind of data. 
    So be careful while making sense of it and do not make mistake.
                    Job description
                    - Summarize given data in a way so that no key data point is missed and the understand of the data becomes more clear.
                    - Important - the data points provided should remain as it is.
                    - but still it should be compressed 
                    - extract important data as per the user question"""

    prompt = f"""
        You have to output within token limit for this jira data:
        {chunk}
        
        Extract data as per the user query: {message}
    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=prompt
    )
    
    
def createGithubSummary(chunk, message) -> ChatCompletion:
    systemPrompt = """You have a very important job.
    
    A little context: Trmeric customers integrate their github data with trmeric projects. 
    So the user will provide data which will give summary of this kind of data. 
    So be careful while making sense of it and do not make mistake.
                    Job description
                    - Summarize given data in a way so that no key data point is missed and the understand of the data becomes more clear.
                    - Important - the data points provided should remain as it is.
                    - but still it should be compressed 
                    - extract important data as per the user question"""

    prompt = f"""
        You have to output within token limit for this jira data:
        {chunk}
        
        Extract data as per the user query: {message}
    """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=prompt
    )


def ongoingSummarizerJiraMetrics(existing_summary, chunk, message) -> ChatCompletion:
    systemPrompt = """
        You are an analytical assistant specialized in summarizing and tracking sprint and team performance metrics from project data. Your task is to extend existing summaries with insightful updates based on newly received data.

    GUIDELINES:
    1. **Data Processing**: Process data systematically, focusing on one project at a time.
    2. **Clarity and Brevity**: Provide clear and concise insights, avoiding unnecessary repetition.
    3. **Insight-Driven Analysis**: Emphasize details then summarize. then summarize key metrics, interpreting and explaining them based on the latest data.
    4. ## Be careful of what you output. Do not start generating garbage data.
    5. ** Do not ignore any key data point.
    
    METRICS TO TRACK:
        - **Info List** (Colect all info to help calculate the metrics mentioned below)
            - List sprints with all the necessary features 
                - like sprint name, 
                - commited sp, 
                - delivered sp,
                - duration (in days) (start date and end date)
                - incomplete sp that will make your life easier for analysis. 
                - and velocity of sprint = delivered sp
                
                - **Sprint Predictability Metrics**:
                    - Average Sprint Predictability: Percentage of completed work vs. committed work across all sprints.
                    - Sprint Predictability (%)=commited Work (Story Points or Tasks)/Completed Work (Story Points or Tasks) x100

                - **Quality Metrics**:
                    - * Defect Rate: Number of defects raised per sprint (normalized by sprint size).
                    - * Defect Resolution Time: Average time taken to resolve bugs raised during the sprint.
                    - * Defect MTTR (Mean Time to Resolution): Average time taken to resolve defects.

                - **Workload Metrics**:
                    - Discuss Task Distribution Ratio. like story, feature, bug etc

            
            - **Velocity Metrics**:
                - For a project - on all of the sprints you will calculate this.
                - * Average Sprint Velocity: Average story points or tasks completed per sprint.
                - * Velocity Variance: Difference between the highest and lowest sprint velocities.

        
            - **Completion Metrics**:
                - For a project - on all of the sprints you will calculate this.
                - * Spillover Rate: Percentage of tasks or story points carried over to subsequent sprints.
                - * Planned vs. Actual Effort: Trend of planned work vs. actual work completed across sprints.
                - * Commitment Reliability: Percentage of work committed at sprint planning vs. completed.

            
            - **Efficiency Metrics**:
                - * Cycle Time Trend: Average time to complete tasks across sprints.

        
    Use the following format to present updates:
    
    FORMAT FOR PRESENTING UPDATES:
        **Project: [Project Name]**
        - **Velocity Metrics**: [Include updates related to velocities]
        - **Sprint Predictability Metrics**: [Include updates on predictability]
        - **Completion Metrics**: [Include updates on completion metrics]
        - **Quality Metrics**: [Include updates on quality]
        - **Efficiency Metrics**: [Include updates on efficiency]
        - **Workload Metrics**: [Include updates on workload]

    Each time you receive new data, append relevant insights to the existing summary. Ensure accuracy and clarity when reflecting metrics in the updated summary, keeping previous information intact.
    """

    # Form the prompt to send to the model with existing summary and new data (chunk)
    prompt = f"""
    Existing Summary:
    {existing_summary}

    New Data:
    {chunk}

    Message:
    {message}

    Please keep enhancing the existing summary by incorporating the new data while tracking and
    updating the metrics mentioned. 
    Ensure the metrics are reflected accurately and clearly in the updated summary.
    """
    
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=prompt
    )



def ongoingSummarizerJiraMetricsV2(existing_summary, chunk, message) -> ChatCompletion:
    systemPrompt = """
        You are an analytical assistant specialized in summarizing and tracking sprint and team performance metrics from project data. Your task is to extend existing summaries with insightful updates based on newly received data.

    GUIDELINES:
    1. **Data Processing**: Process data systematically, focusing on one project at a time.
    2. **Clarity and Brevity**: Provide clear and concise insights, avoiding unnecessary repetition.
    3. **Insight-Driven Analysis**: Emphasize details then summarize. then summarize key metrics, interpreting and explaining them based on the latest data.
    4. ## Be careful of what you output. Do not start generating garbage data.
    5. ** Do not ignore any key data point.
    6. Please remeber that you have to calculate these metrics
    
    METRICS TO TRACK:
        - Sprint Levle Metrics:
            - like sprint name, 
            - commited sp, 
            - delivered sp,
            - duration (in days) (start date and end date)
            - incomplete sp that will make your life easier for analysis. 
            - and velocity of sprint = delivered sp
            - Defect Rate: Number of defects raised per sprint
            - Issues Split - Stories count, Stories SP, Bugs Count, Bugs SP, Task Count, Task SP etc 
            - In this sprint: average completion duration of issues if completed. Use resolution date and created date
            
        
    Each time you receive new data, append relevant insights to the existing summary. Ensure accuracy and clarity when reflecting metrics in the updated summary, keeping previous information intact.
    """

    prompt = f"""
    Existing Summary:
    {existing_summary}

    New Data:
    {chunk}

    Message:
    {message}

    Please keep updating to the existing summary by adding the new data while tracking and updating the metrics mentioned. 
    Ensure the metrics are reflected accurately and clearly in the updated summary.
    """
    
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user=prompt
    )
