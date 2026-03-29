# from src.trmeric_services.tango.functions.Types import TangoFunction
# from src.trmeric_ml.embeddings.VectorSearch import TrmericVectorSearch


# def queryTrmericDocs(**kwargs):
#     """Returns the vector searcher that the user can use to query the Trmeric documents.

#     Returns:
#        vectorSearcher: The vector searcher that the user can use to query the Trmeric documents.
#     """
#     return TrmericVectorSearch(
#         "vectordb-combined-data", "new_data/combined_bp_pq_advice/"
#     )


# QUERY_TRMERIC_DOCS = TangoFunction(
#     name="query_trmeric_docs",
#     description="If the user has a question about how to use Trmeric or the best practices of using the platform or anything related to the platform specifically and how they can use it, use this function.",
#     args=[],
#     return_description="Returns a list of documents that are related to the user's query.",
#     function=queryTrmericDocs,
#     func_type="bp",
#     integration="General"
# )
