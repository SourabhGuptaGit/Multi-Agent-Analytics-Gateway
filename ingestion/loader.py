import os
import pandas as pd
from core.utils import logger, timed, safe_execute


@safe_execute
@timed(detailed=True)
def load_csv(file_path: str, chunksize: int = None):
    """
    Loads a CSV file.
    - If chunksize is None → loads entire CSV (good for small files)
    - If chunksize is provided → loads generator (for large files)
    """

    if not os.path.exists(file_path):
        logger.error(f"CSV file not found: {file_path}")
        return None

    logger.info(f"Loading CSV: {file_path}")

    if chunksize:
        logger.info(f"Loading in chunks of {chunksize} rows")
        return pd.read_csv(file_path, chunksize=chunksize)

    df = pd.read_csv(file_path)

    logger.success(f"CSV loaded successfully: {df.shape[0]} rows, {df.shape[1]} columns")
    return df
