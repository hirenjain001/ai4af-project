"""Shared typed models for the assortment-planning prototype.

Purpose: define the data passed between dataset, RAG, control, and agent nodes.
Workflow step: supports steps 2 and 6 without making business decisions.
Inputs: validated Python values from local data sources and agent nodes.
Outputs: stable models for style-week cases, signals, citations, and decisions.
Controls/rights: models carry the fields required by freshness, grounding, and audit controls.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Action(StrEnum):
    """Actions the planner may propose."""

    CHASE = "chase"
    HOLD = "hold"
    MOVE = "move"
    FIX = "fix"
    RETIRE = "retire"
    CUT_REORDER = "cut_reorder"
    MARKDOWN = "markdown"


class SignalDirection(StrEnum):
    """Direction of a signal relative to demand or risk."""

    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class Citation(BaseModel):
    """A dated source supporting a retrieved or observed signal."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1)
    date: date
    section: str | None = None


class RetrievedChunk(BaseModel):
    """A retrieved RAG chunk with provenance required for grounding."""

    text: str = Field(min_length=1)
    source: str = Field(min_length=1)
    date: date
    store: str = Field(min_length=1)
    style_id: str | None = None
    score: float = Field(default=0.0, ge=0.0)


class Signal(BaseModel):
    """A normalized signal used during style reasoning."""

    model_config = ConfigDict(validate_assignment=True)

    source_type: str = Field(min_length=1)
    text: str = Field(min_length=1)
    direction: SignalDirection = SignalDirection.UNKNOWN
    strength: float = Field(default=0.0, ge=0.0, le=1.0)
    date: date
    citation: Citation | None = None


class StyleWeek(BaseModel):
    """Internal and external evidence for one style in one week."""

    model_config = ConfigDict(validate_assignment=True)

    style_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    week: str = Field(pattern=r"^\d{4}-W\d{2}$")
    region: str = Field(min_length=1)
    sales_last_4w: list[int] = Field(min_length=4, max_length=4)
    weeks_of_supply: float = Field(ge=0.0)
    return_rate: float = Field(ge=0.0, le=1.0)
    open_order_units: int = Field(ge=0)
    vendor_cutoff_date: date
    data_as_of: date
    signals: list[Signal] = Field(default_factory=list)
    is_core_franchise: bool = False
    extended_size_range: bool = False
    label: Action | None = None


class Recommendation(BaseModel):
    """A proposed action and its evidence for planner review."""

    action: Action
    quantity: int | None = Field(default=None, ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)


class AuditEvent(BaseModel):
    """Append-only event shape used by the audit log."""

    timestamp: str
    style_id: str
    node: str
    action: str
    sources: list[str] = Field(default_factory=list)
    output: str
