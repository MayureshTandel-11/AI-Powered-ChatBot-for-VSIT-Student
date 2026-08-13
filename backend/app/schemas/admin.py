"""Admin dashboard statistics schemas."""

from pydantic import BaseModel


class AdminStatisticsResponse(BaseModel):
    total_students: int
    total_documents: int
    total_questions: int
    active_users: int
