import decimal
from peewee import PostgresqlDatabase
from playhouse.pool import PooledPostgresqlDatabase


import datetime
import os
from src.api.types.TabularData import TabularData
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
import base64
import ast
import json
from src.api.logging.AppLogger import appLogger
from dotenv import load_dotenv
load_dotenv()
from typing import List, Dict, Any



class TrmericDatabase:
    _instance = None
    DATA_KEY = b'\xb9\x15\x15\xa5[UR\xad\xdd\x95-3\xd7{\x81\xc4aX\xcb\xb8\xf8\x95\x08\xd8\xc3\x11Lp}@z\x1b:b\xa7/\xa1\xaf\xbf\xc4\xe3K\xa7\x803\xe4\xaa:w\xeavg\xc0\xe6\xbf\x80\xfeM\xf9\xea\xa8\xb0\x1c\xa7'

    # DATA_KEY = os.getenv("DATA_KEY")
    data_key = ast.literal_eval(str(DATA_KEY))
    cipher_suite = AESSIV(data_key)

    TABLES_TO_DEANONYMIZE = [
        {'table': 'users_user', 'columns': [
            'first_name', 'last_name', 'email', 'username', 'provider_name']},
        {'table': 'invite_invitations', 'columns': ['email', 'phone']},
        {'table': 'meetings_meetingguest', 'columns': [
            'guest_email_id', 'invited_user_name']},
        {'table': 'meetings_scheduleproductdemo', 'columns': [
            'first_name', 'last_name', 'work_email']},
        {'table': 'projects_portfoliobusiness', 'columns': [
            'sponser_first_name', 'sponser_last_name', 'sponser_email']},
        {'table': 'tenant_customer', 'columns': [
            'email', 'phone', 'address', 'contact_name']},
        {'table': 'tenant_provider', 'columns': [
            'email', 'phone', 'address', 'contact_name', 'company_name']},
        {'table': 'tenant_providercustomerfeedbackdetails', 'columns': [
            'cust_first_name', 'cust_last_name', 'cust_email']},
        {'table': 'workflow_projectteam', 'columns': [
            'pm_first_name', 'pm_last_name', 'pm_email']},
        {'table': 'workflow_projectteamsplit',
            'columns': ['member_name', 'member_email']},
    ]

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TrmericDatabase, cls).__new__(
                cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        print("initialize in trmeric database ", os.getenv("DB_NAME"))
        self.database = PostgresqlDatabase(
            os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            host=os.getenv("DB_HOST"),
            port=5432,
            password=os.getenv("DB_PASSWORD"),
        )
        self.pool_database = PooledPostgresqlDatabase(
            os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            host=os.getenv("DB_HOST"),
            port=5432,
            password=os.getenv("DB_PASSWORD"),
            max_connections=20,  # Maximum connections in the pool
            stale_timeout=30,   # Close idle connections after 300 seconds
        )
        
        # self.columns_to_deanonymize = [
        #     "provider_name", "created_by", "updated_by", "customer_name", "corresponding", "project_manager_name", "portfolio_leader_first_name", "portfolio_leader_last_name", "first_name", "last_name"
        # ]
        self.columns_to_deanonymize = [
            "provider_name", "created_by", "updated_by", "customer_name", "corresponding",
            "project_manager_name", "portfolio_leader_first_name", "portfolio_leader_last_name",
            "first_name", "last_name", "approver_name", "requestor_name", "owner_first_name", 
            "owner_last_name", "approver_first_name", "approver_last_name",
            "requestor_first_name", "requestor_last_name", "assignee_name", "assignee_first_name",
            "company_name", "provider_name","leader_first_name","leader_last_name",
            "user_first_name",
            
            "sponsor_first_name", "sponsor_last_name", "sponsor_email", "assignee_first_name", "assignee_last_name",
            "assigned_to_first_name", "assigned_to_last_name", "created_by_first_name", "created_by_last_name", 
            "resolved_by_first_name", "resolved_by_last_name"
        ]
        for table in self.TABLES_TO_DEANONYMIZE:
            for col in table['columns']:
                self.columns_to_deanonymize.append(col)

    def connect(self):
        if self.database.is_closed():
            self.database.connect()

    def closeDatabase(self):
        if not self.database.is_closed():
            self.database.close()

    def retrieveSQLQuery(self, query) -> TabularData:
        try:
            # print("retrieveSQLQuery--", query)
            self.closeDatabase()
            self.database.connect()
            cursor = self.database.cursor()
            try:
                cursor.execute(query)
            except Exception as e:
                print("Error in SQL execution: ", e, query)
                return TabularData([])

            columnNames = [desc[0] for desc in cursor.description]
            response = TabularData(columnNames)
            data = cursor.fetchall()

            # print("debug in retrieve sql ", columnNames, self.columns_to_deanonymize)

            columnIndexMap = {name: idx for idx,
                              name in enumerate(columnNames)}

            for row in data:
                updatedRow = list(row)
                for column_name in columnNames:
                    idx = columnIndexMap[column_name]
                    value = updatedRow[idx]
                    if isinstance(value, str):
                        updatedRow[idx] = self.deanonymize_text_from_base64(
                            value)

                    elif isinstance(value, dict):
                        try:
                            # Handle dict as JSON
                            json_value = json.loads(json.dumps(value))
                            for key in json_value:
                                if key in self.columns_to_deanonymize:
                                    json_value[key] = self.deanonymize_text_from_base64(
                                        json_value[key])
                            updatedRow[idx] = json_value
                        except json.JSONDecodeError:
                            updatedRow[idx] = value

                    elif isinstance(value, list):
                        try:
                            processed_list = []
                            for item in value:
                                if isinstance(item, dict):
                                    for key in item:
                                        if key in self.columns_to_deanonymize:
                                            item[key] = self.deanonymize_text_from_base64(
                                                item[key])
                                processed_list.append(item)
                            updatedRow[idx] = processed_list
                        except (json.JSONDecodeError, TypeError):
                            updatedRow[idx] = value

                response.addRow(tuple(updatedRow))

            self.database.close()
            return response

        except Exception as e:
            print("Error in retrieveSQLQuery ", e, query)
            self.database.close()
            return TabularData([])

    def deanonymize_text_from_base64(self, encrypted_text):
        if (encrypted_text is None or encrypted_text == ''):
            return ""
        try:
            decrypted_text = self.cipher_suite.decrypt(
                base64.b64decode(encrypted_text), associated_data=None)
            return decrypted_text.decode('utf-8')
        except Exception as e:
            # print(f"Error decrypting text: {e} .. text -- {encrypted_text}")
            return encrypted_text

    def encrypt_text_to_base64(self, plain_text):
        if not plain_text:
            return ""
        try:
            encrypted_text = self.cipher_suite.encrypt(plain_text.encode('utf-8'), associated_data=None)
            return base64.b64encode(encrypted_text).decode('utf-8')
        except Exception as e:
            # print(f"Error encrypting text: {e} .. text -- {plain_text}")
            return plain_text



    def retrieveSQLQueryOld(self, query):
        try:
            # print("debug_retrieveSQLQuery", query)
            self.closeDatabase()
            self.database.connect()
            cursor = self.database.cursor()
            try:
                # with self.database.cursor() as cursor:
                cursor.execute(query)
            except Exception as e:
                cursor.close()
                print("error in retrieveSQLQueryOld  ", e, query)
                return []
            columnNames = [desc[0] for desc in cursor.description]
            n = len(columnNames)
            res = cursor.fetchall()
            results = []

            columns_to_deanonymize = self.columns_to_deanonymize
            if res:
                for row in res:
                    resultDict = {}
                    for i in range(n):
                        column_name = columnNames[i]
                        value = row[i]
                        # print("column name", column_name, value)
                        if column_name in columns_to_deanonymize:

                            resultDict[column_name] = self.deanonymize_text_from_base64(
                                value)
                        elif isinstance(value, (datetime.datetime, datetime.date)):
                            resultDict[column_name] = value.isoformat()
                        elif isinstance(value, decimal.Decimal):
                            resultDict[column_name] = float(value)
                        elif isinstance(value, dict):
                            try:
                                # print("debug -- found dict", value)
                                # json_value = value
                                json_value = json.loads(json.dumps(value))
                                # print("debug -- found dict 2--", json_value)
                                for key in json_value:
                                    if key in columns_to_deanonymize:
                                        json_value[key] = self.deanonymize_text_from_base64(
                                            json_value[key])
                                resultDict[column_name] = json_value
                            except json.JSONDecodeError:
                                resultDict[column_name] = value
                        elif isinstance(value, list):
                            try:
                                # print("debug -- found list 2--", value)
                                processed_list = []
                                for item in value:
                                    if isinstance(item, str):
                                        try:
                                            parsed_item = json.loads(item)
                                            if isinstance(parsed_item, dict):
                                                processed_item = {}
                                                for key, val in parsed_item.items():
                                                    if key in columns_to_deanonymize and isinstance(val, str):
                                                        processed_item[key] = self.deanonymize_text_from_base64(val)
                                                    else:
                                                        processed_item[key] = val
                                                processed_list.append(processed_item)
                                            else:
                                                processed_list.append(parsed_item)
                                        except json.JSONDecodeError:
                                            processed_list.append(item)
                                    elif isinstance(item, dict):
                                        processed_item = {}
                                        for key, val in item.items():
                                            if key in columns_to_deanonymize and isinstance(val, str):
                                                processed_item[key] = self.deanonymize_text_from_base64(val)
                                            else:
                                                processed_item[key] = val
                                        processed_list.append(processed_item)
                                    else:
                                        processed_list.append(item)
                                resultDict[column_name] = processed_list
                            except (json.JSONDecodeError, TypeError) as e:
                                print(f"DEBUG: Error processing list for {column_name}: {e}, value: {value}")
                                resultDict[column_name] = value
                        else:
                            resultDict[column_name] = value
                    results.append(resultDict)

            self.database.close()
            return results

        except Exception as e:
            print("error in retrieveSQLQueryOld ", e, query)
            self.database.close()
            raise e


    def execute_query_safe(self, query: str, params: tuple = None) -> List[Dict]:
        """
        Safe parameterized query + full post-processing (deanonymize, JSON, dates).
        Replaces retrieveSQLQueryOld(query, params).
        """
        # print("================SQL==================")
        # print("execute_query_safe ", query, params)
        # print("===============***END***==================")
        try:
            self.closeDatabase()
            self.database.connect()
            cursor = self.database.cursor()
            try:
                cursor.execute(query, params or ())
            except Exception as e:
                cursor.close()
                print("error in execute_query_safe execute ", e, query, params)
                return []

            column_names = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            results = self._process_rows(rows, column_names)

            self.database.close()
            return results

        except Exception as e:
            print("error in execute_query_safe ", e, query, params)
            self.database.close()
            raise e
        
    def _process_rows(self, rows, column_names) -> List[Dict]:
        """
        Core logic from retrieveSQLQueryOld — deanonymize, type-convert, JSON parse.
        """
        results = []
        columns_to_deanonymize = self.columns_to_deanonymize

        for row in rows:
            result_dict = {}
            for i, column_name in enumerate(column_names):
                value = row[i]

                if column_name in columns_to_deanonymize:
                    result_dict[column_name] = self.deanonymize_text_from_base64(value)

                elif isinstance(value, (datetime.datetime, datetime.date)):
                    result_dict[column_name] = value.isoformat()

                elif isinstance(value, decimal.Decimal):
                    result_dict[column_name] = float(value)

                elif isinstance(value, dict):
                    try:
                        json_value = json.loads(json.dumps(value))
                        for k in json_value:
                            if k in columns_to_deanonymize and isinstance(json_value[k], str):
                                json_value[k] = self.deanonymize_text_from_base64(json_value[k])
                        result_dict[column_name] = json_value
                    except json.JSONDecodeError:
                        result_dict[column_name] = value

                elif isinstance(value, list):
                    processed_list = []
                    for item in value:
                        if isinstance(item, str):
                            try:
                                parsed = json.loads(item)
                                if isinstance(parsed, dict):
                                    processed = {}
                                    for k, v in parsed.items():
                                        if k in columns_to_deanonymize and isinstance(v, str):
                                            processed[k] = self.deanonymize_text_from_base64(v)
                                        else:
                                            processed[k] = v
                                    processed_list.append(processed)
                                else:
                                    processed_list.append(parsed)
                            except json.JSONDecodeError:
                                processed_list.append(item)
                        elif isinstance(item, dict):
                            processed = {}
                            for k, v in item.items():
                                if k in columns_to_deanonymize and isinstance(v, str):
                                    processed[k] = self.deanonymize_text_from_base64(v)
                                else:
                                    processed[k] = v
                            processed_list.append(processed)
                        else:
                            processed_list.append(item)
                    result_dict[column_name] = processed_list

                else:
                    result_dict[column_name] = value
            results.append(result_dict)
        return results
    
    def executeSQLQuery(self, query, params, fetch=''):
        # print("executeSQLQuery ", query)
        try:
            # Connect to the database
            self.closeDatabase()
            self.database.connect()
            # Create a cursor to execute the query
            cursor = self.database.cursor()
            try:
                cursor.execute(query, params)

                # Commit the changes
                self.database.commit()
                
                # Fetch results if needed
                if fetch == "all":
                    result = cursor.fetchall()
                elif fetch == "one":
                    result = cursor.fetchone()
                else:
                    result = None

                # Check if any rows were affected
                if cursor.rowcount == 0:
                    print("Warning: No rows updated, check your WHERE clause and data.")


            except Exception as e:
                cursor.close()
                print("Error executing query:", e, query)
                raise e

            finally:
                cursor.close()
                self.database.close()

            return result
    
        except Exception as e:
            appLogger.info({
                "event": "error_executeSQLQuery",
                "error": str(e)
            })
            self.database.close()
            raise e


    def retrieveSQLQueryWithPool(self, query):
        try:
            with self.pool_database.connection_context():  # Use pooled database
                cursor = self.pool_database.cursor()  # Corrected to cursor()
                try:
                    cursor.execute(query)
                except Exception as e:
                    print("error in retrieveSQLQueryWithPool ", e, query)
                    return []

                columnNames = [desc[0] for desc in cursor.description]
                n = len(columnNames)
                res = cursor.fetchall()
                results = []

                columns_to_deanonymize = self.columns_to_deanonymize
                if res:
                    for row in res:
                        resultDict = {}
                        for i in range(n):
                            column_name = columnNames[i]
                            value = row[i]
                            if column_name in columns_to_deanonymize:
                                resultDict[column_name] = self.deanonymize_text_from_base64(value)
                            elif isinstance(value, (datetime.datetime, datetime.date)):
                                resultDict[column_name] = value.isoformat()
                            elif isinstance(value, decimal.Decimal):
                                resultDict[column_name] = float(value)
                            elif isinstance(value, dict):
                                try:
                                    json_value = json.loads(json.dumps(value))
                                    for key in json_value:
                                        if key in columns_to_deanonymize:
                                            json_value[key] = self.deanonymize_text_from_base64(json_value[key])
                                    resultDict[column_name] = json_value
                                except json.JSONDecodeError:
                                    resultDict[column_name] = value
                            elif isinstance(value, list):
                                try:
                                    processed_list = []
                                    for item in value:
                                        if isinstance(item, dict):
                                            for key in item:
                                                if key in columns_to_deanonymize:
                                                    item[key] = self.deanonymize_text_from_base64(item[key])
                                        processed_list.append(item)
                                    resultDict[column_name] = processed_list
                                except (json.JSONDecodeError, TypeError):
                                    resultDict[column_name] = value
                            else:
                                resultDict[column_name] = value
                        results.append(resultDict)

                return results

        except Exception as e:
            print("error in retrieveSQLQueryWithPool ", e, query)
            raise e
    
    def executeSQLQuery2(self, query, params=None, fetch=''):
        try:
            self.closeDatabase()
            self.database.connect()
            cursor = self.database.cursor()

            try:
                if params is not None:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                self.database.commit()

                if fetch == "all":
                    result = cursor.fetchall()
                elif fetch == "one":
                    result = cursor.fetchone()
                else:
                    result = None

                if cursor.rowcount == 0:
                    print("Warning: No rows affected.")

            except Exception as e:
                cursor.close()
                print("Error executing query:", e, query, params)
                raise e

            finally:
                cursor.close()
                self.database.close()

            return result

        except Exception as e:
            appLogger.info({
                "event": "error_executeSQLQuery2",
                "error": str(e)
            })
            self.database.close()
            raise e





db_instance = TrmericDatabase()
