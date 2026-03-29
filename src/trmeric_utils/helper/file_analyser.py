import pandas as pd
import io
import traceback
from typing import Optional, Dict, Tuple
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_s3.s3 import S3Service
from src.trmeric_database.dao import FileDao

DEFAULT_S3_FILE_PARAMS = {"files_s3_keys_to_read": []}

class FileAnalyzer:
    """
    A utility class to analyze files uploaded to S3, providing full content for text-based files
    (TXT, DOC, DOCX, PDF) and structured metadata (sheet names, headers, null counts, previews)
    for tabular files (CSV, Excel).
    """
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        self.s3_service = S3Service()

    def analyze_files(self, params: Optional[Dict] = DEFAULT_S3_FILE_PARAMS) -> Dict:
        """
        Analyzes files uploaded in the current session from S3 using provided keys.
        Supports CSV, Excel (multi-sheet), DOCX, DOC, PDF, and TXT formats.
        Returns full content for text-based files; structured metadata for CSV/Excel.
        """
        try:
            params = params.copy() if params else DEFAULT_S3_FILE_PARAMS.copy()
            files_s3_keys_to_read = params.get("files_s3_keys_to_read", [])
            
            if not files_s3_keys_to_read:
                return {
                    'session_id': 'current_session',
                    'files': [],
                    'file_count': 0
                }
            
            files = []
            
            for s3_key in files_s3_keys_to_read:
                try:
                    print("analyze_files ", s3_key)
                    # Retrieve file metadata from database
                    file_info = FileDao.FileUploadedDetailsS3Key(s3_key)
                    
                    print("analyze_files fileinfo ", file_info)
                    
                    filename = file_info.get('filename', f'{s3_key}') if file_info else f'{s3_key}'
                    upload_timestamp = file_info.get('created_on', '') if file_info else ''
                    file_id = file_info.get('file_id',None) or None
                    
                    # Download file content and determine type
                    content, content_type = self._download_file_with_content_type(s3_key)
                    file_type = self._determine_file_type(s3_key, filename, content_type)
                    
                    print("analyze_files fileinfo ", content_type, file_type)
                    
                    # Initialize file result
                    file_result = {
                        'file_s3_key': s3_key,
                        'filename': filename,
                        'file_type': file_type,
                        'upload_timestamp': upload_timestamp,
                        'content': None,
                        'analysis': None,
                        'error': None,
                        'file_id': file_id,
                    }
                    
                    # Handle unreadable files
                    if content is None:
                        file_result['error'] = f"Could not read file {s3_key}"
                        files.append(file_result)
                        continue
                    
                    # Process based on file type
                    if file_type in ['txt', 'doc', 'docx', 'pdf']:
                        file_result['content'] = content  # Full content
                        file_result['analysis'] = self._analyze_text_content(file_type, content)
                    elif file_type in ['csv', 'xlsx']:
                        df_dict = self.s3_service.download_file_as_pd_v2(s3_key, filename=filename)
                        if df_dict:
                            file_result['content'] = content[:2000] if len(content) > 2000 else content  # Preview
                            file_result['analysis'] = self._analyze_tabular_data(file_type, df_dict, content)
                        else:
                            file_result['error'] = f"Could not parse {file_type.upper()} file"
                    
                    files.append(file_result)
                
                except Exception as e:
                    appLogger.error({
                        "function": "analyze_files",
                        "error": f"Failed to process file {s3_key}: {str(e)}",
                        "traceback": traceback.format_exc(),
                        "tenant_id": self.tenant_id
                    })
                    files.append({
                        'file_s3_key': s3_key,
                        'filename': f'{s3_key}',
                        'file_type': 'unknown',
                        'upload_timestamp': '',
                        'content': None,
                        'analysis': None,
                        'error': f"Failed to process file: {str(e)}",
                        'file_id': None,
                    })
            
            return {
                'session_id': 'current_session',
                'files': files,
                'file_count': len(files_s3_keys_to_read)
            }
                
        except Exception as e:
            appLogger.error({
                "function": "analyze_files",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                'session_id': 'current_session',
                'files': [],
                'file_count': 0
            }

    def _download_file_with_content_type(self, s3_key: str) -> Tuple[Optional[str], str]:
        """Download file from S3 and return content and ContentType."""
        try:
            response = self.s3_service.s3.get_object(Bucket=self.s3_service.bucket_name, Key=s3_key)
            binary_content = response['Body'].read()
            content_type = response.get('ContentType', 'application/octet-stream')
            content = self.s3_service._decode_text(binary_content) if content_type.startswith('text/') else self.s3_service.download_file_as_text(s3_key)
            return content, content_type
        except Exception as e:
            appLogger.error({
                "function": "_download_file_with_content_type",
                "error": f"Failed to download file {s3_key}: {str(e)}",
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return None, 'application/octet-stream'

    def _determine_file_type(self, s3_key: str, filename: str, content_type: str) -> str:
        """Determine file type based on filename, S3 key, or ContentType."""
        try:
            # Map extensions to file types
            extension_map = {
                'xlsx': 'xlsx', 'xls': 'xlsx', 'csv': 'csv',
                'docx': 'docx', 'doc': 'doc', 'pdf': 'pdf', 'txt': 'txt',
                'pptx': 'pptx', 'ppt': 'ppt'
            }
            # Check filename or S3 key extension
            ext = filename.lower().split('.')[-1] if '.' in filename else s3_key.lower().split('.')[-1]
            if ext in extension_map:
                return extension_map[ext]
            
            # Check ContentType
            content_type_map = {
                'application/pdf': 'pdf',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
                'text/csv': 'csv',
                'application/msword': 'doc',
                'text/plain': 'txt',
                'text/html': 'txt',
                'application/vnd.ms-powerpoint': 'ppt',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx'
            }
            return content_type_map.get(content_type) or 'txt'
        except Exception:
            appLogger.error({
                "function": "_determine_file_type",
                "error": f"Failed to determine file type for {s3_key}: {traceback.format_exc()}",
                "tenant_id": self.tenant_id
            })
            return 'txt'

    def _analyze_text_content(self, file_type: str, content: str) -> Dict:
        """Analyze text-based file content (TXT, DOC, DOCX, PDF)."""
        try:
            paragraphs = content.split('\n')
            return {
                'content_type': file_type,
                'content_length': len(content),
                'paragraph_count': len([p for p in paragraphs if p.strip()]),
                # 'preview': content[:500] if len(content) > 500 else content
            }
        except Exception as e:
            appLogger.error({
                "function": f"_analyze_{file_type}_content",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                'content_type': file_type,
                'content_length': len(content),
                'error': f"Failed to analyze {file_type} content: {str(e)}"
            }

    def _analyze_tabular_data(self, file_type: str, df_dict: Dict, raw_content: str) -> Dict:
        """Analyze CSV or Excel file content."""
        try:
            print("_analyze_tabular_data" , file_type)
            analysis = {
                'content_type': 'spreadsheet' if file_type == 'csv' else 'excel_multi_sheet',
                'content_length': len(raw_content),
                # 'preview': raw_content[:2000] if len(raw_content) > 2000 else raw_content
            }
            
            if file_type == 'csv':
                analysis['sheets'] = [self._analyze_spreadsheet(df_dict.get('Sheet1', pd.DataFrame()))]
            else:  # Excel
                analysis['sheet_count'] = len(df_dict)
                analysis['sheets'] = [
                    self._analyze_spreadsheet(df, sheet_name)
                    for sheet_name, df in df_dict.items()
                ]
            
            return analysis
        except Exception as e:
            appLogger.error({
                "function": "_analyze_tabular_data",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                'content_type': file_type,
                'content_length': len(raw_content),
                'error': f"Failed to analyze {file_type} file: {str(e)}"
            }

    def _analyze_spreadsheet(self, df: pd.DataFrame, sheet_name: str = 'Sheet1') -> Dict:
        """Analyze a single spreadsheet (CSV or Excel sheet)."""
        try:
            print("_analyze_spreadsheet ", sheet_name)
            if df is None or df.empty:
                return {'sheet_name': sheet_name, 'error': 'Empty or invalid sheet'}
            
            return {
                'sheet_name': sheet_name,
                'column_count': len(df.columns),
                'row_count': len(df),
                'columns': [
                    {
                        'name': col,
                        'data_type': str(df[col].dtype),
                        'sample_values': df[col].dropna().head(3).tolist(),
                        'null_count': int(df[col].isnull().sum())
                    }
                    for col in df.columns
                ],
                'preview_rows': df.head(5).to_dict('records')
            }
        except Exception as e:
            appLogger.error({
                "function": "_analyze_spreadsheet",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                'sheet_name': sheet_name,
                'error': f"Failed to analyze spreadsheet: {str(e)}"
            }
            
    def _analyze_text_content(self, file_type: str, content: str) -> Dict:
        """Analyze text-based file content (TXT, DOC, DOCX, PDF) for project extraction."""
        try:
            paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
            # Detect potential project boundaries (e.g., headers like "Project:", bullet points)
            project_indicators = []
            for idx, para in enumerate(paragraphs):
                if any(keyword in para.lower() for keyword in ['project:', 'title:', 'objective:', 'milestone:', 'budget:']):
                    project_indicators.append({
                        'index': idx,
                        'text': para,
                        'potential_field': para.split(':')[0].strip().lower()
                    })
            
            return {
                'content_type': file_type,
                'content_length': len(content),
                'paragraph_count': len(paragraphs),
                'project_indicators': project_indicators,
                'preview': content[:500] if len(content) > 500 else content
            }
        except Exception as e:
            appLogger.error({
                "function": f"_analyze_{file_type}_content",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {
                'content_type': file_type,
                'content_length': len(content),
                'error': f"Failed to analyze {file_type} content: {str(e)}"
            }
        
