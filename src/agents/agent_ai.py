"""Agent AI — AI Agent + Tools 패턴

Claude가 IFC를 분석하고 위반/수정 의사결정을 내림.
Python 도구는 Claude의 결정에 따라 실제 IFC 조작을 수행.

흐름:
  1. Python: IFC 요약 데이터 추출
  2. Claude: 데이터 분석 + 위반 판단 (JSON 응답)
  3. Python: Claude 결정대로 fix 도구 호출
  4. Claude: 결과를 자연스러운 한국어 보고서로 작성

LLM 호출 횟수 / 실행 1회:
  - 위반 판단: 1번
  - 보고서 작성: 1번
  → 룰 컴파일까지 포함하면 13~14번
"""

import json
import os
from pathlib import Path
from typing import Optional

import anthropic
import ifcopenshell
import ifcopenshell.util.unit

# .env 자동 로드
try:
    from src.utils.env_loader import load_env
    load_env()
except ImportError:
    pass


MODEL = "claude-sonnet-4-6"


# ============================================
# 1. IFC 요약 추출 (Python — 도구)
# ============================================

def extract_ifc_summary(ifc_path: str, max_walls: int = 50) -> dict:
    """Claude에 전달할 IFC 요약 (토큰 절약)"""
    ifc = ifcopenshell.open(ifc_path)
    scale = ifcopenshell.util.unit.calculate_unit_scale(ifc)
    unit_label = "ft" if abs(scale - 0.3048) < 0.001 else ("mm" if abs(scale - 0.001) < 0.0001 else "m")

    walls_data = []
    for wall in ifc.by_type("IfcWall")[:max_walls]:
        try:
            ydim = None
            for rep in (wall.Representation.Representations if wall.Representation else []):
                for item in rep.Items:
                    if item.is_a("IfcExtrudedAreaSolid"):
                        p = item.SweptArea
                        if p.is_a("IfcRectangleProfileDef"):
                            ydim = p.YDim * scale * 1000  # mm 단위
                            break
            walls_data.append({
                "guid": wall.GlobalId,
                "name": (wall.Name or "")[:40],
                "thickness_mm": round(ydim, 1) if ydim else None,
                "is_external": _get_pset_value(wall, "Pset_WallCommon", "IsExternal"),
                "fire_rating": _get_pset_value(wall, "Pset_WallCommon", "FireRating"),
            })
        except Exception:
            continue

    return {
        "ifc_path": ifc_path,
        "schema": ifc.schema,
        "unit": unit_label,
        "unit_scale": scale,
        "total_walls": len(ifc.by_type("IfcWall")),
        "total_spaces": len(ifc.by_type("IfcSpace")),
        "total_stairs": len(ifc.by_type("IfcStair")),
        "walls_sample": walls_data,
    }


def _get_pset_value(element, pset_name, field):
    try:
        for rel in element.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                pdef = rel.RelatingPropertyDefinition
                if pdef.is_a("IfcPropertySet") and pdef.Name == pset_name:
                    for p in pdef.HasProperties:
                        if p.Name == field and hasattr(p, "NominalValue") and p.NominalValue:
                            return p.NominalValue.wrappedValue
    except Exception:
        pass
    return None


# ============================================
# 2. Claude 의사결정 (LLM)
# ============================================

DECIDE_SYSTEM_PROMPT = """너는 한국 건축법/소방법 BIM 검증 전문 AI 에이전트다.
IFC 모델 요약과 룰셋을 받아 위반 사항을 판단하고 수정 명령을 결정한다.

응답은 valid JSON만:
{
  "analysis": "전체 분석 한국어 (2~3문장)",
  "decisions": [
    {
      "guid": "벽 GUID",
      "rule_id": "위반 룰 ID (예: R_F11)",
      "current": "현재 상태 (예: 두께 200mm)",
      "target": "수정 목표 (예: 500mm)",
      "action": "fix_thickness | fix_firerating | fix_material",
      "args": {...},
      "reason": "한국어 사유"
    }
  ]
}

판단 기준:
- R_F3 화재등급: Pset_WallCommon.FireRating이 없거나 비표준이면 "2HR" 설정 필요
- R_F11 외벽 두께: IsExternal=true 외벽은 두께 250mm 이상이어야 함 (500mm로 표준화)
- R_F9 외벽 자재: IsExternal=true 외벽은 Concrete 등 불연재여야 함

- 모르겠으면 decisions 비워두기
- guid는 정확히 입력값에서 가져오기
- 한국어 자연스럽게
"""


def ai_decide_violations(ifc_summary: dict, rules_summary: list[dict]) -> dict:
    """Claude가 위반 판단 + 수정 명령 결정"""
    client = anthropic.Anthropic()

    user_msg = f"""IFC 요약:
{json.dumps(ifc_summary, indent=2, ensure_ascii=False)}

룰셋 ({len(rules_summary)}개):
{json.dumps(rules_summary, indent=2, ensure_ascii=False)}

위 데이터를 분석해서 위반 사항과 수정 명령을 결정하라.
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=DECIDE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = response.content[0].text.strip()
    # 마크다운 펜스 제거
    import re
    text = re.sub(r'^```(?:json)?\n?', '', text)
    text = re.sub(r'\n?```$', '', text)

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {"analysis": text[:500], "decisions": []}


# ============================================
# 3. Claude 결정대로 IFC 수정 (Python — 도구)
# ============================================

def apply_ai_decisions(ifc_path: str, decisions: list[dict], output_path: Optional[str] = None) -> dict:
    """Claude 의사결정대로 IFC 도구 호출 (Python이 실제 수정)"""
    if output_path is None:
        base = Path(ifc_path).stem
        output_path = f"samples/{base}_fixed.ifc"

    ifc = ifcopenshell.open(ifc_path)
    scale = ifcopenshell.util.unit.calculate_unit_scale(ifc)

    results = []
    for d in decisions:
        guid = d.get("guid")
        action = d.get("action", "")
        args = d.get("args", {})

        try:
            if action == "fix_thickness":
                r = _tool_fix_thickness(ifc, guid, args.get("thickness_mm", 500), scale)
            elif action == "fix_firerating":
                r = _tool_fix_firerating(ifc, guid, args.get("rating", "2HR"))
            elif action == "fix_material":
                r = _tool_fix_material(ifc, guid, args.get("material", "Concrete"), args.get("color"))
            else:
                r = {"status": "unknown_action", "action": action}
        except Exception as e:
            r = {"status": "error", "reason": str(e)}

        results.append({
            "guid": guid,
            "rule_id": d.get("rule_id"),
            "action": action,
            "result": r,
        })

    ifc.write(output_path)
    return {
        "output_ifc": output_path,
        "total_decisions": len(decisions),
        "success": sum(1 for r in results if r["result"].get("status") == "success"),
        "results": results,
    }


def _tool_fix_thickness(ifc, guid, thickness_mm, scale):
    """도구: 벽 두께 변경 (단위 변환 포함)"""
    wall = ifc.by_guid(guid)
    if not wall:
        return {"status": "error", "reason": "guid 없음"}

    new_value = thickness_mm / 1000.0 / scale
    changed = 0
    for rep in wall.Representation.Representations:
        for item in rep.Items:
            if item.is_a("IfcExtrudedAreaSolid") and item.SweptArea.is_a("IfcRectangleProfileDef"):
                item.SweptArea.YDim = new_value
                changed += 1
    return {"status": "success" if changed else "skipped", "thickness_mm": thickness_mm}


def _tool_fix_firerating(ifc, guid, rating):
    """도구: FireRating Pset 설정"""
    import ifcopenshell.api
    wall = ifc.by_guid(guid)
    if not wall:
        return {"status": "error", "reason": "guid 없음"}

    existing = None
    for rel in wall.IsDefinedBy:
        if rel.is_a("IfcRelDefinesByProperties"):
            pdef = rel.RelatingPropertyDefinition
            if pdef.is_a("IfcPropertySet") and pdef.Name == "Pset_WallCommon":
                existing = pdef
                break

    if existing is None:
        pset = ifcopenshell.api.run("pset.add_pset", ifc, product=wall, name="Pset_WallCommon")
    else:
        pset = existing
    ifcopenshell.api.run("pset.edit_pset", ifc, pset=pset, properties={"FireRating": rating})
    return {"status": "success", "rating": rating}


def _tool_fix_material(ifc, guid, material_name, color=None):
    """도구: 자재 변경 + 색깔"""
    import ifcopenshell.api
    wall = ifc.by_guid(guid)
    if not wall:
        return {"status": "error", "reason": "guid 없음"}

    # 자재
    existing = next((m for m in ifc.by_type("IfcMaterial") if m.Name == material_name), None)
    mat = existing or ifcopenshell.api.run("material.add_material", ifc, name=material_name)
    ifcopenshell.api.run("material.assign_material", ifc, products=[wall], type="IfcMaterial", material=mat)

    # 색
    if color and len(color) >= 3 and wall.Representation:
        r, g, b = float(color[0]), float(color[1]), float(color[2])
        if r > 1 or g > 1 or b > 1:
            r, g, b = r/255, g/255, b/255
        style = ifcopenshell.api.run("style.add_style", ifc, name=f"{material_name}_Style")
        ifcopenshell.api.run("style.add_surface_style", ifc, style=style,
            ifc_class="IfcSurfaceStyleShading",
            attributes={"SurfaceColour": {"Name": None, "Red": r, "Green": g, "Blue": b}})
        for rep in wall.Representation.Representations:
            ifcopenshell.api.run("style.assign_representation_styles", ifc,
                shape_representation=rep, styles=[style])

    return {"status": "success", "material": material_name, "color": color}


# ============================================
# 4. AI 보고서 작성 (LLM)
# ============================================

REPORT_SYSTEM_PROMPT = """너는 BIM 검토 전문 컨설턴트다.
검증 결과 + 수정 내역을 받아 친절하고 명확한 한국어 마크다운 보고서로 작성한다.

포함:
1. 요약 (전체 통계)
2. 주요 위반 사항 분석 (심각도 순)
3. 자동 수정 내역 (Before/After 명시)
4. 수동 검토 권고
5. 결론

스타일:
- 한국 건축법/소방법 맥락 반영
- 친절하고 명확한 톤
- 표/이모지 적절히 (🔴🟡🟢)
- "이 건물은..." 구체적으로
"""


def ai_write_report(ifc_summary: dict, ai_result: dict, ifc_name: str = "Unknown") -> str:
    """Claude가 한국어 보고서 작성"""
    client = anthropic.Anthropic()

    user_msg = f"""대상 IFC: {ifc_name}

IFC 요약:
{json.dumps(ifc_summary, indent=2, ensure_ascii=False)[:2000]}

AI 분석 + 수정 결과:
{json.dumps(ai_result, indent=2, ensure_ascii=False)[:3000]}

위 데이터로 한국어 마크다운 보고서 작성:
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=REPORT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return response.content[0].text


# ============================================
# 5. 통합 흐름
# ============================================

def run(
    ifc_path: str,
    rules_compiled_path: str = "samples/rules_compiled.json",
    output_ifc_path: Optional[str] = None,
    report_path: str = "samples/report_ai.md",
) -> dict:
    """AI Agent 모드 전체 실행"""
    print("\n" + "═" * 60)
    print("  🤖 BIMHarness — AI Agent 모드")
    print("  Claude가 IFC 분석 + 위반 판단 + 수정 결정")
    print("  Python 도구가 실제 IFC 조작 실행")
    print("═" * 60)

    # 1. IFC 요약 추출
    print("\n📦 [Python] IFC 요약 추출 중...")
    summary = extract_ifc_summary(ifc_path)
    print(f"   벽 {summary['total_walls']}개, 단위 {summary['unit']}")

    # 2. 룰 로드 (요약)
    rules = json.loads(Path(rules_compiled_path).read_text(encoding="utf-8"))
    rules_summary = [
        {"id": r["id"], "name": r["name"], "target": r["target"],
         "check": r.get("check", {}), "severity": r.get("severity")}
        for r in rules
    ]
    print(f"   룰 {len(rules_summary)}개 로드")

    # 3. Claude 판단
    print("\n💬 [Claude] IFC 분석 + 위반 판단 중... (API 호출 1번)")
    ai_decisions = ai_decide_violations(summary, rules_summary)

    analysis = ai_decisions.get("analysis", "")
    decisions = ai_decisions.get("decisions", [])
    print(f"\n💬 Claude 분석:")
    for line in analysis.split("\n")[:5]:
        print(f"   {line}")
    print(f"\n💬 Claude 결정: {len(decisions)}건 수정 명령")
    for d in decisions[:5]:
        print(f"   - {d.get('rule_id', '?')}: {d.get('guid', '')[:15]}... "
              f"{d.get('current', '')} → {d.get('target', '')}")

    # 4. Python이 도구 호출
    print(f"\n🔧 [Python] {len(decisions)}개 결정 실행 중...")
    ai_result = apply_ai_decisions(ifc_path, decisions, output_ifc_path)
    print(f"   성공: {ai_result['success']}/{ai_result['total_decisions']}")
    print(f"   출력: {ai_result['output_ifc']}")

    # 5. AI 보고서
    print("\n📝 [Claude] 한국어 보고서 작성 중... (API 호출 1번)")
    ifc_name = Path(ifc_path).name
    report_md = ai_write_report(summary, ai_result, ifc_name)
    Path(report_path).write_text(report_md, encoding="utf-8")
    print(f"   저장: {report_path} ({len(report_md)}자)")

    print("\n" + "═" * 60)
    print("  ✅ AI Agent 모드 완료")
    print("═" * 60)

    return {
        "ifc_summary": summary,
        "ai_analysis": analysis,
        "decisions_count": len(decisions),
        "fixed_count": ai_result["success"],
        "output_ifc": ai_result["output_ifc"],
        "report_path": report_path,
    }


if __name__ == "__main__":
    import sys
    ifc = sys.argv[1] if len(sys.argv) > 1 else "bimsample/SimpleWall.ifc"
    run(ifc)
