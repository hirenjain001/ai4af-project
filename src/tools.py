"""Least-privilege draft action tools for the assortment-planning agent.

Purpose: expose planner-visible drafts without permitting irreversible actions.
Workflow step: Step 6 — controlled recommendation and approval.
Inputs: style IDs and draft quantities/details.
Outputs: serializable draft payloads for the UI and audit log.
Controls/rights: every function is guarded by config.AGENT_RIGHTS.
"""

from __future__ import annotations

from typing import Any

from src.controls import guarded


@guarded("draft_chase_po")
def draft_chase_po(style_id: str, quantity: int) -> dict[str, Any]:
    """Create a vendor-order draft for planner approval."""

    return {"tool": "draft_chase_po", "style_id": style_id, "quantity": quantity, "status": "draft"}


@guarded("draft_order_cut")
def draft_order_cut(style_id: str, percentage: int) -> dict[str, Any]:
    """Create a reorder-cut draft for planner approval."""

    return {"tool": "draft_order_cut", "style_id": style_id, "percentage": percentage, "status": "draft"}


@guarded("draft_transfer")
def draft_transfer(style_id: str, quantity: int, region: str) -> dict[str, Any]:
    """Create a store-transfer draft for planner approval."""

    return {
        "tool": "draft_transfer",
        "style_id": style_id,
        "quantity": quantity,
        "region": region,
        "status": "draft",
    }


@guarded("draft_markdown")
def draft_markdown(style_id: str, discount_percent: int) -> dict[str, Any]:
    """Create a markdown draft without scheduling it."""

    return {
        "tool": "draft_markdown",
        "style_id": style_id,
        "discount_percent": discount_percent,
        "status": "draft",
    }


@guarded("draft_design_ticket")
def draft_design_ticket(style_id: str, issue: str) -> dict[str, Any]:
    """Create a product-quality design-ticket draft."""

    return {"tool": "draft_design_ticket", "style_id": style_id, "issue": issue, "status": "draft"}
