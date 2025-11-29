from ingestion.loader import load_csv
from ingestion.converter import csv_to_parquet
from db.duckdb_client import DuckDBClient
from db.metadata_store import extract_metadata
from core.config import settings
import os

def run_ingestion():
    # 1. Path to CSV
    csv_path = os.path.join(settings.DATA_RAW, "Cloud Warehouse Compersion Chart.csv")

    # 2. Load CSV (simple load since it's small)
    df = load_csv(csv_path)

    # 3. Convert to Parquet
    parquet_path = csv_to_parquet(csv_path, "cloud_warehouse.parquet")

    # 4. Register table in DuckDB
    db = DuckDBClient()
    db.register_parquet("cloud_warehouse", parquet_path)

    # 5. Extract metadata
    extract_metadata("cloud_warehouse")


if __name__ == "__main__":
    run_ingestion()
