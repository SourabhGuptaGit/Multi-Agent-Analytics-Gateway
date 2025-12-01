import os
from typing import List, Dict, Tuple, Set
from collections import defaultdict

from core.utils import logger, safe_execute, save_json
from core.config import settings
from db.index_builder import search_faiss, load_faiss_index
from db.duckdb_client import DuckDBClient

# -----------------------------
# RAG: Retrieval-Augmented Generation
# -----------------------------
#
# Purpose:
#   - Use FAISS to retrieve relevant metadata "hits" for a user query
#   - Consolidate hits into a compact schema & sample block
#   - Provide a list of recommended table/column names (structured) for NL->SQL agent
#
# Main functions:
#   - retrieve_metadata_hits(query, top_k)
#   - consolidate_hits_to_schema(hits)
#   - build_prompt_context(query, top_k)
#
# Output:
#   - build_prompt_context returns a string (context block) and a structured dict of columns to use
#
# Notes:
#   - This works across multiple metadata files/tables because the FAISS index was global
#   - It deduplicates columns and aggregates hits by table
#   - The NL->SQL agent should append this context to its prompt before asking the model to produce SQL
#


@safe_execute
def retrieve_metadata_hits(query: str, top_k: int = 8) -> List[Dict]:
    """
    Run FAISS search and return a list of hits.
    Each hit is dict with keys: score, table, column, type, samples, doc
    """
    logger.info(f"Retrieving top {top_k} metadata hits for query: {query!r}")
    hits = search_faiss(query, top_k=top_k)
    if not hits:
        logger.warn("No metadata hits returned by FAISS.")
        return []
    logger.info(f"Retrieved {len(hits)} hits from FAISS")
    return hits


def _group_hits_by_table(hits: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group hits by table name. Returns dict: table -> [hit, ...]
    """
    grouped = defaultdict(list)
    for h in hits:
        table = h.get("table") or "unknown_table"
        grouped[table].append(h)
    return grouped


@safe_execute
def _describe_table_from_duckdb(table_name: str) -> List[Dict]:
    """
    Use DuckDB DESCRIBE to get authoritative column types & names.
    This is used to construct the schema block (more precise than metadata samples).
    Returns a list of dict entries: {"column_name": ..., "column_type": ...}
    """
    try:
        db = DuckDBClient()
        df = db.conn.sql(f"DESCRIBE {table_name}").df()
        # convert to list of dicts (consistent shape with metadata_store)
        cols = []
        for _, row in df.iterrows():
            cols.append({
                "column_name": row["column_name"],
                "column_type": row.get("column_type", "UNKNOWN")
            })
        return cols
    except Exception as e:
        logger.warn(f"Could not describe table {table_name}: {e}")
        return []


def consolidate_hits_to_schema(hits: List[Dict]) -> Dict:
    """
    Consolidate FAISS hits into a structured schema snippet.
    - Deduplicate columns
    - Fetch authoritative types from DuckDB (if available)
    - Return:
        {
          "tables": {
             "table_name": {
                 "columns": {
                    "col_name": {
                       "type": "...",
                       "samples": [...],
                       "score": 0.123  # highest score among hits for that col
                    }, ...
                 },
                 "row_count": optional-int
             }, ...
          },
          "recommended_columns": [ {"table": t, "column": c}, ... ]
        }
    """
    schema = {"tables": {}, "recommended_columns": []}
    if not hits:
        return schema

    grouped = _group_hits_by_table(hits) # {"table": [column-wise_hit, ...]}

    for table, table_hits in grouped.items():
        # Build a column-level dict for this table
        cols = {}
        for hit in table_hits:
            col_name = hit.get("column")
            if not col_name:
                continue
            current = cols.get(col_name, {"samples": [], "score": float("-inf"), "type": hit.get("type")})
            # prefer higher score (FAISS relevance)
            if hit.get("score", 0.0) > current.get("score", -1):
                current["score"] = hit.get("score", 0.0)
                # update type if hit contains it
                if hit.get("type"):
                    current["type"] = hit.get("type")
            # append sample values (keeping uniqueness, small number)
            samples = current.get("samples", [])
            for s in hit.get("samples", []) or []:
                if s not in samples:
                    samples.append(s)
                    if len(samples) >= 5:
                        break
            current["samples"] = samples
            cols[col_name] = current

        # Attempt to get authoritative types from DuckDB and merge
        dd_cols = _describe_table_from_duckdb(table)
        dd_map = {c["column_name"]: c["column_type"] for c in dd_cols} if dd_cols else {}

        for cn, info in cols.items():
            if cn in dd_map:
                info["type"] = dd_map[cn]
            # string-ify type to avoid weird objects
            info["type"] = str(info.get("type", "UNKNOWN"))

        schema["tables"][table] = {"columns": cols}

    # build recommended_columns list (flattened, sorted by score desc)
    recs = []
    for table, tinfo in schema["tables"].items():
        for cn, info in tinfo["columns"].items():
            recs.append({"table": table, "column": cn, "score": info.get("score", 0.0)})
    # sort by score descending and dedupe (table+column unique)
    recs = sorted(recs, key=lambda x: x["score"], reverse=True)

    seen = set()
    final_recs = []
    for r in recs:
        key = f"{r['table']}::{r['column']}"
        if key in seen:
            continue
        seen.add(key)
        final_recs.append({"table": r["table"], "column": r["column"]})
    schema["recommended_columns"] = final_recs
    
    save_json(schema, os.path.join(settings.DATA_METADATA, "schema.json")) # for Debuging
    return schema


def _format_schema_block(schema: Dict, max_columns_per_table: int = 10) -> str:
    """
    Produce a compact human-readable schema block suitable to prepend to an LLM prompt.
    Format:

    TABLE: table_name
      columns:
        - column_name (TYPE) — samples: a, b, c
        - ...
    """
    if not schema.get("tables"):
        return ""

    parts = ["# Dataset Schema (extracted via RAG):"]
    for table, info in schema["tables"].items():
        parts.append(f"TABLE: {table}")
        parts.append("  columns:")
        col_items = list(info["columns"].items())[:max_columns_per_table]
        for col_name, meta in col_items:
            sample_str = ", ".join([str(x) for x in (meta.get("samples") or [])][:3]) or "no-samples"
            parts.append(f"    - {col_name} ({meta.get('type')}) — samples: {sample_str}")
        parts.append("")  # blank line between tables
    return "\n".join(parts)


@safe_execute
def build_prompt_context(query: str, top_k: int = 8, max_columns_per_table: int = 10) -> Tuple[str, Dict]:
    """
    High-level function used by the NL->SQL agent.

    Returns:
      - context_str: string to prepend into the LLM prompt
      - structured_schema: the dict returned by consolidate_hits_to_schema

    The context string contains:
      1. Short retrieval note
      2. The schema block (tables & columns)
      3. Suggested columns in a simple list (best to use for SQL generation)
    """
    hits = retrieve_metadata_hits(query, top_k=top_k)
    if not hits:
        return "", {"tables": {}, "recommended_columns": []}

    structured = consolidate_hits_to_schema(hits)
    schema_block = _format_schema_block(structured, max_columns_per_table=max_columns_per_table)

    # recommended columns (top-ordered)
    recs = structured.get("recommended_columns", [])[:20]
    rec_lines = []
    for r in recs:
        rec_lines.append(f"{r['table']}.{r['column']}")

    rec_block = "# Recommended columns (by relevance):\n" + ("\n".join(["- " + l for l in rec_lines]) if rec_lines else "- none")

    context_parts = [
        f"# User question: {query}",
        "",
        schema_block,
        "",
        rec_block,
        "",
        "# Note: Use the above table/column names exactly as provided when writing SQL. If a column doesn't exist, validate with DESCRIBE."
    ]
    context_str = "\n".join([p for p in context_parts if p])
    
    return context_str, structured
