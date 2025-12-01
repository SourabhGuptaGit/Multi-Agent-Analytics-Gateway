# agents/sql_validator.py
import re
from typing import Dict, List, Tuple, Optional
from difflib import get_close_matches

import sqlparse

from core.utils import logger, safe_execute
from db.duckdb_client import DuckDBClient


# ----------------------------
# Helpers: SQL parsing utilities
# ----------------------------

def _extract_tables(sql: str) -> List[str]:
    """
    Extract table names from SQL using simple regex for FROM and JOIN.
    Returns a list (possibly with duplicates).
    """
    tables = []
    # capture FROM <table> and JOIN <table>
    from_matches = re.findall(r'\bFROM\s+([A-Za-z0-9_\."]+)', sql, flags=re.I)
    join_matches = re.findall(r'\bJOIN\s+([A-Za-z0-9_\."]+)', sql, flags=re.I)
    tables.extend(from_matches)
    tables.extend(join_matches)

    # clean table names (remove quotes/schema)
    cleaned = []
    for t in tables:
        t = t.strip().strip('"')
        # if schema.table, take last part
        if "." in t:
            t = t.split(".")[-1]
        cleaned.append(t)
    return list(dict.fromkeys(cleaned))  # Reminder: adding here to preserve order, dedupe


def _extract_qualified_columns(sql: str) -> List[Tuple[str, str]]:
    """
    Extract occurrences of table.column in SQL.
    Returns list of (table, column).
    """
    matches = re.findall(r'([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)', sql)
    return matches


def _extract_select_columns(sql: str) -> List[str]:
    """
    Extract column-like tokens from the SELECT clause (unqualified and qualified).
    This is a heuristic - works for most simple SQL produced by the NL->SQL agent.
    """
    parsed = sqlparse.parse(sql)
    if not parsed:
        return []
    stmt = parsed[0]
    # find text between SELECT and FROM
    text = str(stmt)
    sel_match = re.search(r'\bSELECT\b(.*?)\bFROM\b', text, flags=re.I | re.S)
    if not sel_match:
        return []
    select_part = sel_match.group(1)
    # split on commas at top-level
    parts = [p.strip() for p in select_part.split(",")]
    cols = []
    for p in parts:
        # remove aggregate functions like SUM(...), COUNT(...) -> try to find inner table.column
        q = re.findall(r'([A-Za-z0-9_]+\.[A-Za-z0-9_]+)', p)
        if q:
            for item in q:
                cols.append(item)
            continue
        # otherwise, try to get bare column name or alias
        # remove function wrappers
        nofunc = re.sub(r'[A-Za-z0-9_]+\((.*?)\)', r'\1', p)
        # take first token before space or AS
        token = re.split(r'\s+AS\s+|\s+', nofunc, flags=re.I)[0]
        token = token.strip().strip('"')
        # ignore '*' and numeric constants
        if token and token != '*' and not re.match(r'^[0-9]+$', token):
            cols.append(token)
    # return unique
    uniq = []
    for c in cols:
        if c not in uniq:
            uniq.append(c)
    return uniq


# ----------------------------
# DB Introspection helpers
# ----------------------------

def _get_existing_tables(conn) -> List[str]:
    """
    Return list of table names present in DuckDB's main schema.
    """
    try:
        df = conn.sql("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").df()
        if "table_name" in df.columns:
            return [t for t in df["table_name"].tolist()]
        # fallback if column name differs
        return [r[0] for r in df.values.tolist()]
    except Exception as e:
        logger.error(f"Could not fetch table list: {e}")
        return []


def _get_columns_for_table(conn, table: str) -> List[str]:
    """
    Return list of column names for a given table using DESCRIBE or information_schema.
    """
    try:
        df = conn.sql(f"DESCRIBE {table}").df()
        if "column_name" in df.columns:
            return [c for c in df["column_name"].tolist()]
        # fallback: infer from select *
        return [c.lower() for c in conn.sql(f"SELECT * FROM {table} LIMIT 1").df().columns.tolist()]
    except Exception as e:
        logger.warn(f"Could not describe table {table}: {e}")
        return []


# ----------------------------
# Main Validator logic
# ----------------------------

@safe_execute
def validate_and_fix_sql(sql: str, schema_struct: Optional[Dict] = None, auto_fix: bool = True) -> Dict:
    """
    Validate SQL against DuckDB and schema_struct.
    Attempts safe auto-fixes when possible.

    Returns dict:
      {
        "sql": corrected_sql,
        "valid": bool,
        "issues": [ ... ],
        "fixes": [ ... ]  # human-readable descriptions
      }
    """
    db = DuckDBClient()
    conn = db.conn

    issues = []
    fixes = []
    original_sql = sql

    logger.info("Starting SQL validation")

    # 1) Extract referenced tables & columns
    referenced_tables = _extract_tables(sql)
    qual_cols = _extract_qualified_columns(sql)  # list of (table, col)
    select_cols = _extract_select_columns(sql)   # may contain qualified and unqualified

    logger.debug(f"Referenced tables (from SQL): {referenced_tables}")
    logger.debug(f"Qualified columns found: {qual_cols}")
    logger.debug(f"Select tokens: {select_cols}")

    # 2) Get existing tables from DB
    existing_tables = _get_existing_tables(conn)
    logger.debug(f"Existing tables in DB: {existing_tables}")

    # 3) Validate tables existence (if none referenced, we will try to infer later)
    for t in referenced_tables:
        if t not in existing_tables:
            issues.append(f"Table '{t}' does not exist in DB.")
    if issues:
        logger.warn("Table existence issues detected: " + "; ".join(issues))

    # 4) Build table -> columns mapping using DB (authoritative)
    table_columns = {}
    # If user didn't reference any table, consider all tables present in DB
    tables_to_check = referenced_tables if referenced_tables else existing_tables
    for t in tables_to_check:
        cols = _get_columns_for_table(conn, t)
        table_columns[t] = cols
        logger.debug(f"Table '{t}' columns: {cols}")

    # 5) Validate qualified columns
    for tbl, col in qual_cols:
        # if table not in table_columns (e.g., schema.table case), try to normalize
        tbl_normal = tbl
        if tbl_normal not in table_columns and "." in tbl_normal:
            tbl_normal = tbl_normal.split(".")[-1]
        if tbl_normal not in table_columns:
            issues.append(f"Referenced table '{tbl}' not found for column '{tbl}.{col}'.")
            continue
        if col not in table_columns[tbl_normal]:
            # try close match
            matches = get_close_matches(col, table_columns[tbl_normal], n=1, cutoff=0.7)
            if matches and auto_fix:
                best = matches[0]
                fixes.append(f"Column '{tbl}.{col}' corrected to '{tbl_normal}.{best}'")
                # replace occurrences of tbl.col with tbl_normal.best
                pattern = rf'\b{re.escape(tbl)}\.{re.escape(col)}\b'
                sql = re.sub(pattern, f"{tbl_normal}.{best}", sql)
            else:
                issues.append(f"Column '{tbl}.{col}' does not exist in table '{tbl_normal}'.")

    # 6) Validate unqualified columns (from SELECT or WHERE etc.)
    # For each unqualified column token, try to resolve to a single table within tables_to_check
    # Build reverse mapping col -> list of tables containing that column
    col_table_map = {}
    for t, cols in table_columns.items():
        for c in cols:
            col_table_map.setdefault(c, []).append(t)

    # Filter tokens that are qualified (contain dot) out
    unqualified_tokens = []
    for token in select_cols:
        if "." in token:
            continue
        # ignore SQL keywords like DISTINCT, COUNT, SUM etc (some may appear)
        if token.upper() in ("DISTINCT",):
            continue
        unqualified_tokens.append(token)

    # Also attempt to find unqualified columns inside WHERE clause (simple heuristic)
    where_matches = re.findall(r'\bWHERE\b(.*?)(?:GROUP BY|ORDER BY|LIMIT|$)', sql, flags=re.I | re.S)
    where_cols = []
    if where_matches:
        where_text = where_matches[0]
        # find bare words that look like columns or values; we will check for presence in col_table_map
        tokens = re.findall(r'\b([A-Za-z0-9_]+)\b', where_text)
        for tk in tokens:
            if tk.upper() in ("AND", "OR", "LIKE", "IN", "NOT", "BETWEEN", "IS", "NULL"):
                continue
            # skip numbers (simple)
            if re.match(r'^\d+$', tk):
                continue
            if tk not in unqualified_tokens:
                unqualified_tokens.append(tk)

    logger.debug(f"Unqualified tokens to resolve: {unqualified_tokens}")

    for token in unqualified_tokens:
        if token in col_table_map:
            tables_with_col = col_table_map[token]
            if len(tables_with_col) == 1:
                # unique -> safe to qualify
                chosen_table = tables_with_col[0]
                pattern = rf'\b{re.escape(token)}\b'
                # replace only unqualified occurrences (avoid replacing already qualified)
                # simple heuristic: replace token where not preceded by dot
                sql = re.sub(rf'(?<!\.)\b{re.escape(token)}\b', f"{chosen_table}.{token}", sql)
                fixes.append(f"Unqualified column '{token}' qualified to '{chosen_table}.{token}'")
            else:
                # ambiguous - multiple tables contain this column
                # if schema_struct present, prefer recommended_columns (if they include some table.column)
                resolved = False
                if schema_struct and "recommended_columns" in schema_struct:
                    for rc in schema_struct["recommended_columns"]:
                        if rc["column"] == token and rc["table"] in tables_with_col:
                            chosen_table = rc["table"]
                            sql = re.sub(rf'(?<!\.)\b{re.escape(token)}\b', f"{chosen_table}.{token}", sql)
                            fixes.append(f"Ambiguous column '{token}' resolved to '{chosen_table}.{token}' via RAG ranking")
                            resolved = True
                            break
                if not resolved:
                    # try fuzzy match per table's column names
                    best_match = None
                    for t in tables_with_col:
                        matches = get_close_matches(token, table_columns[t], n=1, cutoff=0.8)
                        if matches:
                            best_match = (t, matches[0])
                            break
                    if best_match and auto_fix:
                        t, bestc = best_match
                        sql = re.sub(rf'(?<!\.)\b{re.escape(token)}\b', f"{t}.{bestc}", sql)
                        fixes.append(f"Ambiguous token '{token}' replaced by best fuzzy match '{t}.{bestc}'")
                    else:
                        issues.append(f"Ambiguous column '{token}' appears in tables: {tables_with_col}. Please clarify.")
        else:
            # token not found as a column name in any table -> could be a literal value (SKU) or alias
            # If the token looks like a quoted literal, skip
            # we'll not treat it as an issue immediately
            pass

    # 7) Final sanity check with EXPLAIN or a lightweight run (LIMIT 1)
    try:
        # Try to run EXPLAIN to check semantics
        check_sql = f"EXPLAIN {sql}"
        conn.sql(check_sql).df()
        valid = True
        logger.success("SQL validated successfully with EXPLAIN.")
    except Exception as e:
        # Attempt to run with LIMIT 1 as last resort (some statements may not support EXPLAIN)
        try:
            conn.sql(sql + " LIMIT 1").df()
            valid = True
            logger.success("SQL executed with LIMIT 1 (validation pass).")
        except Exception as e2:
            valid = False
            issues.append(f"Execution error: {str(e2)}")
            logger.error(f"SQL validation failed: {e2}")

    result = {
        "sql": sql,
        "valid": valid,
        "issues": issues,
        "fixes": fixes,
        "original_sql": original_sql
    }
    logger.debug(f"Validator result: {result}")
    return result
