"""WeasyPrint wrapper: dashboard Pydantic model -> PDF bytes."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from backend.app.api.schemas import DashboardResponse


TEMPLATE_DIR = Path(__file__).parent
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _fmt_money(v):
    if v is None:
        return "—"
    return f"${v:,.0f}"


def _fmt_dt(v):
    return v.strftime("%b %d, %Y at %H:%M UTC") if v else "—"


_env.filters["money"] = _fmt_money
_env.filters["dt"] = _fmt_dt


def render_dashboard_pdf(dashboard: DashboardResponse) -> bytes:
    template = _env.get_template("template.html")
    html_str = template.render(d=dashboard)
    return HTML(string=html_str).write_pdf()
