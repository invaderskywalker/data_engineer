from src.trmeric_ml.llm.Client import LLMClient

def chunkTextForLLM(llm: LLMClient, text: str, chunk_size: int):
    
    # keep halving the text until each chunk is less than chunk_size, then it should return a list of chunks of the text that are each less than chunk_size

    if len(llm.tokenize(text, "gpt-4-turbo")):
        return [text]

    chunks = []
    tokenized_text = llm.tokenize(text, "gpt-4-turbo")
    for i in range(0, len(tokenized_text), chunk_size):
        chunk = tokenized_text[i:min(i + chunk_size, len(tokenized_text))]
        chunks.append(llm.decode(chunk, "gpt-4-turbo"))
    
    return chunks