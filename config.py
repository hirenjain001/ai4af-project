"""Central configuration for the assortment-planning agent.

Purpose: keep thresholds, runtime phase, kill switch, and rights in one auditable module.
Workflow step: applies to steps 2 and 6.
Inputs: environment variables for safe runtime overrides.
Outputs: typed configuration constants consumed by controls and agent nodes.
Controls/rights: defines the default least-privilege action table.
"""

from __future__ import annotations

import os
from enum import IntEnum

from dotenv import load_dotenv

load_dotenv()


class Phase(IntEnum):
    """Deployment phase controlling which actions can be automated."""

    DEVELOPMENT = 1
    PILOT = 2
    CONTROLLED_AUTOMATION = 3


MAX_DATA_AGE_DAYS = int(os.getenv("MAX_DATA_AGE_DAYS", "7"))
CUTOFF_ESCALATE_DAYS = int(os.getenv("CUTOFF_ESCALATE_DAYS", "5"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.8"))
PHASE = Phase(int(os.getenv("AGENT_PHASE", str(Phase.DEVELOPMENT))))
KILL_SWITCH = os.getenv("KILL_SWITCH", "false").strip().lower() in {"1", "true", "yes", "on"}

AGENT_RIGHTS: dict[str, bool] = {
    "read_sales": True,
    "read_rfid": True,
    "read_returns": True,
    "read_open_orders": True,
    "read_signals": True,
    "read_kb": True,
    "draft_chase_po": True,
    "draft_order_cut": True,
    "draft_transfer": True,
    "draft_markdown": True,
    "draft_design_ticket": True,
    "execute_store_transfer": False,
    "schedule_markdown": False,
    "submit_vendor_po": False,
    "cancel_vendor_po": False,
    "retire_style": False,
    "change_full_price": False,
    "exceed_open_to_buy": False,
    "contact_vendor": False,
    "contact_guest": False,
}

FRANCHISE_ACTIONS = {"chase", "retire", "change_full_price"}
AUTO_ACTIONS: dict[Phase, set[str]] = {
    Phase.DEVELOPMENT: set(),
    Phase.PILOT: set(),
    Phase.CONTROLLED_AUTOMATION: {"draft_order_cut", "draft_transfer", "schedule_markdown"},
}