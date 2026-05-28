"""Design-Plan intermediate representation.

The LLM emits a Design Plan (JSON) *before* any OpenSCAD is written. This gives a
place to validate intent before generating geometry, drives the one-question
clarification behavior, and makes conversational refinement auditable. OpenSCAD is
generated from the plan, not straight from prose. (Spec §6.2.)

All linear dimensions are millimeters.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class FeatureType(str, Enum):
    hole = "hole"
    slot = "slot"
    cutout = "cutout"
    fillet = "fillet"
    chamfer = "chamfer"
    mount = "mount"
    boss = "boss"
    rib = "rib"
    thread = "thread"
    text = "text"
    other = "other"


class Feature(BaseModel):
    """A discrete geometric feature on the part. Sizing fields are optional; the
    model fills in whatever it can commit to."""

    type: FeatureType
    description: str
    diameter_mm: float | None = None
    width_mm: float | None = None
    depth_mm: float | None = None
    count: int | None = None
    spacing_mm: float | None = None
    # [x, y, z] reference point, when the user pointed at a location (Phase 2
    # click-to-point) or the model can commit to one.
    position: list[float] | None = None
    notes: str | None = None

    @field_validator("position")
    @classmethod
    def _position_is_xyz(cls, v: list[float] | None) -> list[float] | None:
        if v is not None and len(v) != 3:
            raise ValueError("position must be [x, y, z]")
        return v


class Tolerances(BaseModel):
    """Fit/clearance intent. Concrete clearance defaults come from material +
    printer config; this records what the design *needs*."""

    clearance_mm: float = 0.2
    notes: str | None = None


class DesignPlan(BaseModel):
    """Structured intent, validated before codegen."""

    object_type: str
    summary: str
    # Named dimensions in mm, e.g. {"width": 50, "height": 70, "wall": 3}.
    dimensions: dict[str, float] = Field(default_factory=dict)
    # The model's best estimate of the overall envelope [x, y, z] in mm. This is
    # the primary target for the Printability Gate's dimensional assertion (§6.6).
    bounding_box_mm: list[float] | None = None
    features: list[Feature] = Field(default_factory=list)
    tolerances: Tolerances = Field(default_factory=Tolerances)
    printer: str | None = None
    material: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    @field_validator("bounding_box_mm")
    @classmethod
    def _bbox_is_positive_xyz(cls, v: list[float] | None) -> list[float] | None:
        if v is None:
            return v
        if len(v) != 3:
            raise ValueError("bounding_box_mm must be [x, y, z]")
        if any(d <= 0 for d in v):
            raise ValueError("bounding_box_mm components must be positive")
        return v


def parse_design_plan(data: dict) -> DesignPlan:
    """Validate raw LLM JSON into a DesignPlan (raises pydantic ValidationError)."""
    return DesignPlan.model_validate(data)


def design_plan_schema() -> dict:
    """JSON schema for structured-output / function-calling mode (§6.1)."""
    return DesignPlan.model_json_schema()


def first_clarification(plan: DesignPlan) -> str | None:
    """Minimal Phase-1 clarification policy (§5.2): ask exactly one question.

    The model surfaces the critical missing dimension in ``open_questions``; we ask
    the first one. A short clarification beats a confident wrong guess. If the
    model committed to no envelope and no dimensions at all, we ask a generic
    sizing question rather than guessing a size.
    """
    if plan.open_questions:
        return plan.open_questions[0]
    if plan.bounding_box_mm is None and not plan.dimensions:
        return (
            f"What overall size should the {plan.object_type} be? "
            "Give me the key dimensions in mm (e.g. width × height × depth)."
        )
    return None
