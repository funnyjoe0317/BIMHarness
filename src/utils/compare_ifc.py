"""
IFC 수정 전/후 비교 도구
원본 .ifc와 수정된 .ifc를 파싱해서 무엇이 바뀌었는지 보여줌

사용:
  python -m src.utils.compare_ifc samples/SimpleWall.ifc samples/SimpleWall_fixed.ifc
"""

import json
import sys
from pathlib import Path

from src.agents.agent_1_parser import parse_ifc


def _flatten_psets(elem: dict) -> dict:
    """psets dict를 평탄화: {pset.field: value}"""
    flat = {}
    for pset_name, props in (elem.get("psets") or {}).items():
        if not isinstance(props, dict):
            continue
        for field, value in props.items():
            if field == "id":
                continue
            flat[f"{pset_name}.{field}"] = value
    return flat


def _compare_element(orig: dict, fixed: dict) -> list[dict]:
    """element 1개 비교 → 변경된 필드 리스트"""
    changes = []

    # 기본 속성 비교
    for key in ["name", "description", "predefined_type", "material"]:
        v1, v2 = orig.get(key), fixed.get(key)
        if v1 != v2:
            changes.append({
                "field": key,
                "before": v1,
                "after": v2,
            })

    # Pset 비교
    psets1 = _flatten_psets(orig)
    psets2 = _flatten_psets(fixed)

    all_keys = set(psets1.keys()) | set(psets2.keys())
    for key in sorted(all_keys):
        v1, v2 = psets1.get(key), psets2.get(key)
        if v1 != v2:
            changes.append({
                "field": key,
                "before": v1,
                "after": v2,
            })

    return changes


def compare(orig_path: str, fixed_path: str) -> dict:
    """두 IFC 파일 비교"""
    print(f"📂 원본: {orig_path}")
    print(f"📂 수정: {fixed_path}")
    print("=" * 60)

    print("\n파싱 중...")
    orig = parse_ifc(orig_path)
    fixed = parse_ifc(fixed_path)

    # 카운트 차이
    print("\n📊 요소 카운트 비교")
    print("-" * 60)
    all_types = set(orig["counts"].keys()) | set(fixed["counts"].keys())
    for t in sorted(all_types):
        c1 = orig["counts"].get(t, 0)
        c2 = fixed["counts"].get(t, 0)
        diff = c2 - c1
        diff_str = f"({diff:+d})" if diff != 0 else ""
        print(f"  {t}: {c1} → {c2} {diff_str}")

    # 요소 타입별 변경 사항
    element_types = ["walls", "doors", "windows", "slabs", "stairs",
                     "spaces", "columns", "beams"]
    all_changes = []

    for type_key in element_types:
        orig_elems = orig.get(type_key, [])
        fixed_elems = fixed.get(type_key, [])

        # GUID로 매핑
        orig_by_guid = {e["guid"]: e for e in orig_elems}
        fixed_by_guid = {e["guid"]: e for e in fixed_elems}

        common_guids = set(orig_by_guid) & set(fixed_by_guid)

        for guid in common_guids:
            changes = _compare_element(orig_by_guid[guid], fixed_by_guid[guid])
            if changes:
                all_changes.append({
                    "type": type_key,
                    "guid": guid,
                    "name": orig_by_guid[guid].get("name"),
                    "changes": changes,
                })

    # 출력
    print(f"\n🔍 변경된 객체: {len(all_changes)}개")
    print("=" * 60)

    if not all_changes:
        print("\n⚪ 변경 사항 없음 (또는 모두 동일)")
        return {"total_changed": 0, "changes": []}

    for i, item in enumerate(all_changes, 1):
        print(f"\n{i}. [{item['type']}] {item['name']}")
        print(f"   GUID: {item['guid']}")
        for c in item["changes"]:
            before_str = _format_value(c["before"])
            after_str = _format_value(c["after"])
            print(f"   📌 {c['field']}")
            print(f"      이전: {before_str}")
            print(f"      이후: {after_str}")

    print("\n" + "=" * 60)
    print(f"✅ 총 {len(all_changes)}개 객체에서 변경 사항 발견")

    return {
        "total_changed": len(all_changes),
        "changes": all_changes,
    }


def _format_value(v) -> str:
    """값을 보기 좋게 포맷"""
    if v is None:
        return "❌ (없음)"
    if v == "":
        return "❌ (빈 문자열)"
    if isinstance(v, str) and ("_FIRE-RATING_" in v or "_PLACEHOLDER_" in v
                                or v.startswith("_") and v.endswith("_")):
        return f"⚠️ '{v}' (플레이스홀더)"
    if isinstance(v, str) and len(v) > 80:
        return f"'{v[:77]}...'"
    return f"'{v}'" if isinstance(v, str) else str(v)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법:")
        print("  python -m src.utils.compare_ifc <원본.ifc> <수정.ifc>")
        print("\n예시:")
        print("  python -m src.utils.compare_ifc \\")
        print("    samples/SimpleWall.ifc \\")
        print("    samples/SimpleWall_fixed.ifc")
        sys.exit(1)

    orig_path = sys.argv[1]
    fixed_path = sys.argv[2]

    if not Path(orig_path).exists():
        print(f"❌ 원본 파일 없음: {orig_path}")
        sys.exit(1)
    if not Path(fixed_path).exists():
        print(f"❌ 수정 파일 없음: {fixed_path}")
        print(f"   먼저 'python -m src.main {orig_path}' 실행")
        sys.exit(1)

    compare(orig_path, fixed_path)
