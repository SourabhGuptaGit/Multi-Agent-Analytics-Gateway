import os
import duckdb
import pandas as pd
from core.utils import logger, ensure_dir, timed, safe_execute
from core.config import settings


@safe_execute
@timed(detailed=True)
def csv_to_parquet(csv_path: str, parquet_name: str):
    """
    Converts CSV to Parquet using DuckDB (fastest safe method).
    Saves output to: data/processed/parquet_name
    """
    ensure_dir(settings.DATA_PROCESSED)

    parquet_path = os.path.join(settings.DATA_PROCESSED, parquet_name)

    logger.info(f"Converting CSV → Parquet")
    logger.debug(f"Output: {parquet_path}")

    duckdb.sql(f"""
        COPY (
            SELECT * FROM read_csv_auto('{csv_path}')
        ) TO '{parquet_path}' (FORMAT PARQUET);
    """)

    logger.success(f"Parquet file created: {parquet_path}")
    return parquet_path
