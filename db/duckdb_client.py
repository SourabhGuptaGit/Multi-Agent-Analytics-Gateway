import duckdb
from core.utils import logger, singleton
from core.config import settings

@singleton
class DuckDBClient:
    """
    DuckDB Database Client (Singleton)
    Manages:
    - Database connection
    - Table creation
    - Query execution
    """

    def __init__(self):
        logger.info(f"Initializing DuckDB at: {settings.DUCKDB_PATH}")
        self.conn = duckdb.connect(settings.DUCKDB_PATH)

    def register_parquet(self, table_name: str, parquet_path: str):
        logger.info(f"Registering table '{table_name}' from Parquet")
        self.conn.execute(f"""
            CREATE OR REPLACE TABLE {table_name} AS 
            SELECT * FROM parquet_scan('{parquet_path}');
        """)
        logger.success(f"Table '{table_name}' ready in DuckDB")

    def query(self, sql: str):
        logger.debug(f"Executing SQL: {sql}")
        return self.conn.sql(sql).df()

    def list_tables(self):
        return self.conn.sql("SHOW TABLES").df()
