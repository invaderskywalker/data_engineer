from src.trmeric_integrations.Office.Api import OfficeAPI
from src.trmeric_services.tango.functions.Types import TangoFunction

def read_excel_book(api: OfficeAPI, workbook_id: str):
    return api.get_all_sheets_content(workbook_id)

def read_word_doc(api: OfficeAPI, document_id: str):
    return api.read_word_document(document_id)

def read_pdf(api: OfficeAPI, pdf_id: str):
    return api.read_pdf(pdf_id)

def read_presentation(api: OfficeAPI, presentation_id: str):
    return api.read_powerpoint_presentation(presentation_id)

def write_to_excel_sheet(api: OfficeAPI, workbook_name: str, data: list):
    return api.write_to_excel_sheet(workbook_name, data)

def write_to_word_doc(api: OfficeAPI, document_name: str, text: str):
    return api.write_to_word_document(document_name, text)

def list_excel_sheets(api: OfficeAPI):
    return api.list_excel_sheets().getColumn('Workbook Name')

def list_word_documents(api: OfficeAPI):
    return api.list_word_documents().getColumn('Document Name')

def list_onedrive_pdfs(api: OfficeAPI):
    return api.list_pdfs().getColumn('PDF Name')

def list_onedrive_presentations(api: OfficeAPI):
    return api.list_powerpoint_presentations().getColumn('Presentation Name')

READ_EXCEL_BOOK = TangoFunction(
    name="read_excel_book",
    description="Reads an Excel workbook which contains many sheets.",
    args=[
        {
            "name": "workbook_id",
            "description": "The ID of the workbook that we are looking to read from.",
            "type": "str"
        }
    ],
    return_description="Data of the contents in the sheets of the workbook.",
    func_type="office",
    function=read_excel_book,
    integration="office"
)

READ_WORD_DOC = TangoFunction(
    name="read_word_doc",
    description="Reads the content of a Microsoft Word document.",
    args=[
        {
            "name": "document_id",
            "description": "The ID of the Word document that we are looking to read from.",
            "type": "str"
        }
    ],
    return_description="The text content of the Word document.",
    func_type="office",
    function=read_word_doc,
    integration="office"
)

WRITE_TO_EXCEL_SHEET = TangoFunction(
    name="write_to_excel_sheet",
    description="Writes data to a specific sheet in an Excel workbook. Creates workbook or sheet if not present.",
    args=[
        {
            "name": "workbook_name",
            "description": "The name of the workbook to be created. Do not add a .xlsx suffix.",
            "type": "str"
        },
        {
            "name": "data",
            "description": "The data to be written to the sheet, represented as a list of lists (rows). Do not add any extra formatting.",
            "type": "list"
        }
    ],
    return_description="Success status of the operation.",
    func_type="office",
    function=write_to_excel_sheet,
    integration="office",
    active=True
)

WRITE_TO_WORD_DOC = TangoFunction(
    name="write_to_word_doc",
    description="Writes text to a Word document. Creates the document if not present.",
    args=[
        {
            "name": "document_name",
            "description": "The name of the Doc to be created. Do not add a docx suffix.",
            "type": "str"
        },
        {
            "name": "text",
            "description": "The text to be written to the Word document. Do not include any markdown formatting, only raw text.",
            "type": "str"
        }
    ],
    return_description="Success status of the operation.",
    func_type="office",
    function=write_to_word_doc,
    integration="office",
    active=True
)


LIST_WORD_DOCS = TangoFunction(
    name = "list_word_documents",
    description = "Lists the Word documents that you have access to.",
    args = [], 
    return_description = "List of Word documents that you have access to.",
    func_type = "office",
    function = list_word_documents,
    integration = "office",
)

LIST_EXCEL_SHEETS = TangoFunction(
    name="list_excel_sheets",
    description="Lists the Excel sheets that you have access to.",
    args=[],
    return_description="List of Excel sheets that you have access to.",
    func_type="office",
    function=list_excel_sheets,
    integration="office",
)

LIST_ONEDRIVE_PDFS = TangoFunction(
    name="list_onedrive_pdfs",
    description="Lists the PDFs that you have access to from the user's Microsoft OneDrive.",
    args=[],
    return_description="List of PDFs that you have access to from the user's Microsoft OneDrive.",
    func_type="office",
    function=list_onedrive_pdfs,
    integration="office",
)

READ_PDF = TangoFunction(
    name="read_pdf",
    description="Reads the content of a PDF document.",
    args=[
        {
            "name": "pdf_id",
            "description": "The ID of the PDF document that we are looking to read from.",
            "type": "str"
        }
    ],
    return_description="The text content of the PDF document.",
    func_type="office",
    function=read_pdf,
    integration="office"
)

LIST_OFFICE_PRESENTATIONS = TangoFunction( 
    name="list_onedrive_presentations",
    description="Lists the Powerpoint presentations that you have access to from the user's Microsoft OneDrive.",
    args=[],
    return_description="List of Powerpoint presentations that you have access to from the user's Microsoft OneDrive.",
    func_type="office",
    function=list_onedrive_presentations,
    integration="office",
)

READ_OFFICE_PRESENTATION = TangoFunction(
    name="read_presentations",
    description="Reads the content of a Powerpoint presentation in Microsoft OneDrive.",
    args=[
        {
            "name": "presentation_id",
            "description": "The ID of the Powerpoint presentation that we are looking to read from.",
            "type": "str"
        }
    ],
    return_description="The text content of the Powerpoint presentation in Microsoft OneDrive.",
    func_type="office",
    function=read_presentation,
    integration="office"
)