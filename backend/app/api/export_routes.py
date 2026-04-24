"""GET /export/pdf — render the dashboard as a downloadable PDF."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.api.dashboard_routes import get_dashboard
from backend.app.auth import get_current_user
from backend.app.database import get_db
from backend.app.models import User
from backend.app.pdf.render import render_dashboard_pdf


router = APIRouter(prefix="/export", tags=["export"])


@router.get("/pdf")
def export_pdf(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dashboard = get_dashboard(db=db, _=user)
    pdf_bytes = render_dashboard_pdf(dashboard)
    filename = f"fitzrovia-comp-report-{dashboard.generated_at.strftime('%Y%m%d-%H%M')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
