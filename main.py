from ingestion.loader import load_csv
from ingestion.converter import csv_to_parquet
from db.duckdb_client import DuckDBClient
from db.metadata_store import extract_metadata
from db.index_builder import build_faiss_index
from core.config import settings
import os

def run_ingestion():
    # 1. Path to CSV
    cloud_warehouse_csv_path = os.path.join(settings.DATA_RAW, "Cloud Warehouse Compersion Chart.csv")
    international_sales_csv_path = os.path.join(settings.DATA_RAW, "International sale Report.csv")

    # 2. Load CSV (simple load since it's small)
    # df = load_csv(cloud_warehouse_csv_path)

    # 3. Convert to Parquet
    cloud_warehouse_parquet_path = csv_to_parquet(cloud_warehouse_csv_path, "cloud_warehouse.parquet")
    international_sales_parquet_path = csv_to_parquet(international_sales_csv_path, "international_sales.parquet")

    # 4. Register table in DuckDB
    db = DuckDBClient()
    db.register_parquet("cloud_warehouse", cloud_warehouse_parquet_path)
    db.register_parquet("international_sales", international_sales_parquet_path)

    # 5. Extract metadata
    extract_metadata("cloud_warehouse")
    extract_metadata("international_sales")
    
    build_result = build_faiss_index()
    print("Build result:", build_result)

def test():
    """
    Extract table names from SQL using simple regex for FROM and JOIN.
    Returns a list (possibly with duplicates).
    """
    
    import re
    sql: str = """
    SELECT first_name, last_name, email
    FROM customers;
    """
    tables = []
    # capture FROM <table> and JOIN <table>
    from_matches = re.findall(r'\bFROM\s+([A-Za-z0-9_\."]+)', sql, flags=re.I)
    join_matches = re.findall(r'\bJOIN\s+([A-Za-z0-9_\."]+)', sql, flags=re.I)
    col_matches = re.findall(r'([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)', sql)
    tables.extend(from_matches)
    tables.extend(join_matches)
    print(col_matches)
    # clean table names (remove quotes/schema)
    cleaned = []
    for t in tables:
        t = t.strip().strip('"')
        # if schema.table, take last part
        if "." in t:
            t = t.split(".")[-1]
        cleaned.append(t)
    print(cleaned)
    return list(dict.fromkeys(cleaned))

if __name__ == "__main__":
    output = run_ingestion()
    print(output)
    