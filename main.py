import argparse
import os
from core.utils import logger
from ingestion.loader import load_csv
from ingestion.converter import csv_to_parquet
from db.duckdb_client import DuckDBClient
from db.metadata_store import extract_metadata
from db.index_builder import build_faiss_index
from core.config import settings


def ingest_data():
    logger.info("Starting ingestion pipeline...")

    raw_dir = settings.DATA_RAW
    files = [f for f in os.listdir(raw_dir) if f.endswith(".csv")]

    if not files:
        logger.error("No CSV files found in data/raw/. Add files and retry.")
        return

    db = DuckDBClient()

    parquet_paths = []

    # 1. Convert CSV → Parquet + register into DB
    for file in files:
        csv_path = os.path.join(raw_dir, file)

        table_name = (
            file.replace(".csv", "")
                .replace(" ", "_")
                .replace("-", "_")
                .lower()
        )

        logger.info(f"Processing CSV → Parquet for table: {table_name}")

        parquet_path = csv_to_parquet(csv_path, f"{table_name}.parquet")
        parquet_paths.append((table_name, parquet_path))

        db.register_parquet(table_name, parquet_path)

    # 2. Extract metadata JSON for each table
    for table_name, _ in parquet_paths:
        extract_metadata(table_name)

    logger.success("Ingestion + metadata extraction completed.")


def rebuild_faiss():
    logger.info("Rebuilding FAISS vector index...")
    build_faiss_index()
    logger.success("FAISS index created successfully.")


if __name__ == "__main__":
    """
    main.py — Data Ingestion + Metadata Extraction + FAISS Index Builder

    Run:
        python main.py ingest
        python main.py rebuild
    """

    parser = argparse.ArgumentParser(description="Multi-Agent Analytics Gateway (MAAG) Pipeline Utility")

    parser.add_argument(
        "action",
        choices=["ingest", "rebuild"],
        help="Choose pipeline action: ingest → load CSVs, rebuild → rebuild FAISS index",
    )

    args = parser.parse_args()

    if args.action == "ingest":
        ingest_data()

    elif args.action == "rebuild":
        rebuild_faiss()
