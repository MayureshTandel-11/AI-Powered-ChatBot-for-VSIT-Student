"""Admin dashboard statistics."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, Document, User

logger = logging.getLogger(__name__)


def get_admin_statistics(db: Session) -> dict[str, int]:
    total_students = db.query(User).filter(User.role == "student").count()
    total_documents = db.query(Document).count()
    total_questions = db.query(ChatMessage).filter(ChatMessage.role == "user").count()

    active_since = datetime.now(timezone.utc) - timedelta(days=30)
    active_users = (
        db.query(func.count(distinct(ChatMessage.user_id)))
        .filter(ChatMessage.created_at >= active_since)
        .scalar()
        or 0
    )

    stats = {
        "total_students": total_students,
        "total_documents": total_documents,
        "total_questions": total_questions,
        "active_users": int(active_users),
    }
    logger.info("Admin statistics requested: %s", stats)
    return stats
