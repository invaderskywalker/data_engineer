import datetime
import pandas as pd
class TabularData:
    
    def __init__(self, columns: list):
        self.columns = columns
        self.data = []
    
    def addRow(self, row: list):
        assert len(row) == len(self.columns), "The number of columns in the row should be equal to the number of columns in the tabular data."
        self.data.append(row)

    def getColumnNames(self) -> list:
        return self.columns

    def toDataFrame(self) -> pd.DataFrame:
        return pd.DataFrame(self.data, columns=self.columns)

    def getColumns(self, columns: list) -> list:
        assert all(column in self.columns for column in columns), "The column names do not exist in the tabular data."
        col_indices = [self.columns.index(column) for column in columns]
        return [[row[col_index] for col_index in col_indices] for row in self.data]
        
    def getColumn(self, columnName: str) -> list:
        assert columnName in self.columns, "The column name does not exist in the tabular data."
        col_index = self.columns.index(columnName)
        return [row[col_index] for row in self.data]
    
    def getRow(self, index: int) -> list:
        assert index < len(self.data), "The index is out of bounds."
        return self.data[index]
    
    def formatData(self) -> str:
        response = "|"
        for column in self.columns:
            response += f" {column} |"
        response += "\n"
        response += "|"
        for column in self.columns:
            response += " --- |"
        response += "\n"
        for row in self.data:
            response += "|"
            for value in row:
                if isinstance(value, (datetime.datetime, datetime.date)):
                    response += f" {value.isoformat()} |"
                else:
                    response += f" {value} |"
            response += "\n"
        return response

    def filterColumns(self, column: str, func: callable):
        assert column in self.columns, "The column name does not exist in the tabular data."
        col_index = self.columns.index(column)
        data = [row for row in self.data if func(row[col_index])]
        newTabular = TabularData(self.columns)
        newTabular.data = data
        return newTabular

    def applyFunction(self, columnName: str, func: callable):
        assert columnName in self.columns, "The column name does not exist in the tabular data."
        colIndex = self.columns.index(columnName)
        for row in self.data:
            row[colIndex] = func(row[colIndex])

    def sort(self, columnName: str, ascending: bool = True):
        assert columnName in self.columns, "The column name does not exist in the tabular data."
        colIndex = self.columns.index(columnName)
        if ascending:
            self.data.sort(key=lambda row: row[colIndex])
        else:
            self.data.sort(key=lambda row: row[colIndex], reverse=True)

    def getRows(self):
        return [dict(zip(self.columns, row)) for row in self.data]
