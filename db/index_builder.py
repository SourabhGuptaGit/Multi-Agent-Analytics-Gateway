# db/index_builder.py
import os
import json
from typing import List, Dict, Tuple
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from core.utils import logger, ensure_dir, save_json, load_json, timed, safe_execute
from core.config import settings

# model that outputs 768-dim embeddings that should match settings.VECTOR_DIM
EMBEDDING_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"


def _model_loader():
    """
    Load sentence-transformers model (cached by SentenceTransformers library).
    """
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    # Verify dimension (safety)
    dim = model.get_sentence_embedding_dimension()
    if dim != settings.VECTOR_DIM:
        logger.warn(
            f"Embedding dim {dim} != settings.VECTOR_DIM ({settings.VECTOR_DIM}). "
            "Consider updating settings.VECTOR_DIM to match model."
        )
    return model


def _metadata_files_from_dir(metadata_dir: str) -> List[str]:
    """
    List metadata JSON files stored in settings.DATA_METADATA
    """
    files = []
    for fn in os.listdir(metadata_dir):
        if fn.endswith("_metadata.json"):
            files.append(os.path.join(metadata_dir, fn))
    return files


def _make_docs_from_metadata(metadata: Dict) -> List[Tuple[str, Dict]]:
    """
    Given a metadata object (from metadata_store.extract_metadata),
    create "documents" to embed.

    Returns list of tuples: (doc_text, metadata_reference)

    Example doc_text might include:
      - table name
      - column name
      - type
      - samples
    """
    docs = []
    table = metadata.get("table", "unknown_table")
    columns = metadata.get("columns", [])
    samples = metadata.get("samples", {})

    for col in columns:
        col_name = col.get("column_name")
        col_type = col.get("column_type", "")
        sample_vals = samples.get(col_name, [])
        # Build a small textual description - concise
        sample_str = ", ".join([str(x) for x in sample_vals]) if sample_vals else "no-samples"
        doc_text = (
            f"table: {table}; column: {col_name}; type: {col_type}; "
            f"samples: {sample_str}"
        )
        # metadata reference that we store with the doc
        meta_ref = {
            "table": table,
            "column": col_name,
            "type": col_type,
            "samples": sample_vals
        }
        docs.append((doc_text, meta_ref))
    return docs


@safe_execute
@timed
def build_faiss_index(metadata_dir: str = None, index_path: str = None, overwrite: bool = False):
    """
    Build FAISS index from metadata JSON files.

    - metadata_dir: directory where metadata JSONs are stored
    - index_path: where to save faiss binary & mapping
    - overwrite: if True, rebuild even if index exists
    """

    metadata_dir = metadata_dir or settings.DATA_METADATA
    index_path = index_path or settings.INDEX_PATH
    mapping_path = index_path + ".mapping.json"

    ensure_dir(os.path.dirname(index_path))
    ensure_dir(metadata_dir)

    model = _model_loader()

    # gather metadata JSON files
    files = _metadata_files_from_dir(metadata_dir)
    if not files:
        logger.warn("No metadata files found to build index.")
        return None

    docs = []
    metadata_refs = []
    for f in files:
        logger.info(f"Loading metadata: {f}")
        m = load_json(f)
        if not m:
            continue
        doc_tuples = _make_docs_from_metadata(m)
        for doc_text, meta_ref in doc_tuples:
            docs.append(doc_text)
            metadata_refs.append(meta_ref)

    if not docs:
        logger.warn("No documents created from metadata.")
        return None

    # Create embeddings in batches
    logger.info(f"Creating embeddings for {len(docs)} docs...")
    embeddings = model.encode(docs, show_progress_bar=True, convert_to_numpy=True)
    embeddings = np.array(embeddings).astype("float32")

    # validate dims
    dim = embeddings.shape[1]
    logger.info(f"Embeddings shape: {embeddings.shape}")
    if dim != settings.VECTOR_DIM:
        logger.warn(f"Embedding dim {dim} != settings.VECTOR_DIM ({settings.VECTOR_DIM}).")

    # Build FAISS index (IndexFlatIP with normalization) — we will use inner product on normalized vectors for cosine
    logger.info("Normalizing embeddings for cosine-sim search...")
    faiss.normalize_L2(embeddings)

    logger.info("Building FAISS index (IndexFlatIP)...")
    index = faiss.IndexFlatIP(dim) # is good for upto 100k vectors but use (IVF — Inverted File Index) -> HNSW
    index.add(embeddings)  # add vectors; ids are implicit: 0..n-1

    # Save index and mapping
    logger.info(f"Saving FAISS index to: {index_path}")
    faiss.write_index(index, index_path)

    logger.info(f"Saving metadata mapping to: {mapping_path}")
    save_json({"mapping": metadata_refs, "docs": docs}, mapping_path)

    logger.success(f"FAISS index built with {index.ntotal} vectors.")
    return {"index_path": index_path, "mapping_path": mapping_path, "n_vectors": index.ntotal}


def load_faiss_index(index_path: str = None):
    """
    Load FAISS index and mapping.
    Returns (index, mapping_list)
    """
    index_path = index_path or settings.INDEX_PATH
    mapping_path = index_path + ".mapping.json"

    if not os.path.exists(index_path):
        logger.error(f"FAISS index not found at: {index_path}")
        return None, None

    logger.info(f"Loading FAISS index from: {index_path}")
    index = faiss.read_index(index_path)

    mapping = load_json(mapping_path)
    if mapping is None:
        logger.warn("Mapping file not found or empty.")
        return index, None

    return index, mapping.get("mapping", [])


@safe_execute
def search_faiss(query: str, top_k: int = 5, index_path: str = None) -> List[Dict]:
    """
    Search the FAISS index for top_k relevant metadata docs for `query`.
    Returns list of dicts:
      { "score": float, "table": str, "column": str, "type": str, "samples": [...] , "doc": "..." }
    """
    index_path = index_path or settings.INDEX_PATH
    index, mapping = load_faiss_index(index_path)
    if index is None:
        return []

    model = _model_loader()
    q_emb = model.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(q_emb)

    D, I = index.search(q_emb, top_k)  # D: scores, I: indices
    results = []
    for score, idx in zip(D[0], I[0]):
        if idx < 0:
            continue
        meta = mapping[idx] if mapping and idx < len(mapping) else {}
        doc_text = None
        # mapping file contains docs also (if saved)
        try:
            mapping_full = load_json(index_path + ".mapping.json")
            docs = mapping_full.get("docs", [])
            doc_text = docs[idx] if idx < len(docs) else None
        except Exception:
            doc_text = None

        results.append({
            "score": float(score),
            "table": meta.get("table"),
            "column": meta.get("column"),
            "type": meta.get("type"),
            "samples": meta.get("samples"),
            "doc": doc_text
        })
    save_json(results, "search_faiss.json")
    return results
