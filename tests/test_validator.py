"""Agent 3 (검증) 단위 테스트.

LESSONS.md의 버그들을 회귀 테스트로 박제한다:
  - L1/L9: filter OR/AND 3가지 형식 호환
  - L2:    pset_value_valid invalid=None 처리
  - L3:    면적 0/None = '측정 불가' = 위반 아님
  - L10:   contains operator의 value가 list일 때
"""

from src.agents.agent_3_validator import (
    _apply_operator,
    _evaluate_check,
    _passes_filter,
    validate,
)
from src.agents.agent_2_interpreter import MOCK_COMPILED_RULES


# ── operator ───────────────────────────────────────────────
def test_operator_basic():
    assert _apply_operator(500, "gte", 200) is True
    assert _apply_operator(100, "gte", 200) is False
    assert _apply_operator(100, "lte", 200) is True
    assert _apply_operator("2HR", "equals", "2HR") is True
    assert _apply_operator("2HR", "not_equals", "1HR") is True


def test_operator_gte_none_is_false():
    # 값 없음 → 비교 불가 → False (크래시 X)
    assert _apply_operator(None, "gte", 200) is False
    assert _apply_operator(None, "lte", 200) is False


def test_operator_contains_string():
    assert _apply_operator("비상계단", "contains", "비상") is True
    assert _apply_operator("일반계단", "contains", "비상") is False


def test_operator_contains_value_is_list_L10():
    # L10: value가 list면 '하나라도 포함'
    assert _apply_operator("Emergency Stair", "contains", ["비상", "Emergency"]) is True
    assert _apply_operator("일반", "contains", ["비상", "Emergency"]) is False


def test_operator_is_valid():
    assert _apply_operator("2HR", "is_valid", None) is True
    assert _apply_operator("_FIRE-RATING_", "is_valid", None) is False
    assert _apply_operator(None, "is_valid", None) is False


# ── check 평가 ─────────────────────────────────────────────
def test_check_pset_value_valid_L2():
    # L2: invalid_values 누락/None이어도 크래시 없이 기본값 사용
    check = {"type": "pset_value_valid", "invalid_values": None}
    assert _evaluate_check("2HR", check) is True       # 유효 → 통과
    assert _evaluate_check(None, check) is False        # None → 위반
    assert _evaluate_check("", check) is False          # 빈값 → 위반


def test_check_area_sum_zero_is_pass_L3():
    # L3: 면적 0 또는 None = 측정 불가 = 위반 아님(통과)
    check = {"type": "area_sum", "operator": "lte", "value": 1500.0}
    assert _evaluate_check(0, check) is True
    assert _evaluate_check(None, check) is True
    assert _evaluate_check(2000, check) is False        # 측정됨 + 초과 → 위반


def test_check_geometry_dim_none_is_violation():
    check = {"type": "geometry_dim", "operator": "gte", "value": 1200}
    assert _evaluate_check(None, check) is False        # 값 없음 → 위반
    assert _evaluate_check(1500, check) is True


# ── filter 3형식 호환 (L1/L9) ──────────────────────────────
def _elem_external():
    return {"psets": {"Pset_WallCommon": {"IsExternal": True}}}


def test_filter_format_compact_or_L9():
    # 형식: {"or": [...]}
    f = {"or": [
        {"type": "pset_value", "pset": "Pset_WallCommon",
         "field": "IsExternal", "operator": "equals", "value": True},
    ]}
    assert _passes_filter(_elem_external(), f) is True


def test_filter_format_type_conditions_L1():
    # 형식: {"type": "or", "conditions": [...]}
    f = {"type": "or", "conditions": [
        {"type": "pset_value", "pset": "Pset_WallCommon",
         "field": "IsExternal", "operator": "equals", "value": True},
    ]}
    assert _passes_filter(_elem_external(), f) is True


def test_filter_format_condition_rules():
    # 형식: {"condition": "OR", "rules": [...]}
    f = {"condition": "OR", "rules": [
        {"type": "pset_value", "pset": "Pset_WallCommon",
         "field": "IsExternal", "operator": "equals", "value": True},
    ]}
    assert _passes_filter(_elem_external(), f) is True


def test_filter_none_passes_all():
    assert _passes_filter({}, None) is True


# ── validate 통합 (R3 화재등급 누락) ────────────────────────
def test_validate_firerating_violation_end_to_end():
    """외벽 FireRating 누락 → R3 위반 1건, 정상 벽은 통과."""
    parsed = {
        "walls": [
            {"guid": "bad", "name": "외벽-누락",
             "psets": {"Pset_WallCommon": {"IsExternal": True,
                                           "FireRating": "_FIRE-RATING_"}}},
            {"guid": "ok", "name": "외벽-정상",
             "psets": {"Pset_WallCommon": {"IsExternal": True,
                                           "FireRating": "2HR"}}},
            {"guid": "internal", "name": "내벽",
             "psets": {"Pset_WallCommon": {"IsExternal": False}}},
        ]
    }
    result = validate(parsed, [MOCK_COMPILED_RULES["R3"]])
    assert result["total_violations"] == 1
    assert result["violations"][0]["guid"] == "bad"
    assert result["violations"][0]["rule_id"] == "R3"


def test_validate_no_rules_no_violations():
    assert validate({"walls": []}, [])["total_violations"] == 0
