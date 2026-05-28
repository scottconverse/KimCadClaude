import pytest
from pydantic import ValidationError

from kimcad.ir import (
    DesignPlan,
    Feature,
    FeatureType,
    design_plan_schema,
    first_clarification,
    parse_design_plan,
)


def test_minimal_plan_parses():
    plan = parse_design_plan(
        {
            "object_type": "plate",
            "summary": "50x50x10 plate with a centered 5mm hole",
            "dimensions": {"width": 50, "depth": 50, "height": 10},
            "bounding_box_mm": [50, 50, 10],
            "features": [{"type": "hole", "description": "centered hole", "diameter_mm": 5}],
        }
    )
    assert plan.object_type == "plate"
    assert plan.bounding_box_mm == [50, 50, 10]
    assert plan.features[0].type is FeatureType.hole
    assert plan.features[0].diameter_mm == 5


def test_bbox_must_be_xyz():
    with pytest.raises(ValidationError):
        DesignPlan(object_type="x", summary="x", bounding_box_mm=[10, 10])


def test_bbox_must_be_positive():
    with pytest.raises(ValidationError):
        DesignPlan(object_type="x", summary="x", bounding_box_mm=[10, 0, 10])


def test_feature_position_must_be_xyz():
    with pytest.raises(ValidationError):
        Feature(type=FeatureType.hole, description="h", position=[1, 2])


def test_clarification_prefers_open_question():
    plan = DesignPlan(
        object_type="bracket",
        summary="L-bracket",
        open_questions=["What screw size — M3, M4, or M5?"],
    )
    assert first_clarification(plan) == "What screw size — M3, M4, or M5?"


def test_clarification_asks_for_size_when_no_dims():
    plan = DesignPlan(object_type="widget", summary="a widget")
    q = first_clarification(plan)
    assert q is not None and "size" in q.lower()


def test_clarification_none_when_sized():
    plan = DesignPlan(
        object_type="plate",
        summary="sized",
        bounding_box_mm=[50, 50, 10],
    )
    assert first_clarification(plan) is None


def test_schema_is_generated():
    schema = design_plan_schema()
    assert schema["type"] == "object"
    assert "object_type" in schema["properties"]
