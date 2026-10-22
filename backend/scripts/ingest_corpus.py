"""One-off corpus ingestion — pushes the 14-doc corpus into Azure AI Search. Run manually:

    python scripts/ingest_corpus.py

Requires the Search Index Data Contributor role on the running identity (managed
identity in Azure; your own az-login principal for local/manual runs) — see
infra/modules/build/ai-search.bicep for the managed-identity grant.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.corpus import iter_corpus_documents  # noqa: E402
from app.rag.search_client import INDEX_NAME, ensure_index_exists, upload_documents  # noqa: E402


def main() -> int:
    print(f"Ensuring index '{INDEX_NAME}' exists...")
    ensure_index_exists()

    documents = iter_corpus_documents()
    print(f"Uploading {len(documents)} documents...")
    results = upload_documents(documents)

    failed = [key for key, succeeded in results if not succeeded]
    for key, succeeded in results:
        print(f"  {'OK' if succeeded else 'FAILED'}: {key}")

    if failed:
        print(f"\n{len(failed)} document(s) failed to upload: {failed}")
        return 1

    print(f"\nAll {len(documents)} documents uploaded successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
