# scripts/build_and_test_index.py
from db.index_builder import build_faiss_index, search_faiss
from core.config import settings

def test_faiss_build():
    # Build index (reads metadata in settings.DATA_METADATA)
    build_result = build_faiss_index()
    print("Build result:", build_result)

    # Test search
    query = "Which provider has the lowest storage cost? cloud storage pricing comparison"
    results = search_faiss(query, top_k=5)
    print("Search results:")
    for r in results:
        print(r)
