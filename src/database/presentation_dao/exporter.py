# src/database/presentation_dao/exporter.py

import pandas as pd
import tempfile
from typing import Dict, Any

class PresentationExportService:
    """
    Deterministic export layer.

    Converts presentation output → files.
    NO analytics.
    NO inference.
    """

    def export_to_excel(self, presentation_output: Dict[str, Any]) -> str:
        """
        Returns local file path of generated Excel file.
        """
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            writer = pd.ExcelWriter(tmp.name, engine="xlsxwriter")

            for sheet in presentation_output.get("sheets", []):
                df = pd.DataFrame(sheet.get("data", []))
                sheet_name = sheet.get("title", "Sheet")[:31]
                df.to_excel(writer, sheet_name=sheet_name, index=False)

            writer.close()
            return tmp.name
