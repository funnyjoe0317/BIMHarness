"""형상 탐색 _find_extruded_solids — Clipping(잘린 벽) 재귀 처리 테스트.

실무 IFC 벽의 두 표현:
  - SweptSolid:  IfcExtrudedAreaSolid (직접 노출)
  - Clipping:    IfcBooleanClippingResult → FirstOperand 안에 솔리드 숨음
경사지붕 등에 잘린 벽도 두께/높이 수정하려면 재귀로 안쪽을 찾아야 한다.
"""

from src.agents.agent_ai_react import _find_extruded_solids


class FakeItem:
    """ifcopenshell 엔티티 흉내 (.is_a + .FirstOperand)."""
    def __init__(self, type_name, first_operand=None):
        self._type = type_name
        self.FirstOperand = first_operand

    def is_a(self, name):
        return self._type == name


def test_direct_extruded_solid():
    item = FakeItem("IfcExtrudedAreaSolid")
    assert _find_extruded_solids(item) == [item]


def test_clipping_unwraps_to_inner_solid():
    inner = FakeItem("IfcExtrudedAreaSolid")
    clip = FakeItem("IfcBooleanClippingResult", first_operand=inner)
    assert _find_extruded_solids(clip) == [inner]


def test_generic_boolean_result_unwraps():
    inner = FakeItem("IfcExtrudedAreaSolid")
    bool_res = FakeItem("IfcBooleanResult", first_operand=inner)
    assert _find_extruded_solids(bool_res) == [inner]


def test_none_returns_empty():
    assert _find_extruded_solids(None) == []


def test_unrelated_type_returns_empty():
    assert _find_extruded_solids(FakeItem("IfcFacetedBrep")) == []
