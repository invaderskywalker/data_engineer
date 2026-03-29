from src.trmeric_services.tango.types.TangoIntegrationData import TangoIntegrationData
from src.trmeric_services.tango.types.TangoIntegration import TangoIntegration
from src.api.types.TabularData import TabularData
from src.trmeric_services.tango.functions.Types import ApiMetadata
from src.trmeric_integrations.Drive.Api import DriveAPI
from src.trmeric_services.tango.functions.integrations.drive.GetDriveData import (
    READ_GOOGLE_SHEET, READ_GOOGLE_DOC, WRITE_TO_GOOGLE_SHEET, WRITE_TO_GOOGLE_DOC, LIST_GOOGLE_DOCS, LIST_GOOGLE_SHEETS, READ_GOOGLE_PDF, LIST_GOOGLE_PDFS, LIST_GOOGLE_PRESENTATIONS, READ_GOOGLE_PRESENTATION)

class DriveIntegration(TangoIntegration):
    """
    This is a class to represent the integration of Google Sheets and Docs.
    """

    def __init__(self, userID: int, tenantID: int, metadata: ApiMetadata = None):
        super().__init__("drive", [READ_GOOGLE_SHEET, READ_GOOGLE_DOC, READ_GOOGLE_PDF, WRITE_TO_GOOGLE_SHEET, WRITE_TO_GOOGLE_DOC, LIST_GOOGLE_DOCS, LIST_GOOGLE_SHEETS, LIST_GOOGLE_PDFS, LIST_GOOGLE_PRESENTATIONS, READ_GOOGLE_PRESENTATION], userID, tenantID, True)
        self.api = DriveAPI(userID, tenantID, metadata)

    def initializeIntegration(self):
        """
        Initializes the integration with Google Drive.
        """
        workbooks = self.api.list_google_sheets()
        workbooks_description = "For Google Sheets, here are the workbooks and the sheets inside each of them that you can access and read through"
        
        docs = self.api.list_google_docs()
        docs_description = "For Google Docs, here are the documents that you have access to and can read the content of"
        
        pdfs = self.api.list_google_pdfs()
        pdfs_description = "For Google PDFs, here are the PDFs that you have access to and can read the content of"
        
        pres = self.api.list_google_presentations()
        pres_description = "For Google Presentations, here are the presentations that you have access to and can read the content of"
        
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
            
