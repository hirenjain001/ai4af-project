"""Streamlit planner interface for the assortment-planning prototype.

Purpose: make the agent's evidence, controls, and planner decision visible.
Workflow step: Steps 2 and 6 — style review and controlled recommendation.
Inputs: generated style files, RAG stores, and planner approval/rejection.
Outputs: charts, citations, recommendation status, and audit events.
Controls/rights: UI actions remain drafts; the kill switch routes work to manual review.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

import config
from src.agent import AgentResult, run
from src.audit import AuditLog
from src.build_dataset import build_dataset
from src.ingest import ingest
from src.models import AuditEvent, StyleWeek
from src.retrieve import retrieve

DATA_DIR = Path("data")
STORE_DIR = DATA_DIR / "rag"
AUDIT_PATH = DATA_DIR / "audit.jsonl"


def ensure_demo_data() -> None:
    """Create local demo artifacts when the app is launched from a clean clone."""

    if not (DATA_DIR / "splits.json").exists():
        build_dataset(DATA_DIR)
    if not (STORE_DIR / "playbook.jsonl").exists():
        ingest(DATA_DIR, Path("kb"), STORE_DIR)


def load_styles() -> dict[str, StyleWeek]:
    """Load generated style-week cases for the picker."""

    return {
        path.stem: StyleWeek.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((DATA_DIR / "styles").glob("S*.json"))
    }


def _record_planner_decision(style_id: str, decision: str, result: AgentResult) -> None:
    """Append a planner approval or rejection to the audit trail."""

    AuditLog(AUDIT_PATH).append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            style_id=style_id,
            node="planner_review",
            action=decision,
            sources=[citation.source for citation in result.recommendation.citations]
            if result.recommendation
            else [],
            output=f"Planner selected {decision}.",
        )
    )


def _show_audit() -> None:
    """Render the append-only audit log when it exists."""

    if not AUDIT_PATH.exists():
        st.info("No planner decisions recorded yet.")
        return
    rows = [
        json.loads(line)
        for line in AUDIT_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


def main() -> None:
    """Render the complete planner application."""

    st.set_page_config(page_title="Assortment Planning Agent", layout="wide")
    ensure_demo_data()
    styles = load_styles()
    st.title("Assortment Planning Agent")
    st.caption("Workflow steps 2 and 6 · offline demo mode by default")

    with st.sidebar:
        st.header("Controls")
        kill_switch = st.toggle("KILL_SWITCH", value=config.KILL_SWITCH)
        phase = st.selectbox(
            "Agent phase",
            options=list(config.Phase),
            format_func=lambda value: value.name.replace("_", " ").title(),
            index=list(config.Phase).index(config.PHASE),
        )
        st.write(f"Runtime phase: **{phase.name}**")
        st.write(f"Data freshness limit: **{config.MAX_DATA_AGE_DAYS} days**")
        st.write(f"Confidence threshold: **{config.CONFIDENCE_THRESHOLD:.0%}**")

    style_ids = list(styles)
    demo_cases = {
        "Fading franchise": style_ids[0],
        "Fad vs trend": style_ids[len(style_ids) // 2],
        "Real winner": style_ids[min(30, len(style_ids) - 1)],
    }
    selected_case = st.selectbox("Demo case", options=["Custom"] + list(demo_cases))
    default_style = demo_cases.get(selected_case, style_ids[0])
    style_id = st.selectbox(
        "Select a style · [WORKFLOW STEP 2]",
        options=style_ids,
        index=style_ids.index(default_style),
    )
    style = styles[style_id]
    st.subheader(f"{style.style_id} · {style.category}")
    st.write(
        f"Region: **{style.region}** · Core franchise: **{style.is_core_franchise}** · "
        f"Extended sizes: **{style.extended_size_range}**"
    )

    left, right = st.columns(2)
    with left:
        st.markdown("### Internal metrics · [WORKFLOW STEP 2]")
        chart = pd.DataFrame({"week": range(1, 5), "sales": style.sales_last_4w}).set_index("week")
        st.line_chart(chart)
        st.metric("Weeks of supply", style.weeks_of_supply)
        st.metric("Return rate", f"{style.return_rate:.0%}")
    with right:
        st.markdown("### Outside signals · [RAG]")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "source": signal.source_type,
                        "date": signal.date,
                        "direction": signal.direction.value,
                        "text": signal.text,
                    }
                    for signal in style.signals
                ]
            ),
            use_container_width=True,
        )

    if kill_switch:
        st.error("KILL_SWITCH is ON: this style is routed to the manual planner queue.")
    result = run(style, STORE_DIR, kill_switch_override=kill_switch)
    st.markdown("### Recommendation · [WORKFLOW STEP 6]")
    st.info(f"Route: **{result.route}**")
    if result.recommendation:
        st.write(f"**Action:** `{result.recommendation.action.value}`")
        st.write(f"**Confidence:** `{result.recommendation.confidence:.0%}`")
        st.write(result.recommendation.rationale)
        st.markdown("#### Citations · [RAG]")
        st.dataframe(
            pd.DataFrame(
                [
                    {"source": citation.source, "date": citation.date}
                    for citation in result.recommendation.citations
                ]
            ),
            use_container_width=True,
        )
        similar = retrieve(
            "past decision outcome",
            "past_decisions",
            STORE_DIR,
            top_k=3,
        )
        st.markdown("#### Similar past decisions · [RAG]")
        st.dataframe(
            pd.DataFrame(
                [
                    {"style": chunk.style_id, "source": chunk.source, "date": chunk.date, "evidence": chunk.text}
                    for chunk in similar
                ]
            ),
            use_container_width=True,
        )
        st.markdown("#### Action guard · [RIGHTS]")
        allowed = {
            action: permitted
            for action, permitted in config.AGENT_RIGHTS.items()
            if action.startswith("draft_") or action in {"submit_vendor_po", "schedule_markdown"}
        }
        st.dataframe(
            pd.DataFrame([{"action": action, "allowed": permitted} for action, permitted in allowed.items()]),
            use_container_width=True,
        )
        st.caption(
            "[CONTROL-CUSTOMER] Recommendations are drafts for planner approval. "
            "The agent cannot contact guests or change customer-facing prices directly."
        )

    approve, reject = st.columns(2)
    with approve:
        if st.button("Planner approve", type="primary", disabled=kill_switch):
            _record_planner_decision(style_id, "approve", result)
            st.success("Draft approved and recorded; no irreversible tool was executed.")
    with reject:
        if st.button("Planner reject", disabled=kill_switch):
            _record_planner_decision(style_id, "reject", result)
            st.warning("Recommendation rejected and recorded.")

    st.markdown("### Audit log · [CONTROL-INTERNAL]")
    _show_audit()


if __name__ == "__main__":
    main()
