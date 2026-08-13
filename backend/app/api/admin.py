"""Admin API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.database import get_db
from app.db.models import User
from app.schemas.admin import AdminStatisticsResponse
from app.schemas.auth import MessageResponse
from app.schemas.ml import MLMetricsResponse
from app.services.admin_service import get_admin_statistics
from app.services.intent_service import get_intent_metrics

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/statistics", response_model=AdminStatisticsResponse)
def admin_statistics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> AdminStatisticsResponse:
    """Return basic platform statistics for the admin dashboard."""
    return AdminStatisticsResponse(**get_admin_statistics(db))


@router.get("/ping", response_model=MessageResponse)
def admin_ping(current_admin: User = Depends(get_current_admin)) -> MessageResponse:
    """Verify admin access. Full dashboard comes in Phase 8."""
    return MessageResponse(message=f"Admin access granted for {current_admin.email}")


@router.get("/ml-metrics", response_model=MLMetricsResponse)
def ml_metrics(_: User = Depends(get_current_admin)) -> MLMetricsResponse:
    """Return evaluation metrics from the trained intent classifier."""
    metrics = get_intent_metrics()
    if metrics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intent model metrics not found. Run: python -m app.ml.train_model",
        )
    return MLMetricsResponse(
        model_name=metrics["model_name"],
        training_examples=metrics["training_examples"],
        test_examples=metrics.get("test_examples"),
        accuracy=metrics["accuracy"],
        precision=metrics["precision"],
        recall=metrics["recall"],
        f1_score=metrics["f1_score"],
    )
