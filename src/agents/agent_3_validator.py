"""
Agent 3: Validator
컴파일된 룰(JSON) + 파싱된 IFC → 위반 사항(violations)

흐름:
  rules_compiled.json (Agent 2 결과)
  parsed_ifc_data    (Agent 1 결과)
       ↓ validate()
  violations.json
       [{"rule_id": "R3", "guid": "abc...", "violation_desc": "..."}, ...]

특징:
  - LLM 호출 X (Python only)
  - JSON 스키마로 모든 검사 처리
  - needs_llm=true 인 룰만 별도 처리 (Phase 2)

사용:
  python -m src.agents.agent_3_validator samples/SimpleWall.ifc
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional

from .agent_1_parser import parse_ifc, get_elements_by_type


# ============================================
# 1. check 타입별 평가 함수
# ============================================

def _evaluate_check(value: Any, check: dict) -> bool:
    """check 결과: True = 통과, False = 위반"""
    check_type = check.get("type")

    if check_type == "pset_value_valid":
        invalid = check.get("invalid_values") or [None, ""]
        return value not in invalid

    if check_type == "pset_value":
        return _apply_operator(value, check.get("operator"), check.get("value"))

    if check_type == "attribute":
        return _apply_operator(value, check.get("operator"), check.get("value"))

    if check_type == "geometry_dim":
        if value is None:
            return False  # 값 없으면 위반
        return _apply_operator(value, check.get("operator"), check.get("value"))

    if check_type in ("area_sum", "area_value"):
        # 면적 측정 불가(None 또는 0) = 위반 아님 (측정 자체가 안 됨)
        # 진짜 위반은 면적 측정 가능 + 기준 초과/미달일 때만
        if value is None or value == 0:
            return True  # 통과 처리 (측정 불가)
        return _apply_operator(value, check.get("operator"), check.get("value"))

    if check_type == "material_in":
        if value is None:
            return False
        candidates = check.get("value", [])
        match_mode = check.get("match_mode", "exact")
        if match_mode == "contains":
            return any(c.lower() in str(value).lower() for c in candidates)
        return value in candidates

    # 알려지지 않은 타입 = 위반으로 판정 (보수적)
    return False


def _apply_operator(value: Any, op: str, target: Any) -> bool:
    """operator 적용"""
    try:
        if op == "equals":
            return value == target
        if op == "not_equals":
            return value != target
        if op == "gte":
            return value is not None and value >= target
        if op == "lte":
            return value is not None and value <= target
        if op == "greater_than":
            return value is not None and value > target
        if op == "less_than":
            return value is not None and value < target
        if op == "is_in":
            return value in (target or [])
        if op == "contains":
            if value is None or target is None:
                return False
            # target이 list면 "둘 중 하나라도 포함"
            if isinstance(target, list):
                return any(
                    str(t).lower() in str(value).lower()
                    for t in target if t is not None
                )
            return str(target).lower() in str(value).lower()
        if op == "is_valid":
            return value not in (None, "", "_FIRE-RATING_", "TBD")
    except (TypeError, ValueError):
        return False
    return False


# ============================================
# 2. 값 추출
# ============================================

def _get_value_from_element(elem: dict, spec: dict) -> Any:
    """element에서 spec이 가리키는 값 추출"""
    check_type = spec.get("type")

    # Claude가 type 없이 pset/field만 줄 수도 있어서 자동 감지
    if check_type is None and spec.get("pset") and spec.get("field"):
        check_type = "pset_value"

    if check_type in ("pset_value", "pset_value_valid"):
        pset_name = spec.get("pset")
        field = spec.get("field")
        psets = elem.get("psets", {})
        return (psets.get(pset_name) or {}).get(field)

    if check_type == "attribute":
        return elem.get(spec.get("field", "").lower()) or elem.get(spec.get("field"))

    if check_type == "geometry_dim":
        field = spec.get("field")
        val = elem.get(field.lower()) or elem.get(field)
        if val is None:
            fb_pset = spec.get("fallback_pset")
            fb_field = spec.get("fallback_field")
            if fb_pset and fb_field:
                val = (elem.get("psets", {}).get(fb_pset) or {}).get(fb_field)
        return val

    if check_type == "area_value":
        pset = spec.get("pset")
        field = spec.get("field")
        val = (elem.get("psets", {}).get(pset) or {}).get(field)
        if val is None:
            fb_pset = spec.get("fallback_pset")
            fb_field = spec.get("fallback_field")
            if fb_pset and fb_field:
                val = (elem.get("psets", {}).get(fb_pset) or {}).get(fb_field)
        return val

    if check_type == "material_in":
        return elem.get("material")

    return None


# ============================================
# 3. filter 평가
# ============================================

def _passes_filter(elem: dict, filter_spec: Optional[dict]) -> bool:
    """filter 통과 여부 (filter 없으면 모두 통과)"""
    if filter_spec is None:
        return True

    # Claude가 다양한 키로 컴파일할 수 있어서 호환 처리
    # 형식 1: {"type": "or", "conditions": [...]}
    # 형식 2: {"condition": "OR", "rules": [...]}
    # 형식 3: {"or": [...]} 또는 {"and": [...]}  ← Claude 종종 이 형식
    # 형식 3 우선 (간결한 표현)
    if isinstance(filter_spec.get("or"), list):
        return any(_passes_filter(elem, c) for c in filter_spec["or"])
    if isinstance(filter_spec.get("and"), list):
        return all(_passes_filter(elem, c) for c in filter_spec["and"])

    # 형식 1, 2
    filter_type = (filter_spec.get("type") or
                   filter_spec.get("condition") or "").lower()
    sub_rules = (filter_spec.get("conditions") or
                 filter_spec.get("rules") or [])

    if filter_type == "or":
        return any(_passes_filter(elem, c) for c in sub_rules)
    if filter_type == "and":
        return all(_passes_filter(elem, c) for c in sub_rules)

    # 단일 조건 — type/pset 키 둘 다 지원
    value = _get_value_from_element(elem, filter_spec)
    return _apply_operator(value, filter_spec.get("operator"), filter_spec.get("value"))


# ============================================
# 4. area_sum (층 면적 합)
# ============================================

def _compute_storey_area(parsed: dict, storey: dict) -> float:
    """층 면적 합계 (슬래브 또는 공간 기반)"""
    storey_name = storey.get("name")

    # 1차: 슬래브 면적
    slabs = parsed.get("slabs", [])
    total = 0.0
    for s in slabs:
        if s.get("contained_in") != storey_name:
            continue
        psets = s.get("psets") or {}
        area = (psets.get("BaseQuantities") or {}).get("GrossArea")
        if isinstance(area, (int, float)):
            total += area

    if total > 0:
        return total

    # 2차: 공간 면적
    spaces = parsed.get("spaces", [])
    for sp in spaces:
        if sp.get("contained_in") != storey_name:
            continue
        psets = sp.get("psets") or {}
        area = (
            (psets.get("Qto_SpaceBaseQuantities") or {}).get("NetFloorArea")
            or (psets.get("BaseQuantities") or {}).get("GrossFloorArea")
        )
        if isinstance(area, (int, float)):
            total += area

    return total


# ============================================
# 5. 단일 룰 검증
# ============================================

def _validate_rule(parsed: dict, rule: dict) -> list[dict]:
    """단일 룰을 모든 대상 객체에 적용 → 위반 리스트"""
    target_type = rule["target"]
    elements = get_elements_by_type(parsed, target_type)
    violations = []

    for elem in elements:
        # filter
        if not _passes_filter(elem, rule.get("filter")):
            continue

        check = rule["check"]
        check_type = check.get("type")

        # area_sum (층 단위 특수 처리)
        if check_type == "area_sum":
            value = _compute_storey_area(parsed, elem)
        else:
            value = _get_value_from_element(elem, check)

        passes = _evaluate_check(value, check)
        if passes:
            continue

        violations.append({
            "rule_id": rule["id"],
            "rule_name": rule.get("name", ""),
            "severity": rule.get("severity", "Medium"),
            "guid": elem.get("guid"),
            "element_name": elem.get("name"),
            "element_type": target_type,
            "contained_in": elem.get("contained_in"),
            "current_value": _to_serializable(value),
            "expected": _describe_expected(check),
            "auto_fixable": rule.get("auto_fixable", False),
            "fix_spec": rule.get("fix"),
        })

    return violations


def _to_serializable(value: Any) -> Any:
    """JSON 직렬화 가능한 형태로 변환"""
    if isinstance(value, (str, int, float, bool, list, dict, type(None))):
        return value
    return str(value)


def _describe_expected(check: dict) -> str:
    """기대값 설명 (보고서용)"""
    check_type = check.get("type")
    op = check.get("operator", "")
    val = check.get("value", "")
    unit = check.get("unit", "")

    if check_type == "pset_value_valid":
        return f"유효한 값 (NOT in {check.get('invalid_values', [])})"
    if check_type in ("pset_value", "attribute"):
        return f"{op} {val}"
    if check_type in ("geometry_dim", "area_sum", "area_value"):
        return f"{op} {val}{unit}"
    if check_type == "material_in":
        return f"자재 ∈ {val}"
    return f"check: {check_type}"


# ============================================
# 6. 전체 검증
# ============================================

def validate(parsed_ifc: dict, compiled_rules: list[dict]) -> dict:
    """모든 룰 × 모든 객체 검증"""
    all_violations = []
    rule_summary = {}

    try:
        from tqdm import tqdm
        iterator = tqdm(compiled_rules, desc="🔎 검증", unit="rule")
    except ImportError:
        iterator = compiled_rules

    for rule in iterator:
        if rule.get("needs_llm", False):
            tqdm.write(f"⚠️  {rule['id']}: needs_llm=True → Phase 2에서 처리, 건너뜀") \
                if "tqdm" in str(type(iterator)) else \
                print(f"⚠️  {rule['id']}: needs_llm=True → Phase 2에서 처리, 건너뜀")
            continue

        violations = _validate_rule(parsed_ifc, rule)
        all_violations.extend(violations)
        rule_summary[rule["id"]] = {
            "name": rule.get("name"),
            "violation_count": len(violations),
            "severity": rule.get("severity"),
            "auto_fixable": rule.get("auto_fixable"),
        }

    return {
        "total_violations": len(all_violations),
        "rule_summary": rule_summary,
        "violations": all_violations,
    }


# ============================================
# 7. 메인 흐름
# ============================================

def run(
    ifc_path: str,
    rules_compiled_path: str = "samples/rules_compiled.json",
    output_path: str = "samples/violations.json",
) -> dict:
    """검증 파이프라인"""
    print("=" * 60)
    print(f"🔍 Agent 3: 검증 시작")
    print(f"   IFC: {ifc_path}")
    print(f"   Rules: {rules_compiled_path}")
    print("=" * 60)

    # 1. IFC 파싱 (Agent 1)
    print("\n📦 [Agent 1] IFC 파싱...")
    parsed = parse_ifc(ifc_path)
    print(f"   {parsed['total_entities']}개 엔티티, "
          f"벽 {len(parsed.get('walls', []))}개, "
          f"문 {len(parsed.get('doors', []))}개")

    # 2. 룰 로드 (Agent 2 결과)
    print("\n📜 컴파일된 룰 로드...")
    rules = json.loads(Path(rules_compiled_path).read_text(encoding="utf-8"))
    print(f"   {len(rules)}개 룰")
    for r in rules:
        print(f"   - {r['id']}: {r.get('name')} (severity={r.get('severity')})")

    # 3. 검증
    print("\n🔎 검증 중...")
    result = validate(parsed, rules)

    # 4. 저장
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    # 5. 요약 출력
    print("\n" + "=" * 60)
    print(f"📊 검증 결과")
    print("=" * 60)
    print(f"\n총 위반: {result['total_violations']}건")
    for rule_id, summary in result["rule_summary"].items():
        cnt = summary["violation_count"]
        emoji = "🔴" if summary["severity"] == "High" else "🟡" if summary["severity"] == "Medium" else "🟢"
        print(f"  {emoji} {rule_id} ({summary['name']}): {cnt}건")

    print(f"\n💾 저장: {output_path}")
    return result


if __name__ == "__main__":
    ifc_path = sys.argv[1] if len(sys.argv) > 1 else "samples/SimpleWall.ifc"
    run(ifc_path)
