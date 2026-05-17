"""Agent AI ReAct — Anthropic Tool Use API 기반 진짜 AI Agent

Claude가 도구를 자율적으로 여러 번 호출하면서 위반 사항을 단계별로 처리.

흐름 (옵션 F):
  1. 사용자: "이 IFC 검사하고 수정해줘"
  2. Claude → list_walls 호출 → 벽 목록 받음
  3. Claude → fix_thickness 호출 (각 위반 벽마다)
  4. Claude → fix_firerating 호출
  5. Claude → fix_material 호출
  6. Claude → save_ifc 호출
  7. Claude → "완료" 응답

옵션 E와 차이:
  - 옵션 E: Claude 2번 호출 (일괄 결정 + 보고서)
  - 옵션 F: Claude N+1번 호출 (도구 호출마다 결정)
  - 옵션 F는 산업 표준 ReAct/Agentic 패턴 (Claude Code, Cursor 등 동일)
"""

import json
import os
from pathlib import Path
from typing import Optional

import anthropic
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.unit

# .env 자동 로드
try:
    from src.utils.env_loader import load_env
    load_env()
except ImportError:
    pass


MODEL = "claude-sonnet-4-6"
MAX_ITERATIONS = 50  # 무한 루프 방지


# ============================================
# 도구 정의 (Claude가 호출할 수 있는 함수들)
# ============================================

TOOLS = [
    {
        "name": "list_walls",
        "description": (
            "IFC의 벽 목록을 반환합니다. "
            "각 벽은 GUID, 이름, 두께(mm), IsExternal, FireRating, 자재명 포함."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "fix_thickness",
        "description": (
            "특정 벽의 두께를 변경합니다. "
            "단위는 mm 기준. IFC 단위(피트/m)는 자동 변환."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "guid": {"type": "string", "description": "벽의 GlobalId"},
                "thickness_mm": {"type": "number", "description": "새 두께 (mm)"},
            },
            "required": ["guid", "thickness_mm"],
        },
    },
    {
        "name": "fix_firerating",
        "description": "특정 벽의 Pset_WallCommon.FireRating 값을 설정합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "guid": {"type": "string"},
                "rating": {"type": "string", "description": "예: '2HR', '1HR'"},
            },
            "required": ["guid", "rating"],
        },
    },
    {
        "name": "fix_material",
        "description": (
            "특정 벽의 자재를 변경합니다. "
            "선택적으로 RGB 색깔(0~1) 지정 가능."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "guid": {"type": "string"},
                "material_name": {"type": "string", "description": "예: 'Concrete', 'Brick'"},
                "color_rgb": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "선택. RGB 각각 0~1. 예: [1.0, 0.0, 0.0] = 빨강",
                },
            },
            "required": ["guid", "material_name"],
        },
    },
    {
        "name": "save_ifc",
        "description": "수정된 IFC를 파일로 저장합니다. 모든 변경 작업 후 마지막에 호출하세요.",
        "input_schema": {
            "type": "object",
            "properties": {
                "output_path": {"type": "string", "description": "저장 경로"},
            },
            "required": ["output_path"],
        },
    },
]


# ============================================
# 도구 구현 (Python — Claude가 호출)
# ============================================

class IFCToolbox:
    """IFC 조작 도구 모음. Claude가 호출함."""

    def __init__(self, ifc_path: str):
        self.ifc_path = ifc_path
        self.ifc = ifcopenshell.open(ifc_path)
        self.unit_scale = ifcopenshell.util.unit.calculate_unit_scale(self.ifc)
        self.unit_label = (
            "ft" if abs(self.unit_scale - 0.3048) < 0.001
            else "mm" if abs(self.unit_scale - 0.001) < 0.0001
            else "m"
        )
        self.saved = False
        self.output_path = None

    def list_walls(self) -> dict:
        """벽 목록 반환"""
        walls = []
        for wall in self.ifc.by_type("IfcWall"):
            try:
                ydim = None
                for rep in (wall.Representation.Representations if wall.Representation else []):
                    for item in rep.Items:
                        if item.is_a("IfcExtrudedAreaSolid"):
                            p = item.SweptArea
                            if p.is_a("IfcRectangleProfileDef"):
                                ydim = p.YDim * self.unit_scale * 1000  # mm
                                break

                walls.append({
                    "guid": wall.GlobalId,
                    "name": (wall.Name or "")[:50],
                    "thickness_mm": round(ydim, 1) if ydim else None,
                    "is_external": self._get_pset(wall, "Pset_WallCommon", "IsExternal"),
                    "fire_rating": self._get_pset(wall, "Pset_WallCommon", "FireRating"),
                    "material": self._get_material_name(wall),
                })
            except Exception:
                continue

        return {
            "ifc_unit": self.unit_label,
            "total_walls": len(walls),
            "walls": walls,
        }

    def fix_thickness(self, guid: str, thickness_mm: float) -> dict:
        """벽 두께 변경"""
        wall = self.ifc.by_guid(guid)
        if not wall:
            return {"status": "error", "reason": f"guid 없음: {guid}"}

        new_value = thickness_mm / 1000.0 / self.unit_scale  # mm → IFC unit
        changed = 0
        if wall.Representation:
            for rep in wall.Representation.Representations:
                for item in rep.Items:
                    if item.is_a("IfcExtrudedAreaSolid") and item.SweptArea.is_a("IfcRectangleProfileDef"):
                        item.SweptArea.YDim = new_value
                        changed += 1
        return {
            "status": "success" if changed else "skipped",
            "guid": guid,
            "new_thickness_mm": thickness_mm,
            "changed_items": changed,
        }

    def fix_firerating(self, guid: str, rating: str) -> dict:
        """FireRating Pset 설정"""
        wall = self.ifc.by_guid(guid)
        if not wall:
            return {"status": "error", "reason": f"guid 없음: {guid}"}

        existing = None
        for rel in wall.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                pdef = rel.RelatingPropertyDefinition
                if pdef.is_a("IfcPropertySet") and pdef.Name == "Pset_WallCommon":
                    existing = pdef
                    break

        pset = existing if existing else ifcopenshell.api.run(
            "pset.add_pset", self.ifc, product=wall, name="Pset_WallCommon"
        )
        ifcopenshell.api.run(
            "pset.edit_pset", self.ifc, pset=pset, properties={"FireRating": rating}
        )
        return {"status": "success", "guid": guid, "rating": rating}

    def fix_material(
        self, guid: str, material_name: str, color_rgb: Optional[list] = None
    ) -> dict:
        """자재 변경 + 색깔"""
        wall = self.ifc.by_guid(guid)
        if not wall:
            return {"status": "error", "reason": f"guid 없음: {guid}"}

        # 자재
        existing = next((m for m in self.ifc.by_type("IfcMaterial") if m.Name == material_name), None)
        mat = existing or ifcopenshell.api.run(
            "material.add_material", self.ifc, name=material_name
        )
        ifcopenshell.api.run(
            "material.assign_material", self.ifc,
            products=[wall], type="IfcMaterial", material=mat
        )

        # 색
        if color_rgb and len(color_rgb) >= 3 and wall.Representation:
            r, g, b = float(color_rgb[0]), float(color_rgb[1]), float(color_rgb[2])
            if r > 1 or g > 1 or b > 1:
                r, g, b = r/255, g/255, b/255
            style = ifcopenshell.api.run(
                "style.add_style", self.ifc, name=f"{material_name}_Style"
            )
            ifcopenshell.api.run(
                "style.add_surface_style", self.ifc, style=style,
                ifc_class="IfcSurfaceStyleShading",
                attributes={"SurfaceColour": {"Name": None, "Red": r, "Green": g, "Blue": b}}
            )
            for rep in wall.Representation.Representations:
                ifcopenshell.api.run(
                    "style.assign_representation_styles", self.ifc,
                    shape_representation=rep, styles=[style]
                )

        return {
            "status": "success",
            "guid": guid,
            "material": material_name,
            "color": color_rgb,
        }

    def save_ifc(self, output_path: str) -> dict:
        """수정된 IFC 저장"""
        self.ifc.write(output_path)
        self.saved = True
        self.output_path = output_path
        return {"status": "success", "output_path": output_path}

    def _get_pset(self, element, pset_name, field):
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

    def _get_material_name(self, wall):
        try:
            for rel in wall.HasAssociations:
                if rel.is_a("IfcRelAssociatesMaterial"):
                    m = rel.RelatingMaterial
                    if hasattr(m, "Name") and m.Name:
                        return m.Name
                    return m.is_a()
        except Exception:
            pass
        return None


# ============================================
# ReAct 루프
# ============================================

SYSTEM_PROMPT = """너는 한국 건축법/소방법 BIM 검증 전문 AI 에이전트다.

사용자가 IFC 파일을 주면 다음 절차로 처리한다:
1. list_walls 도구로 벽 목록 확인
2. 한국 화재 안전 표준에 따라 위반 벽 식별:
   - 외벽(is_external=true) 두께 500mm 미만 → fix_thickness로 500mm 설정
   - FireRating이 None/비표준 → fix_firerating으로 "2HR" 설정
   - 자재가 None/비-Concrete → fix_material로 "Concrete" + 색깔 [1.0, 0.0, 0.0](빨강) 설정
3. 모든 수정 후 save_ifc로 저장
4. 한국어로 작업 결과 요약

규칙:
- 한 번에 한 도구씩 호출. 결과 확인 후 다음 결정.
- 위반 없으면 그냥 save_ifc 후 종료
- 모든 도구 호출은 정확한 GUID 사용
"""


def run_react_agent(
    ifc_path: str,
    output_path: Optional[str] = None,
    user_request: Optional[str] = None,
    verbose: bool = True,
) -> dict:
    """ReAct 루프 실행"""
    if output_path is None:
        base = Path(ifc_path).stem
        output_path = f"samples/{base}_fixed.ifc"

    if user_request is None:
        user_request = (
            f"이 IFC 파일을 한국 건축법 화재 안전 표준으로 검사하고 수정해줘. "
            f"수정 완료 후 '{output_path}'로 저장. "
            f"IFC 경로: {ifc_path}"
        )

    print("\n" + "═" * 60)
    print("  🤖 BIMHarness — ReAct AI Agent 모드 (옵션 F)")
    print("  Claude가 도구를 자율적으로 호출하며 BIM 처리")
    print("═" * 60)
    print(f"\n👤 User: {user_request}\n")

    toolbox = IFCToolbox(ifc_path)
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": user_request}]

    tool_handlers = {
        "list_walls": toolbox.list_walls,
        "fix_thickness": toolbox.fix_thickness,
        "fix_firerating": toolbox.fix_firerating,
        "fix_material": toolbox.fix_material,
        "save_ifc": toolbox.save_ifc,
    }

    history = {"api_calls": 0, "tool_calls": []}

    for iteration in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        history["api_calls"] += 1

        # 응답 출력
        if verbose:
            for block in response.content:
                if block.type == "text" and block.text.strip():
                    print(f"💬 Claude: {block.text.strip()}")

        # tool_use 없으면 종료
        if response.stop_reason != "tool_use":
            if verbose:
                print(f"\n✅ Agent 종료 (stop_reason={response.stop_reason})")
            break

        # 도구 호출 처리
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []

        for block in response.content:
            if block.type == "tool_use":
                if verbose:
                    args_str = ", ".join(f"{k}={v!r}" for k, v in block.input.items())
                    print(f"🔧 {block.name}({args_str[:100]})")

                try:
                    handler = tool_handlers.get(block.name)
                    if handler is None:
                        result = {"error": f"알 수 없는 도구: {block.name}"}
                    else:
                        result = handler(**block.input)
                    history["tool_calls"].append({"name": block.name, "result": result})
                except Exception as e:
                    result = {"error": str(e)}
                    history["tool_calls"].append({"name": block.name, "error": str(e)})

                if verbose:
                    result_str = json.dumps(result, ensure_ascii=False)
                    print(f"   ← {result_str[:120]}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        messages.append({"role": "user", "content": tool_results})

    else:
        print(f"\n⚠️ 최대 반복 ({MAX_ITERATIONS}) 도달")

    # 저장 안 됐으면 강제 저장
    if not toolbox.saved:
        toolbox.save_ifc(output_path)

    print("\n" + "═" * 60)
    print(f"  📊 통계")
    print(f"  • Claude API 호출: {history['api_calls']}번")
    print(f"  • 도구 호출: {len(history['tool_calls'])}번")
    print(f"  • 출력 IFC: {toolbox.output_path}")
    print("═" * 60)

    return {
        "output_ifc": toolbox.output_path,
        "api_calls": history["api_calls"],
        "tool_calls": history["tool_calls"],
        "tool_call_count": len(history["tool_calls"]),
    }


if __name__ == "__main__":
    import sys
    ifc = sys.argv[1] if len(sys.argv) > 1 else "bimsample/SimpleWall.ifc"
    run_react_agent(ifc)
