"""Agent 4 (자동 수정) — 화이트리스트 안전 정책 테스트.

자동 수정은 '화이트리스트 fix_type' + 'auto_fixable=True' 둘 다일 때만.
(안전 규칙: 새 요소 추가/삭제 등 위험 작업은 절대 자동 X)
"""

from src.agents.agent_4_autofix import is_auto_fixable, AUTO_FIX_WHITELIST


def _vio(auto_fixable=True, fix_type="pset_set_value"):
    v = {"auto_fixable": auto_fixable}
    if fix_type is not None:
        v["fix_spec"] = {"type": fix_type}
    return v


def test_whitelisted_types_are_fixable():
    for t in ["pset_set_value", "set_pset_value", "set_attribute",
              "set_material", "set_geometry"]:
        assert is_auto_fixable(_vio(fix_type=t)) is True


def test_dangerous_types_not_fixable():
    # 인간 판단 필요 / 제안만 → 자동 수정 금지
    assert is_auto_fixable(_vio(fix_type="needs_human_action")) is False
    assert is_auto_fixable(_vio(fix_type="suggestion_only")) is False


def test_auto_fixable_flag_false_blocks():
    # 화이트리스트 타입이어도 auto_fixable=False면 막음
    assert is_auto_fixable(_vio(auto_fixable=False, fix_type="pset_set_value")) is False


def test_missing_fix_spec_blocks():
    assert is_auto_fixable(_vio(fix_type=None)) is False


def test_whitelist_has_no_dangerous_types():
    # 화이트리스트에 위험 타입이 새어들어가지 않았는지
    assert "needs_human_action" not in AUTO_FIX_WHITELIST
    assert "suggestion_only" not in AUTO_FIX_WHITELIST
