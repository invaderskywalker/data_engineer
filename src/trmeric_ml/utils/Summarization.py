from src.trmeric_ml.llm.Client import LLMClient
from src.trmeric_ml.utils.ChunkText import chunkTextForLLM
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions


def summarizeChunk(llm: LLMClient, chunk: str, context: str, prev_summaries: str = None, chunk_num: int = 0):
    system = f"""You are an assistant for a B2B SaaS company called Trmeric. Your task is to summarize text, with a focus on saving/storing information about company projects, roadmaps, initiatives, actions, and if needed, maybe even making your own analysis at some points of the information.
    """

    if prev_summaries:
        system += f"""
        Additionally, there is a catch. There is a chance that you are summarizing only a specific section of a larger text. In this case, we ask that you do the following:

        Respond with the entire summary so far plus integrated with the summary of the new text. This will help the user to have a complete understanding of the information.
        """
    user = f"""Here is some context behind the text that you need to summarize: {context}"""
    if prev_summaries:
        user += f"""
        Here is the summary that you have so far: {prev_summaries}
        """
    user += f"""
    Here is the text that you need to summarize: {chunk}"""
    return llm.runV2(
        ChatCompletion(system=context, prev=[], user=chunk),
        ModelOptions(model="gpt-4o-mini", max_tokens=16384, temperature=0.3),
        f"Summarizer for chunks: {chunk[:50]}"
    )


def summarizeText(llm: LLMClient, text: str, context: str):
    chunks = chunkTextForLLM(llm, text, 100000)
    print(len(chunks))
    summaries = []
    for chunk in chunks:
        summaries.append(summarizeChunk(llm, chunk, context, summaries[-1] if summaries else None))
    return summaries[-1]