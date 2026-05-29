import pytest
from pydantic import ValidationError

from kimcad.ir import (
    DesignPlan,
    Feature,
    FeatureType,
    design_plan_schema,
    first_clarification,
    normalize_plan_dict,
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


def test_clarification_asks_open_question_when_unsized():
    # No envelope and no dimensions: the model's own question is surfaced.
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


def test_open_questions_do_not_block_a_sized_plan():
    # A committed envelope makes the part buildable; open_questions are refinements.
    plan = DesignPlan(
        object_type="bracket",
        summary="sized bracket",
        bounding_box_mm=[40, 40, 4],
        open_questions=["What screw size — M3, M4, or M5?"],
    )
    assert first_clarification(plan) is None


def test_open_questions_do_not_block_when_only_dimensions():
    plan = DesignPlan(
        object_type="bracket",
        summary="sized via dimensions",
        dimensions={"width": 40, "height": 40, "thick": 4},
        open_questions=["What screw size?"],
    )
    assert first_clarification(plan) is None


def test_normalize_coerces_unknown_feature_type():
    # The model labels the hook arm "arm", which is not in the enum.
    data = {
        "object_type": "hook",
        "summary": "wall hook",
        "bounding_box_mm": [40, 25, 65],
        "features": [{"type": "arm", "description": "the hook arm"}],
    }
    plan = parse_design_plan(normalize_plan_dict(data))
    assert plan.features[0].type is FeatureType.other
    assert "arm" in (plan.features[0].notes or "")


def test_normalize_drops_two_element_position():
    data = {
        "object_type": "clip",
        "summary": "cable clip",
        "bounding_box_mm": [25, 20, 18],
        "features": [{"type": "hole", "description": "screw hole", "position": [12.5, 12.5]}],
    }
    plan = parse_design_plan(normalize_plan_dict(data))
    assert plan.features[0].position is None


def test_normalize_drops_degenerate_bbox():
    data = {
        "object_type": "hook",
        "summary": "pegboard hook",
        "bounding_box_mm": [0, 0, 60],
        "features": [],
    }
    plan = parse_design_plan(normalize_plan_dict(data))
    assert plan.bounding_box_mm is None


def test_normalize_keeps_valid_data_unchanged():
    data = {
        "object_type": "plate",
        "summary": "plate",
        "bounding_box_mm": [50, 50, 10],
        "features": [{"type": "hole", "description": "center", "position": [25, 25, 0]}],
    }
    plan = parse_design_plan(normalize_plan_dict(data))
    assert plan.bounding_box_mm == [50, 50, 10]
    assert plan.features[0].type is FeatureType.hole
    assert plan.features[0].position == [25, 25, 0]


def test_normalize_does_not_mutate_input():
    data = {
        "object_type": "x",
        "summary": "x",
        "features": [{"type": "arm", "description": "a"}],
    }
    normalize_plan_dict(data)
    assert data["features"][0]["type"] == "arm"  # original dict untouched


def test_schema_is_generated():
    schema = design_plan_schema()
    assert schema["type"] == "object"
    assert "object_type" in schema["properties"]
