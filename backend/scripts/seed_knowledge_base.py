"""Seed sample college documents into the knowledge base for demos."""

import logging
from io import BytesIO

from fastapi import UploadFile
from sqlalchemy.orm import Session  # type: ignore

from app.core.config import BACKEND_ROOT
from app.db.database import SessionLocal, init_db
from app.db.models import Document
from app.services.document_service import upload_and_process
from app.services.retrieval_service import get_vector_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

SAMPLES_DIR = BACKEND_ROOT / "data" / "documents" / "samples"
SAMPLE_FILES = [
    "attendance_management.txt",
    "academics_management.txt",
    "library_management.txt",
    "readingroom.txt",
    "playground_facilities.txt",
    "department_directory.csv",
    "canteen_facilities.txt",
    "examination_evaluation.txt",
]


def seed_samples() -> None:
    init_db()
    db: Session = SessionLocal()
    try:
        existing = {document.filename for document in db.query(Document).all()}
        uploaded = 0

        for filename in SAMPLE_FILES:
            if filename in existing:
                logger.info("Skipping existing sample: %s", filename)
                continue

            file_path = SAMPLES_DIR / filename
            if not file_path.exists():
                logger.warning("Sample file not found: %s", file_path)
                continue

            content = file_path.read_bytes()
            upload = UploadFile(filename=filename, file=BytesIO(content))
            upload_and_process(db, upload, content, index_vectors=False)
            uploaded += 1
            logger.info("Processed sample document: %s", filename)

        count = get_vector_store().rebuild_from_database(db)
        print(f"Seed complete. Uploaded {uploaded} new documents. Vector index contains {count} chunks.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_samples()
