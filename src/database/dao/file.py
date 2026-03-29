from src.trmeric_database.Database import db_instance

class FileDao:

    @staticmethod
    def getfilesByID(file_ids: list[int]):

        file_ids_str = f"({', '.join(map(str, file_ids))})"
        query = f"""
            select 
                id as file_id,
                type as file_type,
                file as s3_key,
                original_filename as filename,
                created_on
            from 
                docs_documents
            where 
                id in {file_ids_str}
            order by
                created_on DESC
        """
        # print("--debug file_ids query0--------", query)
        return db_instance.retrieveSQLQueryOld(query)

    def filesUploadedInS3(sessionID: int, userID:int, file_type:str = 'TANGO'):
        query = f"""
            select 
                id as file_id,
                type as file_type,
                file as s3_key,
                original_filename as filename,
                created_on,
                customer_id,
                project_id,
                provider_id
            from 
                docs_documents
            where 
                session_id = '{sessionID}'
                and created_by_id = {userID}
                and type = '{file_type}'
                and deleted_on IS NULL
            order by
                created_on DESC
        """
        return db_instance.retrieveSQLQueryOld(query)
    
    
    def filesUploadedInS3ForSession(sessionID: int):
        query = f"""
            select 
                id as file_id,
                type as file_type,
                file as s3_key,
                original_filename as filename,
                created_on,
                customer_id,
                project_id,
                provider_id
            from 
                docs_documents
            where 
                session_id = '{sessionID}'
                and deleted_on IS NULL
            order by
                created_on DESC
        """
        return db_instance.retrieveSQLQueryOld(query)


    
    def filesUploadedInS3ForKey(key):
        query = f"""
            select 
                id as file_id,
                type as file_type,
                file as s3_key,
                original_filename as filename,
                created_on,
                customer_id,
                project_id,
                provider_id
            from 
                docs_documents
            where 
                type = '{key}'
                and deleted_on IS NULL
            order by
                created_on DESC
        """
        return db_instance.retrieveSQLQueryOld(query)



    def s3ToOriginalFileMapping(sessionID: int, userID:int, file_type:str = 'TANGO'):
        """Create a mapping of s3_key to original filename."""
        files = FileDao.filesUploadedInS3(sessionID,userID,file_type)

        file_mapping = {file['s3_key']:file['filename'] for file in files}
        return file_mapping
    
    
    def FilesUploadedInS3ForSession(sessionID: int):
        """Create a mapping of s3_key to original filename."""
        files = FileDao.filesUploadedInS3ForSession(sessionID)
    
        return [
            {
                "file_id": file["file_id"],
                "s3_key": file['s3_key'],
                "filename": file['filename'],
                "file_type": file['file_type'],
                "created_on": file['created_on']
            } for file in files
        ]

       
       
    def FilesUploadedInS3ForKey(key):
        """Create a mapping of s3_key to original filename."""
        files = FileDao.filesUploadedInS3ForKey(key)

    
        return [
            {
                "file_id": file["file_id"],
                "s3_key": file['s3_key'],
                "filename": file['filename'],
                "file_type": file['file_type'],
                "created_on": file['created_on']
            } for file in files
        ]
        
    def FileUploadedInType(_type = '', user_id = None):
        conditions = ""
        if not _type:
            return []
        
        conditions += f" type = '{_type}' and deleted_on IS NULL "
        if user_id:
            conditions += f"and created_by_id = {user_id}"
        query = f"""
            select 
                id as file_id,
                type as file_type,
                file as s3_key,
                original_filename as filename,
                created_on,
                customer_id,
                project_id,
                provider_id
            from 
                docs_documents
            where 
                {conditions}
            order by
                created_on DESC
        """
        try:
            # print("files fetch query ", query)
            return db_instance.retrieveSQLQueryOld(query)
        except Exception as e:
            return []



    def FileUploadedDetailsS3Key(s3_key):
        conditions = f" file = '{s3_key}' "
        query = f"""
            select 
                id as file_id,
                type as file_type,
                file as s3_key,
                created_on,
                original_filename as filename
            from 
                docs_documents
            where 
                {conditions}
            order by
                created_on DESC
        """
        try:
            res = db_instance.retrieveSQLQueryOld(query)
            if len(res) > 0:
                return res[0]
            raise Exception("Not present")
        except Exception as e:
            print("error in FileUploadedDetailsS3Key ", e)
            return None



        

