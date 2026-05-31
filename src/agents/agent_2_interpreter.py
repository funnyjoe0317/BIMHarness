"""
Agent 2: Rule Interpreter
자연어 룰(rules.md) → JSON 구조 컴파일러

흐름:
  rules_korean_law.md (자연어)
       ↓ parse_rules_md (구조 파싱)
  [{"id": "R1", "raw_text": "..."}, ...]
       ↓ compile_rule (Claude API or Mock)
  [{"id": "R1", "target": "...", "check": {...}}, ...]
       ↓ JSON 저장
  rules_compiled.json

사용:
  # 실제 컴파일 (ANTHROPIC_API_KEY 필요)
  python -m src.agents.agent_2_interpreter

  # Mock 모드 (API 키 없이 테스트)
  python -m src.agents.agent_2_interpreter --mock
"""

import json
import os
import re
import sys
from pathlib import Path

# .env 자동 로드
try:
    from src.utils.env_loader import load_env
    load_env()
except ImportError:
    pass


# ============================================
# 1. md 파일 파싱 (LLM 없이)
# ============================================

def parse_rules_md(md_path: str) -> list[dict]:
    """rules.md를 각 룰 섹션으로 분리.
    지원 ID 패턴:
      R1, R2 (숫자만)
      R_F1, R_MD1, R_RV1 (도메인 prefix)
      R_숫자/문자 자유 조합
    """
    text = Path(md_path).read_text(encoding="utf-8")

    # "## R{영숫자_조합}." 패턴 — R1, R_F1, R_MD1 등 모두 매칭
    id_pattern = r'R[A-Za-z0-9_]*\d+'
    sections = re.split(rf'(?=^## {id_pattern}\.)', text, flags=re.MULTILINE)

    rules = []
    for section in sections:
        match = re.match(rf'## ({id_pattern})\. (.+?)(?:\n|$)', section)
        if not match:
            continue

        rule_id = match.group(1)
        title = match.group(2).strip()

        # 룰 ID는 R로 시작 + 숫자로 끝나야 함 (가이드 섹션 제외)
        if rule_id.startswith("R") and rule_id[-1].isdigit():
            rules.append({
                "id": rule_id,
                "title": title,
                "raw_text": section.strip(),
            })

    return rules


# ============================================
# 2. Claude API 호출 (실제 모드)
# ============================================

SYSTEM_PROMPT = """당신은 BIM 검증 룰 컴파일러입니다.
한국어 자연어 룰을 다음 JSON 스키마로 변환하세요.

JSON 스키마:
{
  "id": "R{숫자}",
  "name": "룰 제목",
  "category": "한국 건축법 / 사내 표준",
  "target": "Ifc...",  // IfcWall, IfcStair 등
  "filter": {...} 또는 null,
  "check": {
    "type": "pset_value_valid | pset_value | attribute | geometry_dim | area_sum",
    "pset": "Pset_...",
    "field": "...",
    "operator": "equals | gte | lte | is_valid | is_in | contains",
    "value": ...,
    "invalid_values": [...] // is_valid일 때만
  },
  "fix": {...} 또는 null,
  "severity": "Low | Medium | High",
  "auto_fixable": true/false,
  "reference": "법 조항",
  "needs_llm": false
}

규칙:
- 반드시 valid JSON만 반환 (다른 텍스트 X)
- 코드 펜스(```json) 사용 OK
- 한국어 그대로 유지
- 모르는 값은 null로
"""


def _user_prompt(rule_raw: dict) -> str:
    """백엔드 공통 user 메시지"""
    return f"이 룰을 JSON으로 변환:\n\n{rule_raw['raw_text']}"


def _extract_json(text: str) -> dict:
    """LLM 응답 텍스트에서 JSON 추출 (```json 펜스 제거 후 파싱).

    Claude·Ollama 등 어떤 백엔드든 응답 후처리는 동일하므로 공통화.
    """
    s = text.strip()
    s = re.sub(r'^```(?:json)?\n?', '', s)
    s = re.sub(r'\n?```$', '', s)
    return json.loads(s.strip())


def compile_rule_via_claude(rule_raw: dict) -> dict:
    """자연어 룰 → JSON (Claude API, 클라우드)"""
    import anthropic

    client = anthropic.Anthropic()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_prompt(rule_raw)}]
    )

    text = response.content[0].text
    try:
        return _extract_json(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude가 invalid JSON 반환:\n{e}\n\n원문:\n{text}")


# ============================================
# 2-b. Ollama 호출 (온프레미스 로컬 LLM)
# ============================================
# 클라우드(Anthropic)로 IFC/룰을 보낼 수 없는 사내 보안망용.
# Claude 경로와 동일한 SYSTEM_PROMPT·출력 스키마 사용 → 드롭인 교체.
# HTTP는 urllib(stdlib)만 사용 — 새 의존성 없음.

OLLAMA_DEFAULT_HOST = "http://localhost:11434"
OLLAMA_DEFAULT_MODEL = "llama3.1"


def compile_rule_via_ollama(
    rule_raw: dict,
    model: str = None,
    host: str = None,
) -> dict:
    """자연어 룰 → JSON (로컬 Ollama LLM, 온프레미스).

    Args:
        rule_raw: parse_rules_md가 만든 {id, title, raw_text}
        model: Ollama 모델명 (기본: 환경변수 OLLAMA_MODEL 또는 llama3.1)
        host: Ollama 서버 (기본: 환경변수 OLLAMA_HOST 또는 localhost:11434)
    """
    import urllib.request
    import urllib.error

    model = model or os.environ.get("OLLAMA_MODEL") or OLLAMA_DEFAULT_MODEL
    host = (host or os.environ.get("OLLAMA_HOST") or OLLAMA_DEFAULT_HOST).rstrip("/")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(rule_raw)},
        ],
        "stream": False,
        "format": "json",          # Ollama가 valid JSON만 출력하도록 강제
        "options": {"temperature": 0},
    }
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Ollama 서버 연결 실패 ({host}). 로컬 LLM이 실행 중인지 확인하세요:\n"
            f"  1) ollama serve              # 서버 실행\n"
            f"  2) ollama pull {model}   # 모델 다운로드\n"
            f"  원인: {e}"
        ) from e

    content = (body.get("message") or {}).get("content", "")
    if not content:
        raise ValueError(f"Ollama 빈 응답: {body}")

    try:
        return _extract_json(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Ollama가 invalid JSON 반환:\n{e}\n\n원문:\n{content}")


# ============================================
# 3. Mock 모드 (API 키 없이 테스트)
# ============================================

MOCK_COMPILED_RULES = {
    "R1": {
        "id": "R1",
        "name": "방화구획",
        "category": "한국 건축법",
        "target": "IfcBuildingStorey",
        "filter": None,
        "check": {
            "type": "area_sum",
            "operator": "lte",
            "value": 1500.0,
            "unit": "m²",
            "method": "sum_of_slabs_or_spaces"
        },
        "fix": {
            "type": "needs_human_action",
            "suggestion": "방화벽 추가 (1500m² 단위로 구획)"
        },
        "severity": "High",
        "auto_fixable": False,
        "reference": "건축법 시행령 제46조",
        "needs_llm": False
    },
    "R2": {
        "id": "R2",
        "name": "비상계단 너비",
        "category": "한국 건축법",
        "target": "IfcStair",
        "filter": {
            "type": "or",
            "conditions": [
                {
                    "type": "attribute",
                    "field": "PredefinedType",
                    "operator": "equals",
                    "value": "FIRE_EXIT"
                },
                {
                    "type": "attribute",
                    "field": "Name",
                    "operator": "contains",
                    "value": "비상"
                }
            ]
        },
        "check": {
            "type": "geometry_dim",
            "field": "NominalWidth",
            "fallback_pset": "Pset_StairCommon",
            "fallback_field": "NominalWidth",
            "operator": "gte",
            "value": 1200,
            "unit": "mm"
        },
        "fix": {
            "type": "set_attribute",
            "field": "NominalWidth",
            "value": 1200
        },
        "severity": "High",
        "auto_fixable": True,
        "reference": "건축물 피난·방화구조 규칙 제15조",
        "needs_llm": False
    },
    "R3": {
        "id": "R3",
        "name": "화재등급 누락",
        "category": "한국 소방법",
        "target": "IfcWall",
        "filter": {
            "type": "or",
            "conditions": [
                {
                    "type": "pset_value",
                    "pset": "Pset_WallCommon",
                    "field": "LoadBearing",
                    "operator": "equals",
                    "value": True
                },
                {
                    "type": "pset_value",
                    "pset": "Pset_WallCommon",
                    "field": "IsExternal",
                    "operator": "equals",
                    "value": True
                }
            ]
        },
        "check": {
            "type": "pset_value_valid",
            "pset": "Pset_WallCommon",
            "field": "FireRating",
            "invalid_values": [None, "", "_FIRE-RATING_", "TBD", "?"]
        },
        "fix": {
            "type": "pset_set_value",
            "pset": "Pset_WallCommon",
            "field": "FireRating",
            "value": "2HR"
        },
        "severity": "Medium",
        "auto_fixable": True,
        "reference": "건축물의 피난·방화구조 규칙 제3조",
        "needs_llm": False
    },
    "R4": {
        "id": "R4",
        "name": "외벽 자재 표준",
        "category": "사내 표준",
        "target": "IfcWall",
        "filter": {
            "type": "pset_value",
            "pset": "Pset_WallCommon",
            "field": "IsExternal",
            "operator": "equals",
            "value": True
        },
        "check": {
            "type": "material_in",
            "operator": "is_in",
            "value": [
                "Concrete", "Brick", "Steel",
                "콘크리트", "벽돌", "철골"
            ],
            "match_mode": "contains"
        },
        "fix": {
            "type": "suggestion_only",
            "default_value": "Concrete",
            "note": "자재 변경은 구조 영향 — 수동 검토 필요"
        },
        "severity": "Low",
        "auto_fixable": False,
        "reference": "사내 시공 표준 v2026",
        "needs_llm": False
    },
    "R5": {
        "id": "R5",
        "name": "회의실 최소 면적",
        "category": "사내 표준",
        "target": "IfcSpace",
        "filter": {
            "type": "or",
            "conditions": [
                {
                    "type": "attribute",
                    "field": "LongName",
                    "operator": "contains",
                    "value": "회의실"
                },
                {
                    "type": "attribute",
                    "field": "LongName",
                    "operator": "contains",
                    "value": "meeting"
                },
                {
                    "type": "attribute",
                    "field": "PredefinedType",
                    "operator": "equals",
                    "value": "MEETING"
                }
            ]
        },
        "check": {
            "type": "area_value",
            "pset": "Qto_SpaceBaseQuantities",
            "field": "NetFloorArea",
            "fallback_pset": "BaseQuantities",
            "fallback_field": "GrossFloorArea",
            "operator": "gte",
            "value": 6.0,
            "unit": "m²"
        },
        "fix": {
            "type": "needs_human_action",
            "suggestion": "공간 재배치 필요 (자동 X)"
        },
        "severity": "Low",
        "auto_fixable": False,
        "reference": "사내 공간 표준",
        "needs_llm": False
    }
}


def compile_rule_mock(rule_raw: dict) -> dict:
    """Mock: 미리 정의된 JSON 반환 (API 없이 테스트)"""
    result = MOCK_COMPILED_RULES.get(rule_raw["id"])
    if result is None:
        raise ValueError(f"Mock에 없는 룰 ID: {rule_raw['id']}")
    return result


# ============================================
# 4. 검증
# ============================================

def validate_compiled_rule(rule_json: dict) -> tuple[bool, str]:
    """컴파일된 JSON 스키마 검증"""
    required = ["id", "target", "check", "severity"]
    missing = [k for k in required if k not in rule_json]
    if missing:
        return False, f"필수 필드 누락: {missing}"

    if not rule_json["target"].startswith("Ifc"):
        return False, f"target은 Ifc로 시작해야 함: {rule_json['target']}"

    severity = rule_json["severity"]
    if severity not in ["Low", "Medium", "High"]:
        return False, f"severity 값 부적절: {severity}"

    return True, "OK"


# ============================================
# 5. 메인 흐름
# ============================================

def compile_all(
    rules_md_path: str = "samples/rules_korean_law.md",
    output_path: str = "samples/rules_compiled.json",
    mock: bool = False,
    backend: str = "claude",
    model: str = None,
) -> list[dict]:
    """전체 룰 컴파일

    Args:
        backend: "claude" (클라우드) | "ollama" (온프레미스 로컬) | "mock" (테스트)
        model:   ollama 백엔드일 때 모델명 (기본: llama3.1 / OLLAMA_MODEL)
        mock:    하위호환 — True면 backend="mock"
    """
    if mock:
        backend = "mock"

    compilers = {
        "claude": compile_rule_via_claude,
        "ollama": lambda raw: compile_rule_via_ollama(raw, model=model),
        "mock": compile_rule_mock,
    }
    if backend not in compilers:
        raise ValueError(f"알 수 없는 backend: {backend} (claude | ollama | mock)")

    labels = {
        "claude": "클라우드 (Anthropic Claude)",
        "ollama": f"온프레미스 로컬 LLM (Ollama / {model or os.environ.get('OLLAMA_MODEL') or OLLAMA_DEFAULT_MODEL})",
        "mock": "MOCK (API 없음)",
    }
    print("=" * 60)
    print(f"📖 Agent 2: 룰 컴파일 시작 — {labels[backend]}")
    print("=" * 60)

    raw_rules = parse_rules_md(rules_md_path)
    print(f"\n발견된 룰: {len(raw_rules)}개")
    for r in raw_rules:
        print(f"  - {r['id']}: {r['title']}")

    print("\n" + "=" * 60)
    print("컴파일 시작")
    print("=" * 60)

    compiler = compilers[backend]
    compiled = []

    try:
        from tqdm import tqdm
        iterator = tqdm(raw_rules, desc="🔨 룰 컴파일", unit="rule")
    except ImportError:
        iterator = raw_rules

    for raw in iterator:
        try:
            rule_json = compiler(raw)
            ok, msg = validate_compiled_rule(rule_json)
            if ok:
                compiled.append(rule_json)
            else:
                print(f"\n   ⚠️  {raw['id']} 검증 실패: {msg}")
        except Exception as e:
            print(f"\n   ❌ {raw['id']} 에러: {e}")

    # 저장
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(compiled, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"📦 저장: {output_path}")
    print(f"   {len(compiled)}/{len(raw_rules)}개 룰 컴파일 성공")
    print("=" * 60)

    return compiled


if __name__ == "__main__":
    args = sys.argv[1:]

    # 백엔드 선택: --mock | --ollama | --backend <name>
    backend = "claude"
    if "--mock" in args:
        backend = "mock"
    if "--ollama" in args:
        backend = "ollama"
    if "--backend" in args:
        i = args.index("--backend")
        if i + 1 < len(args):
            backend = args[i + 1]

    # --model <name> (ollama 모델 지정)
    model = None
    if "--model" in args:
        i = args.index("--model")
        if i + 1 < len(args):
            model = args[i + 1]

    compile_all(backend=backend, model=model)
