import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
import io
import base64

def serialize_dfs(dfs):
    buffer = io.BytesIO()
    
    # Create a list to store all tables
    tables = []
    
    for group, dfs_dict in dfs.items():
        for name, df in dfs_dict.items():
            # Convert columns with any string values to the string type
            for col in df.columns:
                if df[col].apply(lambda x: isinstance(x, str)).any():
                    df[col] = df[col].astype(str)
            
            # Create a PyArrow table
            table = pa.Table.from_pandas(df)
            
            # Add metadata to the table
            metadata = {"group": group, "name": name}
            table = table.replace_schema_metadata({
                **table.schema.metadata,
                **{k.encode(): v.encode() for k, v in metadata.items()}
            })
            
            tables.append(table)
    
    # Combine all tables into one
    combined_table = pa.concat_tables(tables)
    
    # Write the combined table to Parquet
    pq.write_table(combined_table, buffer)
    
    # Encode as Base64 for storing in a database as a text field
    pickled_dfs = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return pickled_dfs


def deserialize_dfs(pickled_dfs):
    # Decode the Base64 string
    buffer = io.BytesIO(base64.b64decode(pickled_dfs))
    
    # Read the Parquet file
    table = pq.read_table(buffer)
    
    # Reconstruct the original dictionary structure
    dfs = {}
    for batch in table.to_batches():
        metadata = batch.schema.metadata
        group = metadata[b'group'].decode()
        name = metadata[b'name'].decode()
        
        df = batch.to_pandas()
        
        if group not in dfs:
            dfs[group] = {}
        dfs[group][name] = df
    
    return dfs
