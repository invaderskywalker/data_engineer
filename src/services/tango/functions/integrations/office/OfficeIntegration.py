from src.trmeric_services.tango.types.TangoIntegrationData import TangoIntegrationData
from src.trmeric_services.tango.types.TangoIntegration import TangoIntegration
from src.trmeric_api.types.TabularData import TabularData
from requests.auth import HTTPBasicAuth
from src.trmeric_services.tango.functions.Types import ApiMetadata
from src.trmeric_integrations.Office.Api import OfficeAPI
from src.trmeric_services.tango.functions.integrations.office.GetOfficeData import (
    READ_EXCEL_BOOK, READ_WORD_DOC, WRITE_TO_EXCEL_SHEET, WRITE_TO_WORD_DOC, LIST_EXCEL_SHEETS, LIST_WORD_DOCS, READ_PDF, LIST_ONEDRIVE_PDFS, LIST_OFFICE_PRESENTATIONS, READ_OFFICE_PRESENTATION)

class OfficeIntegration(TangoIntegration):
    """
    This is a class to represent the integration of Excel.
    """

    def __init__(self, userID: int, tenantID: int, metadata: ApiMetadata = None):
        super().__init__("office", [READ_EXCEL_BOOK, READ_WORD_DOC, READ_PDF,WRITE_TO_EXCEL_SHEET, WRITE_TO_WORD_DOC, LIST_EXCEL_SHEETS, LIST_WORD_DOCS, LIST_ONEDRIVE_PDFS, LIST_OFFICE_PRESENTATIONS, READ_OFFICE_PRESENTATION], userID, tenantID, True)
        self.api = OfficeAPI(userID, tenantID, metadata)

    def initializeIntegration(self):
        """
        Initializes the integration with Office.
        """
        workbooks = self.api.list_excel_sheets()
        workbooks_description = "For excel, here are the workbooks and the sheets inside each of them that you can access and read through"
        
        docs = self.api.list_word_documents()
        docs_description = "For word, here are the docs that you have access too and can read the content of"
        
        pdfs = self.api.list_pdfs()
        pdfs_description = "For pdfs, here are the pdfs that you have access too and can read the content of"
        
        pres = self.api.list_powerpoint_presentations()
        pres_description = "For presentations, here are the presentations that you have access too and can read the content of"
        
        if workbooks is not None:
            workbookData = TangoIntegrationData(workbooks, workbooks_description)
            self.addIntegrationData(workbookData)           
        
        if docs is not None:
            docsData = TangoIntegrationData(docs, docs_description)
            self.addIntegrationData(docsData)
            
        if pdfs is not None:
            pdfsData = TangoIntegrationData(pdfs, pdfs_description)
            self.addIntegrationData(pdfsData)
            
        if pres is not None:
            presData = TangoIntegrationData(pres, pres_description)
            self.addIntegrationData(presData)
