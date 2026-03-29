from src.trmeric_integrations.Drive.Api import DriveAPI
from src.trmeric_services.tango.functions.Types import TangoFunction

def read_sheet(api: DriveAPI, workbook_id: str):
    return api.read_google_sheet(workbook_id)

def read_doc(api: DriveAPI, document_id: str):
    return api.read_google_doc(document_id)

def read_pdf(api: DriveAPI, pdf_id: str):
    return api.read_google_pdf(pdf_id)

def write_to_sheet(api: DriveAPI, sheet_name: str, data: list):
    return api.write_to_google_sheet(sheet_name, data)

def write_to_doc(api: DriveAPI, document_name: str, text: str):
    return api.write_to_google_doc(document_name, text)

def list_google_sheets(api: DriveAPI):
    return api.list_google_sheets().getColumn('Sheet Name')

def list_google_docs(api: DriveAPI):
    return api.list_google_docs().getColumn('Document Name')

def list_google_pdfs(api: DriveAPI):
    return api.list_google_pdfs().getColumn('PDF Name')

def list_google_presentations(api: DriveAPI):
    return api.list_google_presentations().getColumn('Presentation Name')

def read_presentation(api: DriveAPI, presentation_id: str):
    return api.read_google_presentation(presentation_id)

READ_GOOGLE_SHEET = TangoFunction(
    name="read_google_sheet",
    description="Reads a Google Sheet workbook which contains many sheets.",
    args=[
        {
            "name": "workbook_id",
            "description": "The ID of the workbook that we are looking to read from.",
            "type": "str"
        }
    ],
    return_description="Data of the contents in the sheets of the workbook.",
    func_type="drive",
    function=read_sheet,
    integration="drive"
)

READ_GOOGLE_DOC = TangoFunction(
    name="read_google_doc",
    description="Reads the content of a Google Docs document.",
    args=[
        {
            "name": "document_id",
            "description": "The ID of the Google Docs document that we are looking to read from.",
            "type": "str"
        }
    ],
    return_description="The text content of the Google Docs document.",
    func_type="drive",
    function=read_doc,
    integration="drive"
)

READ_GOOGLE_PDF = TangoFunction(
    name="read_google_pdf",
    description="Reads the content of a PDF in the Google Drive.",
    args=[
        {
            "name": "pdf_id",
            "description": "The ID of the pdf that we are looking to read from.",
            "type": "str"
        }
    ],
    return_description="The text content of the selected PDF Document.",
    func_type="drive",
    function=read_pdf,
    integration="drive"
)

WRITE_TO_GOOGLE_SHEET = TangoFunction(
    name="write_to_google_sheet",
    description="Writes data to a specific sheet in an Google Sheet workbook. Creates workbook or sheet if not present.",
    args=[
        {
            "name": "sheet_name",
            "description": "The name of the new Google Sheets workbook where the text should be written.",
            "type": "str"
        },
        {
            "name": "data",
            "description": "The data to be written to the sheet, represented as a list of lists (rows).",
            "type": "list"
        }
    ],
    return_description="Success status of the operation.",
    func_type="drive",
    function=write_to_sheet,
    integration="drive",
    active=True
)

WRITE_TO_GOOGLE_DOC = TangoFunction(
    name="write_to_google_doc",
    description="Writes text to a Google Docs document. Creates the document if not present.",
    args=[
        {
            "name": "document_name",
            "description": "The name of the new Google Docs document where the text should be written.",
            "type": "str"
        },
        {
            "name": "text",
            "description": "The text to be written to the Google Docs document.",
            "type": "str"
        }
    ],
    return_description="Success status of the operation.",
    func_type="drive",
    function=write_to_doc,
    integration="drive",
    active=True
)

LIST_GOOGLE_DOCS = TangoFunction(
    name="list_google_docs",
    description="Lists the Google Docs documents that the user has access to.",
    args=[],
    return_description="The list of Google Docs documents that the user has access to",
    func_type="drive",
    function=list_google_docs,
    integration="drive"
)

LIST_GOOGLE_SHEETS = TangoFunction(
    name="list_google_sheets",
    description="Lists the Google Sheets workbooks that the user has access to.",
    return_description="The list of Google Sheets workbooks that the user has access to",
    args = [],
    func_type="drive",
    function=list_google_sheets,
    integration="drive"
)

LIST_GOOGLE_PDFS = TangoFunction(  
    name="list_google_pdfs",
    description="Lists the PDFs in the google drive that the user has access to.",
    return_description="The list of Google PDFs that the user has access to",
    args = [],
    func_type="drive",
    function=list_google_pdfs,
    integration="drive"
)

LIST_GOOGLE_PRESENTATIONS = TangoFunction(
    name="list_google_presentations",
    description="Lists the Google Slides presentations and pptx that the user has access to.",
    return_description="The list of Google Slides presentations and pptx that the user has access to",
    args = [],
    func_type="drive",
    function=list_google_presentations,
    integration="drive"
)

READ_GOOGLE_PRESENTATION = TangoFunction(
    name="read_google_presentation",
    description="Reads the content of a Google Slides presentation or pptx inside google drive.",
    args=[
        {
            "name": "presentation_id",
            "description": "The ID of the Google Slides presentation that we are looking to read from.",
            "type": "str"
        }
    ],
    return_description="The text content of the Google Slides presentation.",
    func_type="drive",
    function=read_presentation,
    integration = "drive"
)