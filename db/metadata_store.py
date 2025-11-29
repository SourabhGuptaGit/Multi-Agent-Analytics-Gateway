import os
import duckdb
from core.utils import logger, ensure_dir, save_json
from core.config import settings


def extract_metadata(table_name: str):
    """
    Extracts metadata:
    - column names & types
    - 3 sample values per column
    - row count
    """
    conn = duckdb.connect(settings.DUCKDB_PATH)

    schema = conn.sql(f"DESCRIBE {table_name}").df()

    row_count = conn.sql(f"SELECT COUNT(*) as count FROM {table_name}").df()["count"][0]

    samples = {}
    for col in schema["column_name"]:
        try:
            sample_df = conn.sql(f"SELECT {col} FROM {table_name} LIMIT 3").df()
            samples[col] = sample_df[col].tolist()
        except Exception:
            samples[col] = []

    metadata = {
        "table": table_name,
        "row_count": int(row_count),
        "columns": schema.to_dict(orient="records"),
        "samples": samples
    }

    ensure_dir(settings.DATA_METADATA)
    path = os.path.join(settings.DATA_METADATA, f"{table_name}_metadata.json")
    save_json(metadata, path)

    logger.success(f"Metadata extracted for {table_name}: saved to {path}")

    return metadata

# eg. of return metadata - (just to remeber later).
# {
#   "table": "cloud_warehouse",
#   "row_count": 200,
#   "columns": [
#     {"column_name": "Provider", "column_type": "VARCHAR"},
#     {"column_name": "Storage Cost", "column_type": "DOUBLE"}
#   ],
#   "samples": {
#     "Provider": ["AWS", "Azure", "GCP"],
#     "Storage Cost": [0.023, 0.025, 0.022]
#   }
# }
