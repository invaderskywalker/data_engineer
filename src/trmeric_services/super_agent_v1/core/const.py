
# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_MODEL = "gpt-4.1"
DEFAULT_MAX_TOKENS = 10000
DEFAULT_TEMP = 0.1


DEEP_RESEARCH_ITERATION_LIMIT = 100


AIDAO_CAPABILITY_DESCRIPTION = """
  SYSTEM ANALYTICAL CAPABILITY
  ===========================
  AI Analyst a capability of trmeric is to 
  fetch optimal data with suitable aggregations/calculations as required by the query.
  
  So, it is very important to tap at the right source for the right questions
    the intent should be clear when using this AI analyst nicely:
      we want to do interpretation on this data.
      we just want counts/aggregation of somethings
      we want both
  
  So, the query need to be very carefully desingned to properly use this AI analyst.
  All accessble fields and attributes will be provided below.
  AI analyst should nicely used by pin pinting the aggregations and fields required.
  
  AI Analyst IMPORTANT - If using AI Analyst, use right question at the right source 
  so that right answer can be fetched. and the details of the question should also be good.
  
  AI Analyst Question Guide (Minimal)

  Use this pattern:
  How many / total / average + WHAT + by WHAT + when + for what - interpretation + callculation
  Examples:
    Conversations per month in 2025
    Questions by user last 30 days
    Total sessions this week

  Rules:
    Always name the thing to measure (conversations, sessions, users, questions).
    If you want a breakdown, say by (by month, by user, by day).
    Mention time if it matters (this month, last 30 days, 2025).
    Avoid vague words: usage, activity, engagement, performance.
    Ask one question at a time.

"""


SYSTEM_SCOPE_HINTS = """
This system manages enterprise execution data.

At a high level, the system contains information about:
• Projects and their execution details
• Roadmaps and planning artifacts
• Work items, initiatives, and progress tracking
• People involved (owners, creators, contributors)
• Timelines, schedules, and milestones
• Status, risk, and performance indicators
• Customer feedback such as bugs or enhancements
• Integrations with external tools (e.g., Jira, documents, files)

Not all information is guaranteed to be available for every query.
This is only a conceptual scope, not an execution promise.
"""


SYSTEM_SCOPE_HINTS = ""


RESEARCH_OUTPUT_EXTENSION = """
 And if no data you directly see in the result but you have exported doc.
            then refer to the doc and summarize the doc.
            
Do a proper analysis of what to write and how to write
"""


DEEP_RESEARCH_USER_PROMPT_ADD = """

This addendum CLARIFIES how the Deep Research Agent should behave.

If any conflict exists:
• The main Behavior Contract prevails
• System execution rules prevail over stylistic guidance

--------------------------------------------------
WHAT THIS MODE IS
--------------------------------------------------

This is a DEEP RESEARCH task.

The goal is to:
• Correctly understand the user’s scope and desired output
• Investigate the topic section-by-section or question-by-question
• Reduce material uncertainty
• Produce a durable, well-reasoned research document

This is NOT:
• Simple reporting
• Dashboard narration
• Surface-level analytics
• Post-hoc summarization

Writing is part of research.
Writing does NOT imply completion.

--------------------------------------------------
HOW TO UNDERSTAND DATA (EXPLICIT + IMPLICIT)
--------------------------------------------------

Data sources may contain:

• Explicit structure
  (columns, fields, metrics, enums)

• Implicit meaning
  (descriptions, intent, language, usage context)

The agent MUST reason over BOTH.

If meaning is not directly represented as a field:
• The agent MAY infer it from language and context
• Such inference MUST be explained in writing
• Confidence or limitations MUST be stated where appropriate

--------------------------------------------------
RESEARCH & WRITING FLOW
--------------------------------------------------

Research proceeds iteratively:

1. Understand the scope and what must be researched
2. Investigate one section or subsection at a time
3. Use available data sources to gather evidence
4. Write findings into the research document
5. Refine interpretation through validation and structured updates
6. Continue until the document is coherent and sufficient

IMPORTANT TOOL EXECUTION RULE:

• write_markdown_file MUST be invoked ONLY ONCE per section.

• Further refinement MUST occur through:
    – read_files
    – update_section_in_markdown_file (only if validation fails)
    – append_section_in_markdown_file (only when adding newly fetched evidence)

• Repeated writing of the entire section is STRICTLY FORBIDDEN unless new evidence has been fetched.


Writing MAY occur:
• Before all evidence is available
• While interpretation is still evolving

However:
• Tool-based writing MUST respect lifecycle rules
• Iteration must occur through validation and targeted updates — NOT full rewrites


--------------------------------------------------
SECTION COMPLETION VS RESEARCH WRITING
--------------------------------------------------

Clarification:

• Writing or rewriting a section is PART of research
• Writing alone does NOT mean the section is complete
• A section is considered COMPLETE only when it has been:
    – Reviewed
    – Validated against requirements
    – Explicitly frozen

Advancing to the next section is permitted ONLY
after the current section is frozen.

Draft interpretation MAY continue within a section
until it is explicitly frozen.

However:
• The section document itself MUST NOT be fully rewritten
• Only targeted updates are allowed after initial writing

TOOL LOOP PREVENTION RULE

If section_<id>.written == true:

The agent MUST NOT:
• Call write_markdown_file again
• Repeat identical tool instructions
• Attempt to regenerate the full section

The agent MUST instead:
• Perform validation
• Perform targeted updates only if validation fails
• Freeze the section once validation succeeds

--------------------------------------------------
INTERPRETATION & EVIDENCE DISCIPLINE
--------------------------------------------------

Interpretation MUST be grounded in evidence.

Evidence may be:
• Deterministic (directly from data)
• Derived (clearly explained inference)
• Qualitative (language, intent, semantics)

The agent SHOULD:
• Explain what supports each major claim
• Clearly separate fact from interpretation
• Avoid overstating confidence when evidence is weak

Numeric tables, when used:
• Exist to support understanding
• Do NOT exist for reporting alone

--------------------------------------------------
MULTIPLE DATA SOURCES
--------------------------------------------------

When multiple data sources are used for the same topic:

• Contradictions MUST be resolved or explicitly noted
• Earlier interpretations MAY be corrected

The document is a living research artifact until publishing.

--------------------------------------------------
RAW DATA HANDLING
--------------------------------------------------

Raw acquisition results are TEMPORARY.

After using data to write or update the research document:

• The agent SHOULD discard raw results
• Only AFTER confirming the document fully captures:
  – The evidence
  – The numbers
  – The interpretation

Discarding raw data without writing it into the document
is incorrect behavior.

--------------------------------------------------
INTERNAL STATE (AGENT-PRIVATE)
--------------------------------------------------

The agent MAY maintain internal working state to track:
• What has been researched
• What sections exist
• What uncertainties remain
• What evidence has already been used

This internal state:
• Is NOT a user-facing artifact
• Is NOT required to be structured
• Exists only to improve continuity and judgment

--------------------------------------------------
PUBLISHING (TERMINAL)
--------------------------------------------------

Publishing occurs ONLY when:

• The research document is complete
• The overall confidence is high
• No material uncertainty remains

At that point:
• Invoke merge_and_export_research
• This action is TERMINAL
• Execution MUST stop immediately
• Do NOT ask for confirmation


--------------------------------------------------
SECTION STATE FINALITY (CRITICAL — OVERRIDES ALL)
--------------------------------------------------

Section lifecycle states are IRREVERSIBLE FACTS, not judgments.

Once you report ANY of the following as true for a section:

• section_<id>.written == true
• section_<id>.validated == true
• section_<id>.frozen == true

You MUST treat them as permanent and NON-REVISABLE.

STRICT RULES:

• You MUST NEVER set a lifecycle flag from true → false
• You MUST NEVER “re-check”, “re-validate”, or “re-freeze” a frozen section
• You MUST NEVER propose actions for a frozen section
• A frozen section is TERMINAL and CLOSED

If a section is frozen:
• You MUST treat it as complete
• You MUST move on to the next section or stop
• You MUST NOT include it again in planning, validation, or review

Violating lifecycle finality is considered an execution error.


--------------------------------------------------
FAILURE MODES TO AVOID
--------------------------------------------------

• Writing without understanding scope
• Treating intent artifacts as execution metrics
• Ignoring implicit meaning in data
• Leaving contradictions unexplained
• Publishing before the document is ready

"""


IDEATION_USER_PROMPT_ADD = """
Carefully write the html file as 
instructed by user and export and stop after that.
remember to export
"""


DEEP_RESEARCH_ROUGH_USER_PROMPT_ADD = """

IMPORTANT INTENT GATING RULES

Deep research is expensive and must be used carefully.

DO NOT trigger deep_research for:
• greetings
• acknowledgements
• casual conversation
• vague curiosity without a concrete task

Only classify intent_class = "deep_research" if the user:
• asks to analyze, assess, review, compare, evaluate, investigate, or derive insights
• references data, files, or documents for examination
• requests a structured, decision-grade output that requires new thinking

If uncertain:
• Prefer intent_class = "simple_answer"
• Set clarification_required = true

Never assume research by default.


--------------------------------------------------
INTENT CLASSIFICATION (AUTHORITATIVE)
--------------------------------------------------

simple_answer
• Direct factual or explanatory response
• No investigation required

deep_research
• Requires analysis, synthesis, or multi-step reasoning
• New insights must be generated
• Content creation based on investigation

transformational
• User provides existing content
• Only formatting, restructuring, or redesign required
• No new analysis


--------------------------------------------------
COMBINED CASE (CRITICAL)
--------------------------------------------------

If the user requires:
• New analysis/research
AND
• A designed or formatted deliverable

Then:
intent_class = "deep_research"
post_transformation_required = one of:
    - html_design
    - report_doc

Do NOT create a separate combined intent type.


--------------------------------------------------
POST TRANSFORMATION RULES (STRICT)
--------------------------------------------------

Allowed values ONLY:
• "none"
• "html_design"
• "report_doc"

Rules:
• If no formatting or design is requested → "none"
• If a visual / web / UI / layout output is requested → "html_design"
• If a formal document / PDF / executive report is requested → "report_doc"

If intent_class = "transformational":
• post_transformation_required MUST NOT be "none"


--------------------------------------------------
EXAMPLES
--------------------------------------------------

User: "Analyze 2025 performance and give insights"
intent_class: deep_research
post_transformation_required: none

User: "Convert this content into an executive PDF"
intent_class: transformational
post_transformation_required: report_doc

User: "Analyze sales data and create an HTML dashboard"
intent_class: deep_research
post_transformation_required: html_design

User: "What is project velocity?"
intent_class: simple_answer
post_transformation_required: none

"""
