import time
import duckdb
import pandas as pd

from core.utils import logger
from core.config import settings


class SQLExecutor:
    """
    Executes validated SQL against DuckDB and returns results
    in pandas DataFrame + multiple formatted structures.
    """

    def __init__(self):
        logger.info(f"Initializing DuckDB at: {settings.DUCKDB_PATH}")
        self.con = duckdb.connect(settings.DUCKDB_PATH, read_only=False)

    # -----------------------------------------------------------------------------
    # Execute SQL
    # -----------------------------------------------------------------------------
    def run_sql(self, sql: str):
        """
        Execute SQL and return:
            - dataframe
            - raw rows
            - execution time
            - success flag
            - error (if any)
        """
        start = time.time()
        logger.info(f"Executing SQL:\n{sql}")

        try:
            df: pd.DataFrame = self.con.execute(sql).df()
            exec_time = round((time.time() - start) * 1000, 3)

            logger.success(f"SQL executed successfully in {exec_time} ms")
            logger.debug(f"Returned {len(df)} rows")

            return {
                "success": True,
                "df": df,
                "rows": df.to_dict(orient="records"),
                "columns": list(df.columns),
                "execution_time_ms": exec_time,
                "error": None,
                "sql": sql
            }

        except Exception as e:
            logger.error(f"SQL Execution Error: {e}")
            return {
                "success": False,
                "df": None,
                "rows": [],
                "columns": [],
                "execution_time_ms": round((time.time() - start) * 1000, 3),
                "error": str(e),
                "sql": sql
            }

    # -----------------------------------------------------------------------------
    # Format DataFrame for downstream LLM response agent
    # -----------------------------------------------------------------------------
    def format_results(self, df: pd.DataFrame):
        """
        Convert DataFrame into:
            - markdown table
            - JSON response
            - plain text summary
        """

        if df is None or df.empty:
            return {
                "markdown": "_No results returned from SQL query._",
                "json": [],
                "text": "No results found."
            }

        # JSON
        json_records = df.to_dict(orient="records")

        # Markdown table
        markdown = df.to_markdown(index=False)

        # Plain text human-readable
        if len(df) == 1:
            summary = " | ".join(
                f"{col} = {df[col].iloc[0]}" for col in df.columns
            )
        else:
            summary = f"{len(df)} rows returned."

        return {
            "markdown": markdown,
            "json": json_records,
            "text": summary
        }
