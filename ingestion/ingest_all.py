from main import ingest_data, rebuild_faiss

if __name__ == "__main__":
    ingest_data()
    rebuild_faiss()
    print("Full ingestion + FAISS rebuild complete.")
