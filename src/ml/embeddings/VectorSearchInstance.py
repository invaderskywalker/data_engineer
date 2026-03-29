# from langchain_openai import OpenAIEmbeddings
# from langchain.vectorstores.chroma import Chroma 

# from langchain_community.document_loaders import TextLoader
# from langchain_community.embeddings.sentence_transformer import (
#     SentenceTransformerEmbeddings,
# )
# from langchain_text_splitters import CharacterTextSplitter
# from langchain.schema import Document


# class VectorSearchInstance:
#     '''
#     This instance takes a really long string, splits it into chunks of size k.
#     Then it creates a queriable user instance 
#     '''
    
#     def __init__(self, name: str, content: list):
#         self.embeddings = OpenAIEmbeddings()
#         self.textSplitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
#         self.docs = self.textSplitter.create_documents(content)
#         self.db = Chroma.from_documents(self.docs, self.embeddings)

#     def queryDB(self, query):
#         return self.db.similarity_search(query)
