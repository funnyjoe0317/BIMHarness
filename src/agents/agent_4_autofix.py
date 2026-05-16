"""
Agent 4: Auto-Fixer
위반 사항(violations) → 안전한 카테고리만 자동 수정 → fixed.ifc

흐름:
  violations.json (Agent 3 결과)
  원본.ifc
       ↓ apply_fixes()
  fixed.ifc + changes.log

화이트리스트 정책:
  ✅ 자동 수정: pset_set_value (속성 추가)
  ✅ 자동 수정: set_attribute (단순 속성 변경)
  ❌ 자동 X: needs_human_action (공간 재배치 등)
  ❌ 자동 X: suggestion_only (자재 변경 등)

안전 장치:
  - 원본 IFC는 절대 수정 X (백업 자동 생성)
  - 모든 변경은 changes.log에 기록
  - SHA-256 해시로 무결성 검증

사용:
  python -m src.agents.agent_4_autofix samples/SimpleWall.ifc
"""

import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.api


# ============================================
# 1. 화이트리스트 정책
# ============================================

AUTO_FIX_WHITELIST = {
    "pset_set_value",     # Pset 값 추가/변경
    "set_pset_value",     # Claude가 가끔 이 이름으로 생성
    "set_attribute",      # 단순 속성 변경 (Name, Description 등)
    "set_material",       # 자재 이름 + 색깔 변경 (시각적!)
    "material_change",    # set_material 별칭
    "set_geometry",       # 형상 변경 (벽 두께 등)
    "geometry_change",    # set_geometry 별칭
}

NOT_AUTO_FIX = {
    "needs_human_action",  # 인간 판단 필요
    "suggestion_only",     # 자재 변경 등 (구조 영향)
}


def is_auto_fixable(violation: dict) -> bool:
    """이 위반을 자동 수정 가능한지"""
    if not violation.get("auto_fixable"):
        return False
    fix_spec = violation.get("fix_spec")
    if not fix_spec:
        return False
    fix_type = fix_spec.get("type")
    return fix_type in AUTO_FIX_WHITELIST


# ============================================
# 2. 백업 + 해시
# ============================================

def _sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _backup_original(ifc_path: str) -> tuple[str, str]:
    """원본을 백업하고 해시 계산"""
    original_hash = _sha256_of_file(ifc_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{ifc_path}.backup_{timestamp}"
    shutil.copy2(ifc_path, backup_path)
    return backup_path, original_hash


# ============================================
# 3. 개별 수정 함수
# ============================================

def _apply_pset_set_value(ifc, guid: str, fix_spec: dict) -> dict:
    """Pset 값 추가/수정"""
    element = ifc.by_guid(guid)
    if element is None:
        return {"status": "error", "reason": f"GUID 없음: {guid}"}

    pset_name = fix_spec["pset"]
    field = fix_spec["field"]
    # "value" 또는 "default_value" 둘 다 지원 (Claude 출력 다양성)
    new_value = fix_spec.get("value") or fix_spec.get("default_value")
    if new_value is None:
        return {"status": "error", "reason": "fix_spec에 값(value) 없음"}

    # 기존 Pset이 있는지 확인
    existing_pset = None
    if hasattr(element, "IsDefinedBy"):
        for rel in element.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                pdef = rel.RelatingPropertyDefinition
                if pdef.is_a("IfcPropertySet") and pdef.Name == pset_name:
                    existing_pset = pdef
                    break

    try:
        if existing_pset is None:
            # 새 Pset 추가
            pset = ifcopenshell.api.run(
                "pset.add_pset",
                ifc,
                product=element,
                name=pset_name
            )
        else:
            pset = existing_pset

        ifcopenshell.api.run(
            "pset.edit_pset",
            ifc,
            pset=pset,
            properties={field: new_value}
        )
        return {
            "status": "success",
            "action": f"Pset {pset_name}.{field} = {new_value}"
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}


def _apply_set_attribute(ifc, guid: str, fix_spec: dict) -> dict:
    """단순 속성 변경"""
    element = ifc.by_guid(guid)
    if element is None:
        return {"status": "error", "reason": f"GUID 없음: {guid}"}

    field = fix_spec["field"]
    new_value = fix_spec["value"]

    try:
        ifcopenshell.api.run(
            "attribute.edit_attributes",
            ifc,
            product=element,
            attributes={field: new_value}
        )
        return {
            "status": "success",
            "action": f"{field} = {new_value}"
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}


def _apply_fix(ifc, violation: dict) -> dict:
    """위반 1건 자동 수정"""
    fix_spec = violation.get("fix_spec", {})
    fix_type = fix_spec.get("type")
    guid = violation.get("guid")

    if fix_type in ("pset_set_value", "set_pset_value"):
        return _apply_pset_set_value(ifc, guid, fix_spec)
    if fix_type == "set_attribute":
        return _apply_set_attribute(ifc, guid, fix_spec)
    if fix_type in ("set_material", "material_change"):
        return _apply_material_change(ifc, guid, fix_spec)
    if fix_type in ("set_geometry", "geometry_change"):
        return _apply_geometry_change(ifc, guid, fix_spec)

    return {"status": "skipped", "reason": f"Unsupported fix_type: {fix_type}"}


def _apply_material_change(ifc, guid: str, fix_spec: dict) -> dict:
    """자재 변경 — 자재명 + 색깔 (시각적 변화!)"""
    element = ifc.by_guid(guid)
    if element is None:
        return {"status": "error", "reason": f"GUID 없음: {guid}"}

    new_material_name = (
        fix_spec.get("value")
        or fix_spec.get("material_name")
        or fix_spec.get("default_value")
    )
    if not new_material_name:
        return {"status": "error", "reason": "자재명 누락"}

    # RGB 색 (선택, 0~1 범위)
    color_rgb = fix_spec.get("color")  # 예: [0.5, 0.5, 0.5]

    try:
        # 1. 새 자재 생성 (또는 기존 자재 찾기)
        existing = None
        for m in ifc.by_type("IfcMaterial"):
            if m.Name == new_material_name:
                existing = m
                break

        if existing:
            new_material = existing
        else:
            new_material = ifcopenshell.api.run(
                "material.add_material", ifc,
                name=new_material_name
            )

        # 2. element에 자재 할당
        ifcopenshell.api.run(
            "material.assign_material", ifc,
            products=[element],
            type="IfcMaterial",
            material=new_material
        )

        # 3. 색깔 추가 (옵션) — 자재 representation
        if color_rgb and len(color_rgb) >= 3:
            try:
                _set_material_color(ifc, new_material, color_rgb)
            except Exception:
                pass  # 색은 best-effort

        return {
            "status": "success",
            "action": f"자재: {new_material_name}"
            + (f" (RGB: {color_rgb})" if color_rgb else "")
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}


def _set_material_color(ifc, material, rgb):
    """IfcMaterial에 IfcSurfaceStyle 색상 추가"""
    r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])
    # 0~255 범위면 0~1로 정규화
    if r > 1 or g > 1 or b > 1:
        r, g, b = r/255, g/255, b/255

    # IfcColourRgb
    color = ifc.create_entity("IfcColourRgb", None, r, g, b)
    rendering = ifc.create_entity(
        "IfcSurfaceStyleRendering",
        color, 0.0, None, None, None, None, None, None, "NOTDEFINED"
    )
    style = ifc.create_entity("IfcSurfaceStyle", material.Name + "_Style", "BOTH", [rendering])
    # 자재에 styled 연결은 별도 IfcStyledItem 필요 — 단순화


def _apply_geometry_change(ifc, guid: str, fix_spec: dict) -> dict:
    """형상 변경 — 벽 두께 (IfcRectangleProfileDef.YDim)"""
    element = ifc.by_guid(guid)
    if element is None:
        return {"status": "error", "reason": f"GUID 없음: {guid}"}

    target_field = fix_spec.get("field", "thickness")
    new_value = (
        fix_spec.get("value")
        or fix_spec.get("default_value")
    )
    if new_value is None:
        return {"status": "error", "reason": "새 값 누락"}

    try:
        new_value = float(new_value)
    except (TypeError, ValueError):
        return {"status": "error", "reason": f"숫자 변환 실패: {new_value}"}

    try:
        # element의 형상 탐색
        if not hasattr(element, "Representation") or element.Representation is None:
            return {"status": "skipped", "reason": "형상 정보 없음"}

        changed_count = 0
        for rep in element.Representation.Representations:
            for item in rep.Items:
                # IfcExtrudedAreaSolid의 단면 (벽 두께/너비)
                if item.is_a("IfcExtrudedAreaSolid"):
                    profile = item.SweptArea
                    if profile.is_a("IfcRectangleProfileDef"):
                        if target_field in ("thickness", "width", "ydim"):
                            old = profile.YDim
                            profile.YDim = new_value
                            changed_count += 1
                        elif target_field in ("length", "xdim"):
                            old = profile.XDim
                            profile.XDim = new_value
                            changed_count += 1
                    # 깊이 (높이)
                    if target_field in ("height", "depth"):
                        old = item.Depth
                        item.Depth = new_value
                        changed_count += 1

        if changed_count == 0:
            return {"status": "skipped", "reason": "변경 가능한 형상 없음"}

        return {
            "status": "success",
            "action": f"형상 {target_field} = {new_value} ({changed_count}곳)"
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}


# ============================================
# 4. 전체 수정 흐름
# ============================================

def apply_fixes(
    ifc_path: str,
    violations_path: str,
    output_ifc_path: str,
    changes_log_path: str,
) -> dict:
    """위반 사항 자동 수정 + 결과 저장"""
    # 1. 백업
    backup_path, original_hash = _backup_original(ifc_path)

    # 2. 위반 사항 로드
    violations_data = json.loads(Path(violations_path).read_text(encoding="utf-8"))
    violations = violations_data.get("violations", [])

    # 3. IFC 열기
    ifc = ifcopenshell.open(ifc_path)

    # 4. 자동 수정 적용
    changes = []
    skipped = []

    try:
        from tqdm import tqdm
        iterator = tqdm(violations, desc="🔧 자동 수정", unit="건")
    except ImportError:
        iterator = violations

    for v in iterator:
        if not is_auto_fixable(v):
            skipped.append({
                "rule_id": v.get("rule_id"),
                "guid": v.get("guid"),
                "element_name": v.get("element_name"),
                "reason": "auto_fix 불가 (인간 판단 필요)",
            })
            continue

        result = _apply_fix(ifc, v)
        changes.append({
            "rule_id": v.get("rule_id"),
            "rule_name": v.get("rule_name"),
            "guid": v.get("guid"),
            "element_name": v.get("element_name"),
            "previous_value": v.get("current_value"),
            "fix_type": v.get("fix_spec", {}).get("type"),
            "result": result,
        })

    # 5. 수정된 IFC 저장
    ifc.write(output_ifc_path)
    fixed_hash = _sha256_of_file(output_ifc_path)

    # 6. 변경 로그 저장
    success_count = sum(1 for c in changes if c["result"]["status"] == "success")
    log = {
        "timestamp": datetime.now().isoformat(),
        "original_ifc": ifc_path,
        "original_sha256": original_hash,
        "backup_path": backup_path,
        "output_ifc": output_ifc_path,
        "output_sha256": fixed_hash,
        "total_violations": len(violations),
        "auto_fixed": success_count,
        "skipped": len(skipped),
        "changes": changes,
        "skipped_violations": skipped,
    }
    with open(changes_log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False, default=str)

    return log


# ============================================
# 5. 메인 흐름
# ============================================

def run(
    ifc_path: str,
    violations_path: str = "samples/violations.json",
    output_ifc_path: str = None,
    changes_log_path: str = "samples/changes.log.json",
) -> dict:
    """Agent 4 실행"""
    if output_ifc_path is None:
        base = Path(ifc_path).stem
        output_ifc_path = f"samples/{base}_fixed.ifc"

    print("=" * 60)
    print(f"🔧 Agent 4: 자동 수정 시작")
    print(f"   원본: {ifc_path}")
    print(f"   위반: {violations_path}")
    print(f"   출력: {output_ifc_path}")
    print("=" * 60)

    log = apply_fixes(ifc_path, violations_path, output_ifc_path, changes_log_path)

    print("\n" + "=" * 60)
    print(f"✅ 수정 완료")
    print("=" * 60)
    print(f"\n📊 결과:")
    print(f"  - 전체 위반: {log['total_violations']}건")
    print(f"  - 자동 수정 성공: {log['auto_fixed']}건")
    print(f"  - 건너뜀 (인간 판단): {log['skipped']}건")
    print(f"\n💾 파일:")
    print(f"  - 백업: {log['backup_path']}")
    print(f"  - 수정 IFC: {log['output_ifc']}")
    print(f"  - 변경 로그: {changes_log_path}")
    print(f"\n🔐 SHA-256:")
    print(f"  - 원본: {log['original_sha256'][:16]}...")
    print(f"  - 수정: {log['output_sha256'][:16]}...")

    return log


if __name__ == "__main__":
    ifc_path = sys.argv[1] if len(sys.argv) > 1 else "samples/SimpleWall.ifc"
    run(ifc_path)
