from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import AuditLog


router = APIRouter(
    prefix="/api/audit",
    tags=["Audit Logs"],
)


@router.get("/logs")
def get_audit_logs(
    limit: int = Query(
        50,
        ge=1,
        le=500,
    ),
    db: Session = Depends(get_db),
):
    logs = (
        db.query(AuditLog)
        .order_by(
            AuditLog.timestamp.desc()
        )
        .limit(limit)
        .all()
    )

    return {
        "count": len(logs),
        "logs": [
            {
                "id": log.id,
                "timestamp": log.timestamp,
                "action": log.action,
                "case_id": log.case_id,
                "registration_number": (
                    log.registration_number
                ),
                "previous_status": (
                    log.previous_status
                ),
                "new_status": log.new_status,
                "details": log.details,
            }
            for log in logs
        ],
    }