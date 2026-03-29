import traceback
from src.api.logging.AppLogger import appLogger
# from src.database.dao import TangoDao, TenantDao
# from src.ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_services.reinforcement import core

TANGO_MEM_FEATURES = ["tango"]

def tango_mem_criteria(user_id:int, feature_name:str, streaming: bool) -> bool:
    
    if not feature_name:
        return False
    return (user_id is not None and feature_name in TANGO_MEM_FEATURES and streaming)

def _get_tango_mem_insights(user_id:int =None,last_days:int=5):
    """
    Fetch and format recent user insights from Tango Memory to reinforce consistent, personalized behavior.
    These insights are derived from past conversations and captured patterns (goals, preferences, pain points, priorities, etc.).
    They help the agent stay aligned with the user's evolving needs, style, and feedback over time.
    """
    if not user_id:
        return ""
    tangomem_insights = ""
    try:
        from src.utils.knowledge.TangoMemory import TangoMem
        tango_mem = TangoMem(user_id).tango_memory_insights_for_rl(last_days=last_days)
        if tango_mem:
            tangomem_insights = f"\nRemember these insights about the user:\n{tango_mem}"
    except Exception as e:
        print(f"Warning: Failed to load Tango Memory insights:{e} {traceback.format_exc()}")

    return tangomem_insights

    
def _optimize_prompt(raw_prompt, tenant_id, agent_name, feature_name,section=None,subsection=None, limit=1,user_id:int=None, streaming:bool = False):
    # print(f"\n--debug _optimize_prompt: {agent_name}/{feature_name}/{section}/{subsection}---")

    rl = core.ReinforcementLearning()
    delta_prompts = rl.get_delta_prompts(tenant_id=tenant_id,feature_name=feature_name,agent_name=agent_name,section=section,subsection=subsection,user_id=user_id,limit=limit)
    print("--debug delta_prompts added: ",len(delta_prompts))
    if not delta_prompts:
        return raw_prompt.strip()

    latest = delta_prompts[0]
    delta_text = latest['delta_prompt'].strip()
    metadata = latest.get('metadata', {})

    lines = [line.strip() for line in delta_text.split("\n") if line.strip()]
    rules = [line for line in lines if line.startswith("RULE:")]
    # insights = [line for line in lines if not line.startswith("RULE:")]
    signals = [line for line in lines if not line.startswith("RULE:")]

    instruction_blocks = []


    # INTERNAL REINFORCEMENT (NON-VERBAL)
    if rules or signals:
        internal_block = ["## INTERNAL QUALITY SIGNALS"]

        if rules:
            internal_block.append("Reinforcement rules to guide response behavior:")
            internal_block.extend(sorted(rules))

        if signals:
            internal_block.append("Additional quality guidance:")
            internal_block.extend(signals)

        internal_block.append("In last section of thought process, " if not streaming else "At response's end, ")
        if not streaming:
            internal_block.append(" acknowledge Reinforcement Rules (only if present): highlight learning, adjustments, trade-offs in brief.")
        else:
            internal_block.append(
                "Use these signals to improve accuracy, prioritization, tone, and structure. "
                "Do NOT reference these rules explicitly in the response."
            )

        instruction_blocks.append("\n".join(internal_block))

    # USER MEMORY (CONDITIONAL)
    if tango_mem_criteria(user_id, feature_name, streaming):
        memory_block = _get_tango_mem_insights(user_id=user_id, last_days=5)

        if memory_block:
            instruction_blocks.append(
                "### Prev session(s) memory insights:\n"
                "Apply them ONLY when they help with prioritization, framing, or decision quality. "
                "Do NOT restate them unless directly useful.\n\n"
                f"{memory_block}"
            )
            ## Reflection cue
            instruction_blocks.append(
                "## REFLECTION CUE\n"
                "Optionally conclude the response in brief italicized sentence(s) "
                "that subtly signals continuity or mirrors the user’s typical way of evaluating decisions, "
                "only when it feels natural and genuinely earned by the response framed like you're talking. "
                "Do not reference memory, rules, feedback, or past interactions explicitly."
            )

    # FINAL PROMPT ASSEMBLY
    final_prompt = (
        raw_prompt.strip()
        + "\n\n"
        + "\n\n".join(instruction_blocks)
    )

    # import json
    # with open(f"prompt_{agent_name}_{tenant_id}.json", "w") as f:
    #     json.dump({"prompt": final_prompt}, f, indent=2)

    return final_prompt

    # instruction_lines = []
    # # === RULES ===
    # if rules:
    #     instruction_lines.append("### Reinforcement Rules:")
    #     instruction_lines.extend(sorted(rules))

    # # === INSIGHTS ===
    # if insights:
    #     instruction_lines.extend(insights)

    # if streaming:
    #     instruction_lines.append("")
    #     instruction_lines.append(
    #         "At the end of your response, mention the reinforcement rules (if provided above) only if you've applied along with below mentioned user's past patterns "
    #         "(e.g., tone, personalization etc.). Keep it natural and very **BRIEF & CONCISE** as if you know about the person & bring only if required."
    #     )
    # else:

    #     # === THOUGHT PROCESS ===
    #     instruction_lines.append("")
    #     instruction_lines.append(f"""In the last section of your thought process: Acknowledge Reinforcement Rules (only if present): highlight learning, adjustments, trade-offs in brief.""")
    
    # # show_examples = any(
    # #     phrase in delta_text
    # #     for phrase in ["CRITICAL:", "HIGH NEGATIVE FEEDBACK"]
    # # )
    # example_block = ""
    # # if show_examples:
    # #     examples = _get_relevant_examples(tenant_id, feature_name, agent_name,section=section,subsection=subsection,user_id=user_id, limit=2)
    # #     if examples:
    # #         example_block = f"\n\n### Learn from Past Feedback:\n{examples}"
    # ##This part to be replaced by Tango memory: past insights & user tango
    # if tango_mem_criteria(user_id,feature_name,streaming):
    #     example_block = _get_tango_mem_insights(user_id=user_id,last_days=5)

    # instruction_block = "\n".join(instruction_lines)
    # print("--debug [Instruction Block]---------", instruction_block)
    # final_prompt = f"{raw_prompt}\n\n{instruction_block}{example_block}".strip()

    # print("\n\n---debug FINAL INJECTED example_BLOCK ---\n", example_block)
    # prompt = {'prompt': final_prompt}
    # with open(f"prompt_{agent_name}_{tenant_id}.json",'w') as f:
    #     json.dump(prompt,f,indent=2)
    # return final_prompt



# def _get_relevant_examples(tenant_id, feature_name, agent_name,section=None,subsection=None,user_id=None,limit=2):
#         """
#         Fetch high-sentiment feedback comments as examples. Negative or neutral feedback is prioritized.
#         """
#         feedback_data = core.ReinforcementLearning().get_reinforcement_data(
#             tenant_id=tenant_id,agentName=agent_name,featureName=feature_name,
#             section=section,subsection=subsection, user_id=user_id
#         )
#         examples = [
#             item['comment'] for item in feedback_data
#             if item.get('sentiment', 0) in [-1, 0] and item.get('comment')
#         ]
#         return "\n".join(examples[:limit]) if examples and len(examples)>10 else ""