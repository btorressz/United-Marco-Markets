from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_report(kind: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = context or {}
    title = {"daily_brief": "Daily Macro Risk Brief", "tariff_risk": "Tariff Risk Report", "portfolio_risk": "Portfolio Exposure Report", "agent_signals": "Agent Signal Report"}.get(kind, "Risk Report")
    sections = [
        {"title": "Executive Summary", "items": ctx.get("summary", ["System is operating in fail-open proposal-only mode", "No autonomous live trading"])} ,
        {"title": "Key Risks", "items": ctx.get("risks", ["Tariff/GDELT data may be degraded", "Liquidity and funding should be monitored"])},
        {"title": "Recommended Actions", "items": ctx.get("actions", ["Review allocation preview", "Use paper-mode hedges and conditional orders only"])},
    ]
    return {"report_type": kind, "title": title, "sections": sections, "export_formats": ["json", "copy_text"], "degraded": bool(ctx.get("degraded", False)), "generated_at": datetime.now(timezone.utc).isoformat()}
