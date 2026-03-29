# from langchain_openai import OpenAIEmbeddings
# from langchain.vectorstores.chroma import Chroma


# class TrmericVectorSearch:
#     def __init__(self, name: str, path: str):
#         self.embedder = OpenAIEmbeddings()
#         self.vectorDB = Chroma(
#             name, embedding_function=self.embedder, persist_directory=path
#         )
#         self.retriever = self.vectorDB.as_retriever()

#     def queryVectorDB(self, query: str):
#         docs = self.retriever.get_relevant_documents(query)
#         doc_string = self.format_docs(docs=docs)
#         return doc_string

#     def format_docs(self, docs):
#         return "\n\n".join(doc.page_content for doc in docs)
