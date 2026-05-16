"""
Agent 1: IFC Parser
입력: .ifc 파일
출력: 구조화된 dict (Agent 2~5가 사용)
"""

from typing import Optional

import ifcopenshell
import ifcopenshell.util.element


def parse_ifc(path: str) -> dict:
    """IFC 파일을 구조화된 dict로 변환"""
    ifc = ifcopenshell.open(path)
    return {
        "schema": ifc.schema,
        "total_entities": len(list(ifc)),
        "project": _parse_project(ifc),
        "site": _parse_site(ifc),
        "building": _parse_building(ifc),
        "storeys": [_parse_storey(s) for s in ifc.by_type("IfcBuildingStorey")],
        "walls": [_parse_wall(w) for w in ifc.by_type("IfcWall")],
        "doors": [_parse_door(d) for d in ifc.by_type("IfcDoor")],
        "windows": [_parse_window(w) for w in ifc.by_type("IfcWindow")],
        "slabs": [_parse_slab(s) for s in ifc.by_type("IfcSlab")],
        "spaces": [_parse_space(s) for s in ifc.by_type("IfcSpace")],
        "stairs": [_parse_stair(s) for s in ifc.by_type("IfcStair")],
        "columns": [_parse_simple(c) for c in ifc.by_type("IfcColumn")],
        "beams": [_parse_simple(b) for b in ifc.by_type("IfcBeam")],
        "counts": _count_elements(ifc),
    }


def _parse_project(ifc):
    projects = ifc.by_type("IfcProject")
    if not projects:
        return None
    p = projects[0]
    return {
        "guid": p.GlobalId,
        "name": p.Name,
        "description": p.Description,
        "long_name": getattr(p, "LongName", None),
    }


def _parse_site(ifc):
    sites = ifc.by_type("IfcSite")
    if not sites:
        return None
    s = sites[0]
    return {
        "guid": s.GlobalId,
        "name": s.Name,
        "ref_latitude": getattr(s, "RefLatitude", None),
        "ref_longitude": getattr(s, "RefLongitude", None),
    }


def _parse_building(ifc):
    buildings = ifc.by_type("IfcBuilding")
    if not buildings:
        return None
    b = buildings[0]
    return {
        "guid": b.GlobalId,
        "name": b.Name,
        "description": b.Description,
        "long_name": getattr(b, "LongName", None),
        "elevation_of_ref": getattr(b, "ElevationOfRefHeight", None),
    }


def _parse_storey(storey):
    return {
        "guid": storey.GlobalId,
        "name": storey.Name,
        "elevation": getattr(storey, "Elevation", None),
        "long_name": getattr(storey, "LongName", None),
        "psets": _get_psets_safe(storey),
    }


def _parse_wall(wall):
    return {
        "guid": wall.GlobalId,
        "name": wall.Name,
        "description": wall.Description,
        "predefined_type": getattr(wall, "PredefinedType", None),
        "psets": _get_psets_safe(wall),
        "material": _get_material_name(wall),
        "contained_in": _get_contained_storey_name(wall),
    }


def _parse_door(door):
    return {
        "guid": door.GlobalId,
        "name": door.Name,
        "overall_height": getattr(door, "OverallHeight", None),
        "overall_width": getattr(door, "OverallWidth", None),
        "predefined_type": getattr(door, "PredefinedType", None),
        "psets": _get_psets_safe(door),
        "contained_in": _get_contained_storey_name(door),
    }


def _parse_window(win):
    return {
        "guid": win.GlobalId,
        "name": win.Name,
        "overall_height": getattr(win, "OverallHeight", None),
        "overall_width": getattr(win, "OverallWidth", None),
        "predefined_type": getattr(win, "PredefinedType", None),
        "psets": _get_psets_safe(win),
        "contained_in": _get_contained_storey_name(win),
    }


def _parse_slab(slab):
    return {
        "guid": slab.GlobalId,
        "name": slab.Name,
        "predefined_type": getattr(slab, "PredefinedType", None),
        "psets": _get_psets_safe(slab),
        "material": _get_material_name(slab),
        "contained_in": _get_contained_storey_name(slab),
    }


def _parse_space(space):
    return {
        "guid": space.GlobalId,
        "name": space.Name,
        "long_name": getattr(space, "LongName", None),
        "predefined_type": getattr(space, "PredefinedType", None),
        "psets": _get_psets_safe(space),
        "contained_in": _get_contained_storey_name(space),
    }


def _parse_stair(stair):
    return {
        "guid": stair.GlobalId,
        "name": stair.Name,
        "predefined_type": getattr(stair, "PredefinedType", None),
        "psets": _get_psets_safe(stair),
        "contained_in": _get_contained_storey_name(stair),
    }


def _parse_simple(element):
    return {
        "guid": element.GlobalId,
        "name": element.Name,
        "predefined_type": getattr(element, "PredefinedType", None),
        "psets": _get_psets_safe(element),
        "material": _get_material_name(element),
        "contained_in": _get_contained_storey_name(element),
    }


def _get_psets_safe(element) -> dict:
    try:
        return ifcopenshell.util.element.get_psets(element) or {}
    except Exception:
        return {}


def _get_material_name(element) -> Optional[str]:
    try:
        mats = ifcopenshell.util.element.get_material(element)
        if mats is None:
            return None
        if hasattr(mats, "Name") and mats.Name:
            return mats.Name
        if hasattr(mats, "ForLayerSet"):
            return getattr(mats.ForLayerSet, "LayerSetName", None)
        return str(mats.is_a())
    except Exception:
        return None


def _get_contained_storey_name(element) -> Optional[str]:
    try:
        storey = ifcopenshell.util.element.get_container(element)
        if storey and storey.is_a("IfcBuildingStorey"):
            return storey.Name
        return None
    except Exception:
        return None


def _count_elements(ifc) -> dict:
    types = [
        "IfcWall", "IfcDoor", "IfcWindow", "IfcSlab", "IfcRoof",
        "IfcStair", "IfcColumn", "IfcBeam", "IfcSpace",
        "IfcBuildingStorey", "IfcBuilding", "IfcSite", "IfcProject",
    ]
    counts = {}
    for t in types:
        n = len(ifc.by_type(t))
        if n > 0:
            counts[t] = n
    return counts


def to_summary_text(parsed: dict) -> str:
    """LLM에 줄 요약 텍스트 (토큰 효율)"""
    p = parsed.get("project") or {}
    b = parsed.get("building") or {}

    lines = [
        "# IFC 파일 요약",
        "",
        f"- 스키마: {parsed['schema']}",
        f"- 총 엔티티: {parsed['total_entities']}개",
        f"- 프로젝트: {p.get('name') or '(없음)'}",
        f"- 건물: {b.get('name') or '(없음)'}",
        "",
        "## 요소 카운트",
    ]
    for t, c in parsed.get("counts", {}).items():
        lines.append(f"- {t}: {c}개")

    storeys = parsed.get("storeys", [])
    if storeys:
        lines.append("")
        lines.append("## 층 정보")
        for s in storeys[:20]:
            elev = s.get("elevation")
            elev_str = f"{elev:.0f}mm" if isinstance(elev, (int, float)) else "?"
            lines.append(f"- {s.get('name') or '(이름없음)'} (elev: {elev_str})")

    return "\n".join(lines)


def get_walls_by_storey(parsed: dict) -> dict:
    """층별 벽 그룹화"""
    result = {}
    for w in parsed.get("walls", []):
        key = w.get("contained_in") or "(미배치)"
        result.setdefault(key, []).append(w)
    return result


def get_elements_by_type(parsed: dict, ifc_type: str) -> list:
    """타입별 요소 추출 (소문자 키 매핑)"""
    mapping = {
        "IfcWall": "walls",
        "IfcDoor": "doors",
        "IfcWindow": "windows",
        "IfcSlab": "slabs",
        "IfcSpace": "spaces",
        "IfcStair": "stairs",
        "IfcColumn": "columns",
        "IfcBeam": "beams",
        "IfcBuildingStorey": "storeys",
    }
    key = mapping.get(ifc_type)
    if not key:
        return []
    return parsed.get(key, [])


if __name__ == "__main__":
    import json
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "samples/SimpleWall.ifc"
    print(f"\n📂 파싱: {path}")
    print("=" * 60)

    data = parse_ifc(path)

    print("\n" + to_summary_text(data))

    if data["walls"]:
        print("\n## 첫 번째 벽 상세")
        print(json.dumps(data["walls"][0], indent=2,
                         ensure_ascii=False, default=str))
