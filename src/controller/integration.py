from flask import jsonify, request
from src.trmeric_api.logging.AppLogger import appLogger
import traceback
from src.trmeric_services.integration.IntegrationService import IntegrationService
from src.trmeric_services.integration.RefreshTokenService import RefreshTokenService
# from src.trmeric_integrations.Drive.Api import DriveAPI
# from src.trmeric_services.integration.Drive import Drive
from src.trmeric_services.integration.Drive_v2 import DriveV2
from src.trmeric_services.integration.Smartsheet import Smartsheet
from src.trmeric_database.dao import IntegrationDao, JobDAO, TangoDao
import json
import requests
import traceback
from datetime import datetime
from src.trmeric_services.integration.JiraOnPrem import JiraOnPrem


class IntegrationController:
    def __init__(self):
        self.service = IntegrationService()
        self.refreshTokenService = RefreshTokenService()

    def integrationUpdate(self):
        try:
            project_id = request.json.get("project_id")
            tenant_id = request.json.get("tenant_id")
            user_id = request.json.get("user_id")
            print("--integrationUpdate-", project_id, tenant_id, user_id)
            self.service.updateIntegrationData(tenant_id, user_id, project_id)
            return jsonify({"status": "success", "data": {}}), 200
        except Exception as e:
            appLogger.error({
                "event": "integrationUpdate",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500

    def integrationUpdateV2(self):
        try:
            project_id = request.json.get("project_id")
            tenant_id = request.json.get("tenant_id")
            user_id = request.json.get("user_id")
            mapping_id = request.json.get("mapping_id")
            print("--integrationUpdate-",  tenant_id, user_id, mapping_id)
            self.service.updateIntegrationDataV2(
                project_id, tenant_id, user_id, mapping_id)
            return jsonify({"status": "success", "data": {}}), 200
        except Exception as e:
            appLogger.error({
                "event": "integrationUpdate",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500

    def refreshIntegrationAccessToken(self):
        try:
            integration_type = request.json.get("integration_type")
            tenantId = request.decoded.get("tenant_id")
            userId = request.decoded.get("user_id")

            data = self.refreshTokenService.refreshIntegrationAccessToken(
                tenantId, userId, integration_type
            )
            return jsonify({"status": "success", "data": data}), 200
        except Exception as e:
            appLogger.error({
                "event": "refreshIntegrationAccessToken",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500

    def internalRefreshIntegrationAccessToken(self):
        try:
            integration_type = request.json.get("integration_type")
            tenantId = request.json.get("tenant_id")
            userId = request.json.get("user_id")

            data = self.refreshTokenService.refreshIntegrationAccessToken(
                tenantId, userId, integration_type
            )
            return jsonify({"status": "success", "data": data}), 200
        except Exception as e:
            appLogger.error({
                "event": "refreshIntegrationAccessToken",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500

    
    def paginate_items_v2(self, items, page, page_size, total=None):
        print(f"--debug paginate_items: input items length: {len(items)}")

        total = total if total is not None else len(items)
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total)

        # print("--debug paginate_items: items: ", items[start_idx:end_idx], "index  ", start_idx, end_idx)
        paginated_data = items[start_idx:end_idx]

        has_more = end_idx < total

        paginated_json = {
            "data": paginated_data,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "hasMore": has_more
        }
        # print(f"--debug paginated_json: {paginated_json}")
        appLogger.info({"event": "paginate_items", "data": paginated_json})
        return paginated_json



    def fetchGoogleDriveResourcesV2(self, type):
        """Fetch Google Drive resources: folders, docs, or presentations with pagination and search."""
        print(f"--debug fetchGoogleDriveResources started for type: {type}")

        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            project_id = request.decoded.get("project_id")
            print(f"--debug ids: {tenant_id}, {user_id}, {project_id}")

            # Extract pagination and search parameters
            page = request.args.get("page", default=1, type=int)
            page_size = request.args.get("pageSize", default=10, type=int)
            search = request.args.get("search", default=None, type=str)

            # Extract selected items from request
            request_data = request.json or {}
            selected_folders = request_data.get("folders", [])
            selected_ppts = request_data.get("ppts", [])
            selected_spreadsheets = request_data.get("spreadsheets", [])
            selected_sheets = request_data.get("sheets", [])
            
            print("\n\n\n--debug frontend params----", page, page_size, selected_folders,selected_spreadsheets,selected_sheets)

            token = self.refreshTokenService.refreshIntegrationAccessToken(tenant_id, user_id, "drive")
            print(f"\n\n--debug drive token: {token}")

            access_token = token["access_token"]
            refresh_token = token["refresh_token"]

            drive_api = DriveV2(
                user_id=user_id,
                tenant_id=tenant_id,
                project_id=project_id,
                metadata={"refresh_token": refresh_token},
                access_token=access_token
            )
            print(f"--debug drive_api: {drive_api}")

            # Initialize response data
            all_folders = []
            docs = []
            ppts = []
            slides = []
            spreadsheets = []
            sheets = []
    
            sheet_projects_list = []
            total = 0
            has_more = False

            # Fetch based on type
            if type == "folders":
                # Fetch folders with pagination and search
                folder_response = drive_api.list_top_level_folders(page=page, page_size=page_size, search=search)
                print("--debug folders response: ", folder_response)
                
                all_folders = folder_response.get("data", [])
                total = folder_response.get("total", len(all_folders))
                print(f"\n\nTotal folders {total}\n\n--debug all_folders: {all_folders}")

                if not selected_folders:
                    result = {
                        "folders": all_folders,
                        "docs": [],
                        "ppts": [],
                        "slides": []
                    }
                    return jsonify({
                        "status": "success",
                        "data": result,
                        "total": total,
                        "hasMore": folder_response.get("hasMore", False),
                        "page": page,
                        "pageSize": page_size
                    }), 200

            # Process selected folders for docs or ppts
            print(f"--debug selected folders: {selected_folders}")
            if selected_folders:
                folder_ids = [folder["id"] for folder in selected_folders]
                if type == "docs":
                    doc_response = drive_api.list_google_documents_v2(
                        folder_ids=folder_ids, page=page, page_size=page_size, search=search
                    )
                    print("--debug docs response: ", doc_response)
                    
                    docs = doc_response.get("data", [])
                    total = doc_response.get("total", len(docs))
                    print(f"\n\nTotal docs {total}\n\n--debug documents: {docs}")
                    
                elif type == "ppt":
                    ppt_response = drive_api.list_google_presentations_v2(
                        folder_ids=folder_ids, page=page, page_size=page_size, search=search
                    )
                    print("--debug ppts response-----", ppt_response)
                    
                    ppts = ppt_response.get("data", [])
                    total = ppt_response.get("total", len(ppts))
                    print(f"\n\nTotal ppts {total}\n\n--debug presentations: {ppts}")
                    
                elif type == "spreadsheet":
                    # folder_ids = [folder["id"] for folder in selected_folders]
                    spreadsheet_response = drive_api.list_spreadsheets_v2(
                        folder_ids=folder_ids, page=page, page_size=page_size, search=search
                    )
                    
                    print("\n\n--debug spreadsheets response-----", spreadsheet_response)
                    spreadsheets = spreadsheet_response.get("data", [])
                    total = spreadsheet_response.get("total", 0)
                    has_more = spreadsheet_response.get("hasMore", False)
                    
                    
            # Fetch slides for selected presentations
            if type == "slides" and selected_ppts:
                print("\n\n\n\n\n--debug here---------------", type, selected_ppts)
                total_slides = 0
                for ppt in selected_ppts:
                    print("\n\n\n--debug ppt", ppt)
                    ppt_id = ppt["id"]
                    ppt_name = ppt.get("name", "Unknown Presentation")
                    try:
                        presentation_content = drive_api.fetchPresentationContent(ppt_name, ppt_id)
                        if presentation_content:
                            slide_response = drive_api.parseSlidesFromPresentationV2(
                                presentation_content, page=page, page_size=page_size, search=search
                            )
                            slides_data = slide_response.get("data", [])
                            slide_total = slide_response.get("total", 0)
                            slide_has_more = slide_response.get("hasMore", False)
                            slides.append({
                                "presentation_id": ppt_id,
                                "presentation_name": ppt_name,
                                "slides_data": slides_data,
                                "total": slide_total,
                                "hasMore": slide_has_more,
                                "page": page,
                                "pageSize": page_size
                            })
                            total_slides += slide_total
                            print(f"--debug slides fetched for presentation {ppt_name}: {slides_data}")
                    except Exception as e:
                        print(f"--debug error fetching slides for presentation {ppt_name}: {str(e)}")
                total = total_slides


            # print("--debug data fetched---------")
            # appLogger.info({"events": "fetchGoogleDriveResources", "status": "success"})

            elif type == "sheets" and selected_spreadsheets:
                print("\n\n --debug Selected spreadsheets---", selected_spreadsheets)
                total_sheets = 0
                for spreadsheet in selected_spreadsheets:
                    spreadsheet_id = spreadsheet["id"]
                    spreadsheet_type = spreadsheet.get("type", "Google Sheets")  # Default to Google Sheets
                    spreadsheet_name = spreadsheet.get("name", "Unknown Spreadsheet")
                    sheet_response = drive_api.list_sheets_in_spreadsheet_v2(
                        spreadsheet_id=spreadsheet_id,
                        spreadsheet_type=spreadsheet_type,
                        page=page,
                        page_size=page_size,
                        search=search
                    )
                    sheets_data = sheet_response.get("data", [])
                    sheet_total = sheet_response.get("total", 0)
                    sheet_has_more = sheet_response.get("hasMore", False)
                    sheets.append({
                        "spreadsheet_id": spreadsheet_id,
                        "spreadsheet_name": spreadsheet_name,
                        "sheets_data": sheets_data,
                        "total": sheet_total,
                        "hasMore": sheet_has_more,
                        "page": page,
                        "pageSize": page_size
                    })
                    total_sheets += sheet_total
                    has_more = has_more or sheet_has_more
                total = total_sheets

            
            
            
            # print("\n\n--debug type and selected_sheets: ", type, selected_sheets)
            if type == "sheet_projects" and selected_sheets:
        
                for sheet in selected_sheets:    
                    
                    spreadsheet_id = sheet.get("spreadsheet_id")
                    sheet_name = sheet.get("name")
                    spreadsheet_type = sheet.get("type", "Google Sheets")
                    if not spreadsheet_id or not sheet_name:
                        continue
                    
                    print("\n\n--debug fetching projects for sheet: ", sheet_name, spreadsheet_id, spreadsheet_type)
                    try:
                        content = drive_api.extract_sheet_content(
                            spreadsheet_id=spreadsheet_id,
                            spreadsheet_type=spreadsheet_type,
                            sheet_name=sheet_name
                        )
                        print("--debug content extracted---", len(content))
                        
                        project_response = drive_api.parse_sheet_project_content(
                            content, page=page, page_size=page_size, search=search
                        )
                        
                        projects_data = project_response.get("data", [])
                        project_total = project_response.get("total", 0)
                        project_has_more = project_response.get("hasMore", False)

                        sheet_projects_list.extend(projects_data)
                        # sheet_projects_list.append({
                        #     "spreadsheet_id": spreadsheet_id,
                        #     "sheet_name": sheet_name,
                        #     "projects_data": projects_data,
                        #     "total": project_total,
                        #     "hasMore": project_has_more,
                        #     "page": page,
                        #     "pageSize": page_size
                        # })
                        total += project_total
                        # has_more = has_more or project_has_more
                        
                        
                        print(f"--debug projects fetched for sheet {sheet_name}: {len(projects_data)}")
                        
                    except Exception as e:
                        print(f"--debug error fetching projects for sheet {sheet_name}: {str(e)}")
                        appLogger.error({"event": "fetch_sheet_projects","sheet_name": sheet_name,"error": str(e),"traceback": traceback.format_exc()})
                        
                        
                # total = total_projects
                appLogger.info({"event": "sheets", "data": len(sheet_projects_list), "status": "success"})
                # start_idx = (page - 1) * page_size
                # end_idx = start_idx + page_size
                paginated_sheet_projects = self.paginate_items_v2(
                    sheet_projects_list, page, page_size=total, total=total)

                sheet_projects_response = paginated_sheet_projects["data"]
                has_more = paginated_sheet_projects["hasMore"]
                
            # Construct response
            result = {
                "folders": all_folders if type == "folders" else [],
                "docs": docs if type == "docs" else [],
                "ppts": ppts if type == "ppt" else [],
                "slides": slides if type == "slides" else [],
                "spreadsheets": spreadsheets if type == "spreadsheet" else [],
                "sheets": sheets if type == "sheets" else [],
                "sheet_project_list": sheet_projects_response if type == "sheet_projects" else []
            }

            print("\n\n\n--debug data fetched [Result]---------", result)
            appLogger.info({"events": "fetchGoogleDriveResources", "status": "success"})

            return jsonify({
                "status": "success",
                "data": result,
                "total": total,
                "hasMore": has_more,
                "page": page,
                "pageSize": page_size
            }), 200


        except Exception as e:
            appLogger.error({"event": "error_in_fetchGoogleDriveResources","error": str(e),"traceback": traceback.format_exc()})
            print(f"--debug error in fetchGoogleDriveResources: {e}, {traceback.format_exc()}")
            return jsonify({
                "status": "error",
                "message": str(e),
                "data": {"folders": [], "docs": [], "ppts": [], "slides": [], "spreadsheets": [], "sheets": [],"sheet_project_list":[]},
                "total": 0,
                "hasMore": False,
                "page": page,
                "pageSize": page_size
            }), 500



    def paginate_items(self, items, page, page_size, total=None, hasMore=None):

        print(f"--debug paginate_items: input items length: {len(items)}")

        total = total if total is not None else len(items)
        # start_idx = (page - 1) * page_size
        # end_idx = start_idx + page_size

        start_idx = 0
        end_idx = page_size

        print("--debug paginate_items: items: ", items, "index  ", start_idx, end_idx)
        paginated_data = items[start_idx:end_idx]

        # print(f"--debug paginated_data: {paginated_data}")
        has_more = end_idx < total

        paginated_json = {
            "data": paginated_data,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "hasMore": has_more
        }
        # print(f"--debug paginated_json: {paginated_json}")
        appLogger.info({"event": "paginate_items", "data": paginated_json})
        return paginated_json

    def fetchSmartsheetSources(self, integration_type, page=1, page_size=50, search=None):
        """
        Fetch Smartsheet workspaces, folders, and sheets with combined pagination.
        """
        # print(f"--debug fetchSmartsheetSources started for integration_type: {integration_type}")
        appLogger.info({"event": "fetchSmartsheetSources",
                       "integration_type": integration_type})

        try:
            # Extract user and tenant information
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            project_id = request.decoded.get("project_id")

            page = request.args.get("page", default=1, type=int)
            page_size = request.args.get("pageSize", default=50, type=int)
            search = request.args.get("search")

            # Extract selected items from request
            request_data = request.json or {}
            selected_workspaces = request_data.get("workspaces", [])
            selected_folders = request_data.get("folders", [])

            appLogger.info({"event": "ss_metadata", "integration_type": integration_type,
                           "workspace": selected_workspaces, "folders": selected_folders})

            # Refresh access token
            token = self.refreshTokenService.refreshIntegrationAccessToken(
                tenant_id, user_id, "smartsheet", force=False)
            access_token = token["access_token"]

            # Initialize Smartsheet API handler
            smartsheet_api = Smartsheet(
                accessToken=access_token,
                user_id=user_id,
                project_id=project_id,
                tenant_id=tenant_id,
                workspaceIDs=[],
                sheetIDs=[],
            )

            # Initialize response
            response = {}

            if integration_type.lower() == "workspaces":
                # Fetch workspaces with client-side pagination
                workspaces_response = smartsheet_api.fetchWorkspaces(
                    search=search, page=page, page_size=page_size)
                response = self.paginate_items(
                    items=workspaces_response["data"],
                    page=workspaces_response["page"],
                    page_size=workspaces_response["pageSize"],
                    total=workspaces_response["total"],
                    hasMore=workspaces_response["hasMore"]
                )

            elif integration_type.lower() == "folders":
                # Collect all folder responses from selected workspaces
                all_folder_responses = []
                print("--debug workspaces select-------", selected_workspaces)

                hasMore = False
                for workspace in selected_workspaces:
                    workspace_id = workspace.get("id")
                    workspace_name = workspace.get("name")
                    if workspace_id:
                        # Fetch all folders with large page_size

                        print("--debug folder params-----", page, page_size)
                        folder_response = smartsheet_api.fetchWorkspaceFolders(
                            workspace_id, workspace_name, search=search, page=page, page_size=page_size
                        )
                        # print(f"--debug folder_response----------- {folder_response.url}")
                        # print(f"--debug folder len-------- {len(folder_response['data'])}")
                        appLogger.info(
                            {"event": "folder_response", "data": folder_response, "status": "success"})

                        if len(folder_response["data"]) >= page_size:
                            hasMore = True

                        all_folder_responses.append(folder_response)

                # Combine folder data and aggregate metadata
                all_folders = []
                total = 0
                for folder_response in all_folder_responses:
                    all_folders.extend(folder_response["data"])
                    total += folder_response["total"]

                # Apply pagination on combined folders
                response = self.paginate_items(
                    all_folders, page, page_size, total=total, hasMore=hasMore)

            elif integration_type.lower() == "sheets":
                # Collect all sheets from selected folders across workspaces
                # for workspace in selected_workspaces:
                #     workspace_id = workspace.get("id")
                #     workspace_name = workspace.get("name")
                #     if workspace_id:
                #         # Fetch workspace folders to validate selected_folders
                #         workspace_folders_response = smartsheet_api.fetchWorkspaceFolders(
                #             workspace_id, workspace_name, search=None, page=page, page_size=page_size
                #         )
                #         workspace_folders = workspace_folders_response["data"]

                #         # Determine folders to process
                #         folders_to_process = []
                #         if selected_folders:
                #             valid_folder_ids = {folder.get("id") for folder in workspace_folders}
                #             folders_to_process = [
                #                 folder for folder in selected_folders if folder.get("id") in valid_folder_ids
                #             ]
                #         else:
                #             folders_to_process = workspace_folders

                folders_ = []
                all_sheets = []
                total = 0
                hasMore = False

                for folder in selected_folders:
                    folder_id = folder.get("id")
                    folder_name = folder.get("name")
                    if folder_id:
                        # Fetch sheets directly
                        sheet_response = smartsheet_api.fetchFolderDetails(
                            folder_id, folder_name, search=search, page=page, page_size=page_size
                        )
                        print(
                            f"\n\nSheets: --debug sheet len------- {len(sheet_response['data'])}")
                        all_sheets.extend(sheet_response["data"])
                        total += sheet_response["total"]

                        if (len(sheet_response['data']) >= page_size):
                            hasMore = True

                        # Traverse subfolders if no sheets found
                        # if not sheet_response["data"] and not search:
                        #     print("--debug no sheets found in folder, traversing subfolders")
                        #     traverse_response = smartsheet_api.traverseFolders(
                        #         folder_id, folder_name, folders_, search=search, page=page, page_size=page_size
                        #     )
                        #     all_sheets.extend(traverse_response["data"])
                        #     total += traverse_response["total"]

                # pagination on combined sheets
                # total = total if total is not None else len(items)

                appLogger.info({"event": "sheets", "data": len(
                    all_sheets), "status": "success"})
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                response = self.paginate_items(
                    all_sheets[start_idx:end_idx], page, page_size, total=total, hasMore=hasMore)

            else:
                return jsonify({"status": "error", "message": f"Unsupported integration type: {integration_type}"}), 400

            return jsonify({
                "status": "success",
                "integration_type": integration_type,
                "data": response["data"],
                "total": response["total"],
                "hasMore": response["hasMore"],
                "page": response["page"],
                "pageSize": response["pageSize"]
            }), 200

        except Exception as e:
            appLogger.error({
                "function": "fetchSmartsheetSources",
                "event": "error_in_fetchSmartsheetSources",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            print("--debug error in fetchSmartsheetSources",
                  e, traceback.format_exc())
            return jsonify({"status": "error", "message": str(e)}), 500

    def fetchAdoRequiredSources(self):
        print("debug fetchAdoRequiredSources start")
        try:
            source = request.json.get("source")
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")

            team = request.json.get("board") or None
            organization = request.json.get("organization")
            project = request.json.get("project")

            project_name = request.json.get("project_name") or None
            team_name = request.json.get("board_name") or None

            token = self.refreshTokenService.refreshIntegrationAccessToken(
                tenant_id,
                user_id,
                "ado"
            )
            access_token = token["access_token"]

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }

            print(
                "fetchAdoRequiredSources hello debug ",
                source,
                tenant_id,
                user_id,
                team,
                project,
                team_name,
                project_name
            )
            if (source == 'teams'):
                url = f"https://dev.azure.com/{organization}/_apis/projects/{project}/teams?api-version=7.1"
                response = requests.get(
                    url,
                    headers=headers
                )
                if response.status_code == 200:
                    return jsonify({"status": "success", "data": response.json()}), 200
                else:
                    return jsonify({'error': 'Failed to fetch teams', 'status_code': response.status_code}), response.status_code
            
            if source == 'epic':
                appLogger.info({
                    "event": "fetchAdoRequiredSources",
                    "source": "epic",
                    "organization": organization,
                    "project_name": project_name,
                    "board_name": team_name
                })

                # -------------------------------------------------
                # 1. Fetch TEAM AREA PATHS (THIS IS THE KEY FIX)
                # -------------------------------------------------
                team_fields_url = (
                    f"https://dev.azure.com/{organization}/"
                    f"{project_name}/{team_name}/"
                    f"_apis/work/teamsettings/teamfieldvalues?api-version=7.1"
                )

                print("team field values url -- ", team_fields_url)
                team_fields_resp = requests.get(team_fields_url, headers=headers)

                if team_fields_resp.status_code != 200:
                    appLogger.error({
                        "function": "fetchAdoRequiredSources",
                        "event": "error_in_team_field_values",
                        "source": "epic",
                        "error": team_fields_resp.text,
                        "status_code": team_fields_resp.status_code
                    })
                    return jsonify({
                        "error": "Failed to fetch team area paths",
                        "status_code": team_fields_resp.status_code
                    }), team_fields_resp.status_code

                team_field_data = team_fields_resp.json()

                # Build AreaPath UNDER clauses
                area_clauses = [
                    f"[System.AreaPath] UNDER '{v['value']}'"
                    for v in team_field_data.get("values", [])
                ]

                if not area_clauses:
                    return jsonify({"status": "success", "data": []}), 200

                area_filter = " OR ".join(area_clauses)

                # -------------------------------------------------
                # 2. WIQL QUERY (BOARD-SCOPED EPICS)
                # -------------------------------------------------
                wiql_url = (
                    f"https://dev.azure.com/{organization}/"
                    f"{project_name}/_apis/wit/wiql?api-version=7.1"
                )

                query = {
                    "query": f"""
                    SELECT [System.Id], [System.Title]
                    FROM WorkItems
                    WHERE
                    [System.WorkItemType] = 'Epic'
                    AND ({area_filter})
                    """
                }

                print("epic wiql query -- ", query)
                response = requests.post(wiql_url, headers=headers, json=query)

                if response.status_code != 200:
                    appLogger.error({
                        "function": "fetchAdoRequiredSources",
                        "event": "error_in_wiql_query",
                        "source": "epic",
                        "error": response.text,
                        "status_code": response.status_code
                    })
                    return jsonify({
                        "error": "Failed to fetch epics",
                        "status_code": response.status_code
                    }), response.status_code

                work_item_ids = [wi["id"] for wi in response.json().get("workItems", [])]

                if not work_item_ids:
                    return jsonify({"status": "success", "data": []}), 200

                # -------------------------------------------------
                # 3. FETCH EPIC DETAILS (BATCHED)
                # -------------------------------------------------
                detailed_work_items = []
                batch_size = 100

                for i in range(0, len(work_item_ids), batch_size):
                    ids_batch = work_item_ids[i:i + batch_size]
                    ids_str = ",".join(map(str, ids_batch))

                    details_url = (
                        f"https://dev.azure.com/{organization}/"
                        f"{project_name}/_apis/wit/workitems"
                        f"?ids={ids_str}&api-version=7.1"
                    )

                    details_response = requests.get(details_url, headers=headers)

                    if details_response.status_code != 200:
                        appLogger.error({
                            "function": "fetchAdoRequiredSources",
                            "event": "error_in_fetch_epic_details",
                            "source": "epic",
                            "error": details_response.text,
                            "status_code": details_response.status_code
                        })
                        continue

                    epic_details = details_response.json()

                    detailed_work_items.extend([
                        {
                            "id": epic["id"],
                            "name": epic["fields"]["System.Title"]
                        }
                        for epic in epic_details.get("value", [])
                    ])

                return jsonify({"status": "success", "data": detailed_work_items}), 200

                    
        except Exception as e:
            appLogger.error({
                "function": "fetchAdoRequiredSources",
                "event": "error_in_fetchAdoRequiredSources",
                "source": "epic",
                "error": e,
                "traceback": traceback.format_exc()
            })
            # print("error in fetchAdoRequiredSources ",
            #       e, traceback.format_exc())
            return jsonify({'error': 'Failed to fetch ', 'status_code': 500}), 500

    def fetchIntegrationSourceProjects(self, integration_id, integration_type, resource_name, page=1, page_size=50, search=None, tenantID=None, userID=None):
        try:
            if tenantID:
                tenantId = tenantID
            else:
                tenantId = request.decoded.get("tenant_id")

            if userID:
                userId = userID
            else:
                userId = request.decoded.get("user_id")

            page = request.args.get("page", default=1, type=int)
            page_size = request.args.get("pageSize", default=50, type=int)
            project_id = request.args.get("project_id")
            search = request.args.get("search")
            nextPageToken = request.args.get("nextPageToken")

            response = {}
            if integration_type == "Initiatives":
                response = self.service.fetchJiraInitiatives(
                    tenantId=tenantId,
                    userId=userId,
                    resource_name=resource_name,
                    page=page,
                    page_size=page_size,
                    search=search,
                    nextPageToken=nextPageToken
                )
                # return response, 200
            elif integration_type == "Projects":
                response = self.service.fetchJiraProjects(
                    tenantId=tenantId,
                    userId=userId,
                    resource_name=resource_name,
                    page=page,
                    page_size=page_size,
                    search=search,
                    nextPageToken=nextPageToken
                )
                # return response, 200
            elif integration_type == "Epics":
                response = self.service.fetchJiraEpics(
                    tenantId=tenantId,
                    userId=userId,
                    resource_name=resource_name,
                    project_id=project_id,
                    page=page,
                    page_size=page_size,
                    search=search,
                    nextPageToken=nextPageToken
                )
                # return response, 200
            elif integration_type == "Issues":
                response = self.service.fetchJiraIssues(
                    tenantId=tenantId,
                    userId=userId,
                    resource_name=resource_name,
                    project_id=project_id,
                    page=page,
                    page_size=page_size,
                    search=search,
                    nextPageToken=nextPageToken
                )
                # return response, 200
            else:
                return jsonify({"error": f"Unsupported integration type: {integration_type}"}), 400

            # Handle error responses
            if "error" in response:
                status_code = 400 if "No project ID" in response["error"] else 500
                return jsonify({"error": response["error"]}), status_code

            # # Extract response fields
            # data = response.get("data", [])
            # total = response.get("total", len(data))
            # has_more = response.get("hasMore", (page * page_size) < total)
            # page = response.get("page", page)
            # page_size = response.get("pageSize", page_size)

            if tenantID and userID:
                return response
            return jsonify({
                "status": "success",
                **response
            }), 200

        except Exception as e:
            import traceback
            appLogger.error({
                "event": "fetchIntegrationSourceProjects",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500

    def fetchSlackDataForIntegration(self, key):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            response = []
            if (key == "channels"):
                response = self.service.fetchSlackChannels(
                    tenant_id=tenant_id, user_id=user_id, key=key)
            return jsonify({"status": "success", "data": response}), 200
        except Exception as e:
            appLogger.error({
                "event": "fetchSlackDataForIntegration",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return jsonify({"error": "Internal Server Error"}), 500


    def fetchListforProjectIntegrations(self, project_id):
        tenant_id = request.decoded.get("tenant_id")
        user_id = request.decoded.get("user_id")
        data = self.service.fetchListForProjectIntegration(tenant_id, project_id)
        return jsonify({"status": "success", "data": data}), 200
    
    def fetchProjectDataforIntegration(self, project_id):
        tenant_id = request.decoded.get("tenant_id")
        user_id = request.decoded.get("user_id")
        data = self.service.fetchProjectDataforIntegration(tenant_id, project_id)
        return jsonify({"status": "success", "data": data}), 200


    def createDummyDataAndIntegration(self):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            data = request.json.get("data")
            data = self.service.createDummyDataAndIntegration(tenant_id, user_id, data)
            return jsonify({"status": "success", "data": data}), 200
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)}), 200


    def updateTrmericDataFromIntegration(self):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            integration_mapping_id = request.json.get("integration_mapping_id")
            data = self.service.updateTrmericDataFromIntegration(integration_mapping_id)
            return jsonify({"status": "success", "data": data}), 200
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)}), 200



    # def fetchGoogleDriveResources(self):
    #     """fetching google drive resources: sheets, docs, pdfs, presentations"""
    #     print("--debug fetchGoogleDriveResources started")

    #     try:
    #         tenant_id = request.decoded.get("tenant_id")
    #         user_id = request.decoded.get("user_id")
    #         project_id = request.decoded.get("project_id")

    #         print("--debug ids-----", tenant_id, user_id, project_id)

    #         # Extract selected items from request
    #         request_data = request.json
    #         selected_folders = request_data.get("folders", [])

    #         selected_ppts = request_data.get("ppts", [])
    #         selected_slides = request_data.get("slides", [])
    #         selected_docs = request_data.get("docs", [])

    #         token = self.refreshTokenService.refreshIntegrationAccessToken(
    #             tenant_id, user_id, "drive")
    #         print("--debug drive token: ", token)

    #         access_token = token["access_token"]
    #         refresh_token = token["refresh_token"]

    #         drive_api = DriveV2(
    #             user_id=user_id,
    #             tenant_id=tenant_id,
    #             project_id=project_id,
    #             metadata={
    #                 "refresh_token": refresh_token
    #             },
    #             access_token=access_token
    #         )
    #         print("--debug drive_api: ", drive_api)

    #         all_folders = drive_api.list_top_level_folders()
    #         # print("--debug all_folders: ", all_folders)

    #         ppts = []
    #         slides = []
    #         docs = []

    #         if not selected_folders:
    #             return jsonify({"status": "success", "data": {"folders": all_folders, "docs": [], "ppts": [], "slides": []}}), 200

    #         print("--debug selected folders------", selected_folders)
    #         for folder in selected_folders:
    #             folder_id = folder["id"]
    #             folder_name = folder.get("name", "Unknown Folder")
    #             print(
    #                 f"--debug processing folder: {folder_name} ({folder_id})")

    #             folder_ppts = drive_api.list_google_presentations_v2(
    #                 folder_id=folder_id).get("presentations", [])
    #             ppts.extend(folder_ppts)
    #             print(
    #                 f"--debug presentations in folder {folder_name}: ", folder_ppts)

    #             # Fetch documents in the folder
    #             folder_docs = drive_api.list_google_documents_v2(
    #                 folder_id=folder_id).get("documents", [])
    #             docs.extend(folder_docs)
    #             print(
    #                 f"--debug documents in folder {folder_name}: ", folder_docs)

    #         # all_docs = drive_api.list_google_documents_v2()
    #         # all_ppts = drive_api.list_google_presentations_v2()
    #         # # ppts = drive_api.fetchPresentations()
    #         # # print("--debug controller all_ppts:  ", all_ppts)
    #         # ppts_ = []
    #         # slides_ = []

    #         for ppt in selected_ppts:
    #             ppt_id = ppt["id"]
    #             ppt_name = ppt["name"]
    #             if ppt_id:
    #                 try:
    #                     presentation_content = drive_api.fetchPresentationContent(
    #                         ppt_name, ppt_id)
    #                     slides_data = drive_api.parseSlidesFromPresentationV2(
    #                         presentation_content)

    #                     slides.append({
    #                         "presentation_id": ppt_id,
    #                         "presentation_name": ppt_name,
    #                         "slides_data": slides_data
    #                     })
    #                     print(
    #                         f"--debug slides fetched for presentation {ppt_name}: ", slides_data)
    #                 except Exception as e:
    #                     print(
    #                         f"--debug error fetching slides for presentation {ppt_name}: ", str(e))

    #         # Filter selected documents (optional, if UI requires specific doc details)
    #         selected_doc_ids = {doc.get("id") for doc in selected_docs}
    #         filtered_docs = [doc for doc in docs if doc["id"]
    #                          in selected_doc_ids] if selected_docs else docs

    #         print("--debug data fetched---------")
    #         appLogger.info(
    #             {"event": "fetchGoogleDriveResources", "status": "success"})
    #         # print("--debug folders: ", all_folders)
    #         # print("--debug docs: ", filtered_docs)
    #         # print("--debug ppts and slides: ", ppts, slides)

    #         result = {
    #             "folders": all_folders,  # Always return all folders for UI navigation
    #             "docs": filtered_docs,
    #             "ppts": ppts,
    #             "slides": slides
    #         }
    #         return jsonify({"status": "success", "data": result}), 200

    #     except Exception as e:
    #         appLogger.error({
    #             "function": "fetchGoogleDriveResources",
    #             "event": "error_in_fetchGoogleDriveResources",
    #             "error": e,
    #             "traceback": traceback.format_exc()
    #         })
    #         print("--debug error in fetchGoogleDriveResources",
    #               e, traceback.format_exc())
    #         return jsonify({"status": "error", "message": str(e)}), 500


    def integrationUpdateV3(self):
        tenant_id = request.json.get("tenant_id")
        ## also they can send selected project ids
        results = IntegrationDao.fetchActiveProjectMappingsFortenant(tenant_id=tenant_id)
        job_type = "integration-job"
        job_dao = JobDAO
        
        # Generate run_id
        run_id = f"integrationUpdateV3-cron-{tenant_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        total_items = len(results)
        enqueued_items = 0
        
        for res in results:
            try:
                project_id = res["trmeric_project_id"]
                integration_mapping_id = res["id"]
                job_user_id = res["user_id"]
             
                # Enqueue job
                payload = {
                    "job_type": job_type,
                    "project_id": project_id,
                    "integration_mapping_id": integration_mapping_id,
                    "run_id": run_id,
                    "total_count": total_items
                }
                job_id = job_dao.create(
                    tenant_id=tenant_id,
                    user_id=job_user_id,
                    schedule_id=None,
                    job_type=job_type,
                    payload=payload
                )
                enqueued_items += 1
                print(f"✅ Enqueued integration-cron job for tenant {tenant_id}, user {job_user_id}, project {project_id} (job_id: {job_id}, run {run_id})")
                
            except Exception as e:
                appLogger.error({
                    "event": "initiate_job_for_tenant_v2",
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                
        TangoDao.deleteTangoStatesForSessionIdAndTenantAndKey(
            session_id="",
            tenant_id=tenant_id,
            key=f"TENANT_LEVEL_INTEGRATION_INFO_{run_id}",
        )
        TangoDao.insertTangoState(
            tenant_id=tenant_id,
            user_id=job_user_id,
            key=f"TENANT_LEVEL_INTEGRATION_INFO_{run_id}",
            value=json.dumps({
                "state": 0,
                "message": "Starting..",
            }),
            session_id=""
        )
        
        return jsonify({"status": "success", "data": {}}), 200


    def integrateOnPrem(self, integration_type):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            data = request.json or {}

            base_url = data.get("base_url")
            pat_token = data.get("pat_token")

            if not base_url or not pat_token:
                return jsonify({
                    "success": False,
                    "message": "Both 'base_url' and 'pat_token' are required."
                }), 400

            metadata = {
                "base_url": base_url,
                "pat_token": pat_token,
                "auth_method": "PAT",
            }

            result = IntegrationDao.insertOrUpdateIntegrationUserConfig(
                tenant_id=tenant_id,
                user_id=user_id,
                integration_type=integration_type,
                metadata=json.dumps(metadata),
                status="Active"
            )

            return jsonify({
                "success": True,
                "message": f"{integration_type.capitalize()} On-Premise integration saved successfully.",
                "data": {"integration_userconfig_id": result}
            }), 200

        except Exception as e:
            print(f"[ERROR] integrateOnPrem({integration_type}):", e)
            return jsonify({
                "success": False,
                "message": f"Failed to save {integration_type} On-Prem integration.",
                "error": str(e)
            }), 500

    def fetchOnPremSources(self, integration_type):
        try:
            tenant_id = request.decoded.get("tenant_id")
            user_id = request.decoded.get("user_id")
            body = request.json or {}
            
            resource_type = body.get("resource_type", "projects")
            project_key = body.get("project_key")  # optional, for fetching issues/epics
            
            start_at = int(body.get("start_at", 0))
            max_results = int(body.get("max_results", 50))
            search = body.get("search")
            
            print("fetchOnPremSources body ", body)

            # Step 1: Fetch stored PAT + base_url from DB
            records = IntegrationDao.fetchActiveIntegrationForUser(
                user_id=user_id, 
                integration_type=integration_type
            )
            record = None
            if len(records) > 0:
                record = records[0]
                
            print("fetchOnPremSources check ", resource_type, record)
                
            
            if not record:
                return jsonify({
                    "success": False,
                    "message": f"No {integration_type} On-Prem configuration found."
                }), 404

            metadata = record.get("metadata")
            base_url = metadata.get("base_url")
            pat_token = metadata.get("pat_token")

            if not base_url or not pat_token:
                return jsonify({
                    "success": False,
                    "message": f"{integration_type} On-Prem credentials are incomplete."
                }), 400

            # Step 2: Initialize Jira client
            jira = JiraOnPrem(
                base_url=base_url, 
                access_token=pat_token, 
                project_key=project_key
            )

            # Step 3: Route to appropriate Jira methods
            if resource_type == "projects":
                result = jira.fetchProjects(start_at=start_at, max_results=max_results, search=search)
            elif resource_type == "issues":
                result = jira.fetchIssues(start_at=start_at, max_results=max_results, search=search)
            elif resource_type == "epics":
                result = jira.fetchEpics(start_at=start_at, max_results=max_results, search=search)
            elif resource_type == "initiatives":
                result = jira.fetchInitiatives(start_at=start_at, max_results=max_results, search=search)
            elif resource_type == "accessible_resources":
                result = jira.fetchAccessibleResources()
            else:
                return jsonify({
                    "success": False,
                    "message": f"Unsupported resource_type: {resource_type}"
                }), 400

            # Step 4: Return standardized response
            if "error" in result:
                return jsonify({
                    "success": False,
                    "message": result["error"]
                }), 500

            return jsonify({
                "success": True,
                "data": result.get("data", []),
                "total": result.get("total", len(result.get("data", []))),
                "hasMore": result.get("hasMore", False),
                "page": result.get("page"),
                "pageSize": result.get("pageSize"),
            }), 200

        except Exception as e:
            print("[ERROR] fetchOnPremSources:", e)
            return jsonify({
                "success": False,
                "message": "Failed to fetch On-Prem sources",
                "error": str(e)
            }), 500
    
    
    def run_auto_status(self):
        tenant_id = request.json.get("tenant_id")
        res = self.service.updateProjectsStatusWithIntegrationDataAndProjectBasicInfo(tenant_id)
        return jsonify({"status": "success", "data": res}), 200
