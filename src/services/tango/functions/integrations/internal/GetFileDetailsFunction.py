from src.trmeric_s3.s3 import S3Service
from src.trmeric_services.tango.functions.Types import TangoFunction
from src.trmeric_services.summarizer.SummarizerService import SummarizerService

def process_uploaded_files(
        eligibleProjects: list[int],
        tenantID: int,
        userID: int,
        s3_keys: list[str], 
        user_query: str, 
        **kwargs
    ):
    """
    Processes uploaded files from S3, chunks and summarizes their content, 
    and responds to the user's query based on document content.
    
    Args:
        s3_keys (list): List of S3 keys for files to process.
        user_query (str): The user's question related to the document content.
        
    Returns:
        str: Response summarizing the relevant content based on user query.
    """
    s3_service = S3Service()    
    all_summaries = []
    print("--debug inside process_upload_files fxn-------")

    for s3_key in s3_keys:
        print(f"Processing file with S3 key: {s3_key}")
        
        # Download file data
        file_content = s3_service.download_file_as_text(s3_key)
        if file_content is None:
            print(f"Skipping file {s3_key} due to download error.")
            continue
        
        summarizer_service = SummarizerService(logInfo=None)
        summaries = summarizer_service.summarizer(file_content, user_query, "files_uploaded")
        all_summaries.extend(summaries)

    response = "\n\n".join(all_summaries)
    return response


GET_FILE_DETAILS = TangoFunction(
    name="get_file_details",
    description="""If the user has uploaded documents, 
                then use this function to retreive the details of the documents and pass the user_query so that 
                we can extract important points from the document.
                """,
    args=[
        #  {
        #     "name": "filename",
        #     "type": "str",
        #     "description": "The filename the user wants details for."
        #  },
         {
            "name": "s3_keys",
            "type": "str[]",
            "description": "The list of s3_keys of filenames that user wants to enquire about",
        },
        {
            "name": "user_query",
            "type": "str",
            "description": "The user's query related to the document content."
        },
    ],
    return_description="The result of the user input query on the uploaded document",
    function=process_uploaded_files,
    func_type = "general",
    integration="trmeric"
)







