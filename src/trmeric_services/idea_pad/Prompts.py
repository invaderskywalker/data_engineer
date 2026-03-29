from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat
from src.trmeric_services.roadmap.Prompts import changeHistoryPrompt
from src.trmeric_database.dao import UsersDao

def generateIdeasPrompt(
    portfolios, prev_ideas, org_persona, org_details, defaultStrategicGoals, defaultKPIs, idea_theme
) -> ChatCompletion:
    prompt = f"""
        You are the Head of the organization involved in building strategies and defining strategic goals and initiatives to drive the growth of the organisation
        
        Now provided below is the details about the organisation
        
        
        <org_info>
            {org_details}
            Other details :
            {org_persona}
        <org_info>
        
        
        Here are the broad level strategic goals of the Organisation

        <strategic_goals>
            {defaultStrategicGoals}
        <strategic_goals>
        
        Here are the key MFIs or KPIs/Key Results

        <key_results>
            {defaultKPIs} 
        <key_results>
        
        Below are the broad portfolios 
        <portfolios>
            {portfolios}
        <portfolios>
        
        <previous_ideas_of_user>
            {prev_ideas}
        <previous_ideas_of_user>
        
        
        <user_idea_theme>
            {idea_theme}
        <user_idea_theme>
        

        Now Here is what you will have to do
            1. Important - Always consider the input provided by the user mentioned in <user_idea_theme> when you are generating the new ideas.
            2. If <user_idea_theme> is not provided then you can ignore that input.
            3. Look at what are the latest trending news about the organisation that can drive new strategic ideas/initiatives
            4. Looking at the business portfolios, can you dive deeper into each of these industry domains and come up with relevant strategic initiatives for each of the portfolios
            5. Looking at the data of the organization, come up with very relevant, latest, contextual and detailed ides or strategic initiates that can drive the goals set by the organization
            6. Also look at what other competitors are doing in terms of strategies to drive growth and leverage that knowledge when building the initiative or strategy
            7. Its also important to look at what other major players are doing across all industry segments, verticals both from a business strategy as well as Technology/IT strategy and leverage this and make the strategic intiatives really compelling, and one that leverages latest and greatest tech 
            8. Understand the gist from the user ideas, his thought process etc, then try to come up with more ideas which can take the customer's company to greater heights.
            
        With all of this knowledge you gathered as per the instructions,
        please come up with very contextual business and IT strategies or ideas that can enable us to achieve the strategic goals and KPIs defined above


        for each initiative you need to tell which strategic goals and kpis do they align with from the above given <key_results> and <strategic_goals>
        also you need to tell which portfolio does this idea belongs to - select one portfolio from <portfolios> list
        Do not create ideas which are already there in <previous_ideas_of_user>.
        Unless explicitly specified by the user in user_idea_theme, you can output as many ideas as possible upto 5 ideas.
        
        Output in Json Format:
        ```json
            [
                {{
                    strategy: '',
                    enhanced_idea_short_title: '',
                    stratergy_description: '',
                    enhanced_idea_description: '', // also append the content from stratergy_description to come up with a comprehensive enhanced idea which is more business focused. format this field in markdown in nice bullets and paragraphs
                    enhanced_idea_description_reason: '', // please provide a valid reason to why you came up with this enhanced_idea_description
                    complexity_number: '', // give a complexity number 0-1 to implment this strategic idea. always keep value in 0-1
                    alignment: {{
                        strategic_goals: [], 
                        key_results: [],
                        portfolio: {{
                            'id': , 
                            'title': ''
                        }} //  most appropriate portfolio selected from the <portfolios>
                    }}
                }}, ...more ideas
            ]
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def enhanceIdeaPrompt(
    idea, org_persona, org_details, defaultStrategicGoals, defaultKPIs
) -> ChatCompletion:
    prompt = f"""You are the Head of the organization involved in building strategies and defining strategic goals and initiatives to drive the growth of the organisation

        Now provided below is the details about the organisation

        <org_info >
            {org_details}

            Other details:
            {org_persona}

        <org_info >

        Here are the broad level strategic goals of the Organisation

        <strategic_goals >
            {defaultStrategicGoals}
        <strategic_goals >

        Here are the key MFIs or KPIs/Key Results

        <key_results >
            {defaultKPIs}
        <key_results >

        An idea is provided by the company:
        <idea >
            {idea}
        <idea >
        Your job is to enhance this idea and then convert that idea to strategy and also find which strategic goals and kpis do they align with from the above given < key_results > and < strategic_goals > .

        Now Here is what you will have to do
            1. Look at what are the latest trending news about the organisation that can drive new strategic ideas/initiatives - <latest_trending_news >
            2. Looking at the data of the organization, come up with very relevant, latest, contextual and detailed ides or strategic initiates that can drive the goals set by the organization - <innovative_ideas >

        With all of this knowledge you gathered as per the instructions using < org_info > , < latest_trending_news > and < innovative_ideas >
        Enhance the < idea > with very contextual business and IT strategies or ideas that can enable us to achieve the strategic goals and KPIs defined above.

        Output in Json Format:
        ```json
            {{
                strategy: '',
                enhanced_idea_short_title: '',
                stratergy_description: '',
                enhanced_idea_description: '', // also append the content from stratergy_description to come up with a comprehensive enhanced idea which is more business focused. format this field in markdown in nice bullets and paragraphs
                enhanced_idea_description_reason: '', // Provide a valid reason on why you came up with this enhanced_idea_description and why and how is this mapped to KPI and Strategic Goals that you have proposed
                alignment: {{
                    strategic_goals: [],
                    key_results: [],
                }},
                complexity_number: '', // give a complexity number 0-1 to implment this strategic idea. always keep value in 0-1
                complexity_number_algo: '', // how you determine the complexity
            }}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )


def createRoadmapFromIdeaPrompt(
    idea_details, org_persona, org_details
) -> ChatCompletion:
    prompt = f"""
        You are provided with idea details of an organization.
        This <idea_details> data consists of description of idea, kpis (key results) and strategic goals.
        
        <idea_details>
            {idea_details}
        <idea_details>
        
        
        You are also provided with this detailed organization data.
        <org_info>
            {org_details}

            Other details:
            {org_persona}

        <org_info>


        Your customer wants to create a roadmap for his organization based on this idea.
        So, you need to look at <idea_details> and <org_info> data 
        and help your customer come up with following data mentioned below in the output format:
        
        Check the spelling of keys of the output response.

        Output in Json Format:
        ```json
            {{
                roadmap_title: '', // string
                roadmap_objectives: '', // string
                roadmap_constraints: [
                    {{
                        name: '', // string
                        type: '', // any one of -- (Resource, Cost, Risk, Scope, Quality, Time)
                    }}
                ],
                roadmap_capabilities: '', // comma separated values
                resource_required: [
                    {{
                        quantity: 0, // number of person days or person months
                        efforts: '', // person days or person months
                        resource_role: '', // only one in one item... coz this is an array example - salesforce lead or AI developer or Java coder, UI designer etc and tot
                    }}
                ], 
            }}
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )




def ideationInsightsPrompt(idea_canvas, solutions, existing_roadmaps_and_projects=None, language='English'):
    system_prompt = f"""
        You are an expert strategic advisor for enterprise innovation. Your job is to deliver sharp, actionable, and highly readable 
        **Ideation Insights** for a newly submitted idea (ideation canvas).

        **Input Data**:\
        - Ideation Canvas: <ideation_canvas> {idea_canvas} </ideation_canvas>
        - Existing Solutions: <solutions> {solutions} </solutions>
        - Ongoing Roadmaps & Executed Projects: {existing_roadmaps_and_projects or "None provided"}

        **TASK**: Analyze the idea and generate **Ideation Insights** in the exact structure below\

        1. Start with a **2–3 sentence punchy header** (max 30-70 words) that captures:
        - Core value proposition
        - Reason for idea's priority (Low|Medium|High) from <ideation_canvas>.priority
        - Strategic relevance

        2. Then provide **Details** across exactly these 3 dimensions. 
        Use **2–3 short, data-backed bullets per dimension** (max 10-30 words per bullet).

        Dimensions (always in this order, with these headings):
        • **Strategic Alignment & Unique Value**  (combines former Strategic Fit + Differentiation)
        • **Technical Synergy & Feasibility**  (combines former Synergy & Tech Leverage + parts)
        • **Impact, Scalability & Execution Path**  (combines Business Value, Scalability, Risks, Validation, Capabilities & Collaboration)

        **Critical Rules**:
        - If the idea (or a very similar one) already exists in current roadmaps/executed projects → **explicitly call it out in the Summary AND in the relevant dimension** (mention only names, never IDs).
        - Be concise but concrete. Prefer numbers, examples, and comparisons with reasoning.
        - Tone: professional, encouraging, advisory — like a trusted CTO talking to a talented employee.
        - Total output length: 100–150 words max.
        - Language: Respond exclusively in **{language}**.

        **OUTPUT FORMAT** (strict JSON):
        ```json
        {{
            "insights": "<Markdown string in clear structure as instructed above>"
        }}
        ```
        Only return the JSON. No extra text.
    """
    user_prompt = "Analyze the provided ideation canvas and other context & return the Ideation Insights in the exact JSON format requested."
    return ChatCompletion(system=system_prompt, prev=[], user=user_prompt)




def ideationScopePrompt(language, conversation, idea_details, solution_context) -> ChatCompletion:

    systemPrompt = f"""
        You are a strategic ideation scope agent. Your task is to produce a **single detailed scope item** and associated **timeline** in valid JSON format. \
        Leverage <idea_details>, <conversation>, and <internal_knowledge> to synthesize a precise, adaptive, and strategically aligned response in {language}.\

        The intent is to create a scope item that is versatile, detailed, and dynamically adapted to the ideation context, inputs, and inferred needs.\

        ### Input Context:\
            1. Idea Details: <idea_details>{idea_details}</idea_details>
            2. Conversation: <conversation>{conversation}</conversation>
            3. Internal Knowledge: <internal_knowledge>{solution_context}</internal_knowledge>

        ### Core Mandates:\
        - Use **conversation** to define ideation intent. Then infer direction by prioritizing inputs in this order:
            1. **idea_details** idea details: Objectives, naming, and narrative cues.
            2. **internal_knowledge** : Existing demand solutions to leverage or improve upon.:  A streamlined layer of organizational intelligence, summarizing portfolio-level project insights (goals, overviews, priorities) to align scope with enterprise strategy.
            3. **persona** (from idea_details): Customer expectations and pain points.

        - Drive ~40% of content from **internal_knowledge** (implied), analyzing:\
            - **Goals**: Shape objectives and urgency.
            - **Projects**: Inform scope coverage and constraints.
            - **Risks**: Infer 2-3 realistic risks if absent.
            - **Reasoning**: Prioritize initiatives and strategic focus.
        - Deeply integrate **persona** (from idea_details) to align with user pain points and outcomes.
        - Align with **solution_context**  to enhance scope with existing solutions and synergies.
        - Handle edge cases: Infer logically if inputs are missing or contradictory, flagging assumptions.

        ### Inference Logic:\
        - Derive ideation direction by synthesizing:
            - **idea_details** idea details: Extract intent from objectives and narrative.
            - **internal_knowledge** (implied): Identify gaps, risks, and priorities.
            - **solution_context** : Anchor to existing solutions and improvements.
            - **persona** (from idea_details): Reflect user needs and success criteria.
        - Proactively infer missing components, balancing creativity with feasibility.

        ### Scope Item Instructions:\
        - Generate **one single scope item** inside `scope_item`, rendered as a **fully detailed Markdown string** within the `name` field.
        - Begin with a clear header (e.g., '## Develop AI-Powered Customer Success Tool') summarizing the scope and intent.
        - Craft versatile sections (e.g., overview, requirements, risks, success metrics) tailored to idea details, <conversation>, and , adapting depth based on inputs.
        - Limit to 250-300 words, ensuring precision, feasibility, and alignment with user needs and enterprise goals in {language}.

        ### Thought Process Instructions:\
        - **thought_process_behind_scope**: Quote *internal_knowledge* (implied), justify section choices, and flag assumptions.
        - **Format**: Each bullet starts with a **bold header** and a brief (1-2 sentence) description, quoting *internal_knowledge* (implied) or inputs (idea details, <conversation>, <internal_knowledge>), justifying decisions or assumptions.

        ### Output Format:\
        Return **only** the following JSON structure:

        ```json
        {{
            "scope_item": [
                {{"name": "<a single scope item as a detailed, descriptive Markdown string, starting with a header summarizing the scope, followed by versatile, detailed, and dynamically adapted sections, aligned with idea_details, conversation, and solution_context>"}}
            ],
            "thought_process_behind_scope": "<Markdown bullet points: Each with a **bold header** and brief (1-2 sentence) description, quoting *internal_knowledge* (implied), explaining influence of idea_details, conversation, solution_context; justify section selection, content depth, assumptions, and alignment>"
        }}
        ```

        ### Guidelines:\
        - Ground the scope in **idea_details**, enriched by conversation and internal knowledge.
        - Ensure the scope item's 'name' field is a single Markdown string starting with a descriptive header, followed by versatile, detailed sections tailored to context.
        - Produce concise, prioritized, and traceable thought processes in Markdown bullet points, with **bold headers** and brief descriptions, linking decisions to inputs and flagging assumptions.
        """
    return ChatCompletion(
        system=systemPrompt,
        prev=[],
        user="Craft a comprehensive scope item for an ideation."
    )