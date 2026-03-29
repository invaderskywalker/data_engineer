# from langchain_openai import OpenAIEmbeddings
# from langchain_chroma import Chroma  # Updated import
# from langchain.schema import Document
# from langchain_community.document_loaders import DirectoryLoader
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from tango.const import TRMERIC_COMBINED_INPUT_PATH, TRMERIC_COMBINED_VECTOR_PATH
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
import traceback

class TrmericVectorSearch:
    def __init__(self, name: str = 'vectordb-combined-data-new', path: str = 'vectorDB/combined_new'):
        # self.embedder = OpenAIEmbeddings()
        # self.vectorDB = Chroma(collection_name=name, embedding_function=self.embedder, persist_directory=path)  # Updated parameter
        # self.retriever = self.vectorDB.as_retriever()
        pass

    def queryVectorDB(self, query: str):
        try:
            print("queryVectorDB ", query)
            # docs = self.retriever.get_relevant_documents(query)
            # doc_string = self.format_docs(docs=docs)
            # print("queryVectorDB  doc_string", doc_string)
            # debugLogger.info({"function": "queryVectorDB", "query": query, "doc_count": len(docs)})
            return query
        except Exception as e:
            appLogger.error({"function": "queryVectorDB_error", "error": str(e), "traceback": traceback.format_exc()})
            return ""

    def format_docs(self, docs):
        return "\n\n".join(doc.page_content for doc in docs)

# def vectorize_combined_data():
#     try:
#         loader = DirectoryLoader(TRMERIC_COMBINED_INPUT_PATH)
#         pages = loader.load()
#         for k in pages:
#             debugLogger.info({"function": "vectorize_combined_data", "metadata": k.metadata})
#         splitter = RecursiveCharacterTextSplitter(chunk_size=600)
#         docs = splitter.split_documents(pages)
#         chromaDB = get_combined_vectorDB()
#         chromaDB.add_documents(docs)
#         chromaDB.persist()
#         return chromaDB.get()
#     except Exception as e:
#         appLogger.error({"function": "vectorize_combined_data_error", "error": str(e), "traceback": traceback.format_exc()})
#         return {}

# def get_combined_vectorDB() -> Chroma:
#     embedder = OpenAIEmbeddings()
#     chromaDB = Chroma(
#         collection_name="vectordb-combined-data-new",
#         embedding_function=embedder,
#         persist_directory=TRMERIC_COMBINED_VECTOR_PATH
#     )
#     return chromaDB
