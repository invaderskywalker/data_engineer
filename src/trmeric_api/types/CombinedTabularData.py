import datetime

class CombinedTabularData:
    
    def __init__(self, tabular_data_list: list):
        self.tabular_data_list = tabular_data_list
    
    def formatData(self) -> str:
        response = ""
        for tabular_data in self.tabular_data_list:
            # Format each table separately and concatenate them with an additional newline
            response += "|"
            for column in tabular_data.columns:
                response += f" {column} |"
            response += "\n"
            response += "|"
            for column in tabular_data.columns:
                response += " --- |"
            response += "\n"
            for row in tabular_data.data:
                response += "|"
                for value in row:
                    if isinstance(value, (datetime.datetime, datetime.date)):
                        response += f" {value.isoformat()} |"
                    else:
                        response += f" {value} |"
                response += "\n"
            response += "\n"  # Add a newline to separate tables
        return response

    def filterColumns(self, column: str, func: callable):
        filtered_data_list = [tabular_data.filterColumns(column, func) for tabular_data in self.tabular_data_list]
        return CombinedTabularData(filtered_data_list)

    def applyFunction(self, columnName: str, func: callable):
        for tabular_data in self.tabular_data_list:
            tabular_data.applyFunction(columnName, func)

    def sort(self, columnName: str, ascending: bool = True):
        for tabular_data in self.tabular_data_list:
            tabular_data.sort(columnName, ascending)

    def getRows(self):
        combined_rows = []
        for tabular_data in self.tabular_data_list:
            combined_rows.extend(tabular_data.getRows())
        return combined_rows
