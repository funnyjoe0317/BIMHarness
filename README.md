# BIMHarness

> **자연어 룰 기반 BIM 자동 검증 · 수정 · 보고 멀티 에이전트 시스템**
>
> IFC 파일을 입력하면 자연어로 작성된 한국 건축법/사내 표준 룰셋을
> 자동으로 검증하고, 안전한 항목은 수정하며, 변경 보고서를 생성합니다.

```
rules.md (자연어)           SimpleWall.ifc
       │                          │
       ▼                          ▼
 ┌──────────┐              ┌─────────────┐
 │ Agent 2  │  rules.json  │  Agent 1    │
 │ 컴파일러 │ ───────────► │   파서      │
 │ (Claude) │              │ (Python)    │
 └──────────┘              └─────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   Agent 3       │
                         │   검증          │  →  violations.json
                         └─────────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   Agent 4       │
                         │   자동 수정     │  →  *_fixed.ifc
                         └─────────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   Agent 5       │
                         │   보고서        │  →  report.md
                         └─────────────────┘
```

---

## ✨ 주요 기능

- **자연어 룰** — `.md` 파일에 한국어로 룰 작성, Claude가 JSON으로 컴파일
- **5 에이전트 분업** — Parser · Interpreter · Validator · AutoFix · Reporter
- **안전한 자동 수정** — 화이트리스트 정책 (`pset_set_value`, `set_attribute`, `material_change`, `geometry_change`)
- **시각 변화** — IfcMaterial + RGB 색 + 형상 두께 자동 적용
- **SHA-256 무결성 검증** — 모든 변경은 로그 + 해시로 추적
- **비용 절감** — `--skip-compile`로 컴파일 결과 캐시 재사용

---

## 🚀 빠른 시작

### 1. 환경 셋업

```bash
git clone https://github.com/<your-id>/BIMHarness.git
cd BIMHarness

python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Claude API 키 설정
cp .env.example .env
# .env 파일 열어서 ANTHROPIC_API_KEY 입력
```

### 2. 샘플 실행

```bash
# 한국 건축법 8개 룰 (기본)
.venv/bin/python -m src.main bimsample/SimpleWall.ifc \
  --rules bimsample/rules_korean_law.md

# 화재 안전 11개 룰
.venv/bin/python -m src.main bimsample/SimpleWall.ifc \
  --rules bimsample/rules/core/fire_safety.md

# 컴파일 캐시 재사용 (API 호출 없음)
.venv/bin/python -m src.main bimsample/SimpleWall.ifc \
  --rules bimsample/rules/core/fire_safety.md \
  --skip-compile
```

### 3. 결과 확인

```
bimsample/SimpleWall_fixed.ifc   ← 수정된 IFC
bimsample/violations.json        ← 검증 결과
bimsample/changes.log.json       ← 변경 로그 + SHA-256
bimsample/report.md              ← 한국어 보고서
```

---

## 📂 폴더 구조

```
BIMHarness/
├── src/
│   ├── agents/
│   │   ├── agent_1_parser.py        # IFC → JSON 파싱
│   │   ├── agent_2_interpreter.py   # 자연어 룰 → JSON (Claude)
│   │   ├── agent_3_validator.py     # JSON 룰 검증
│   │   ├── agent_4_autofix.py       # 화이트리스트 자동 수정
│   │   └── agent_5_reporter.py      # 한국어 보고서 생성
│   ├── utils/
│   │   ├── env_loader.py            # .env 자동 로드
│   │   └── compare_ifc.py           # 원본/수정 비교
│   └── main.py                      # 통합 파이프라인
│
├── bimsample/                       # 공개 샘플 + 룰셋
│   ├── SimpleWall.ifc
│   ├── rules_korean_law.md
│   └── rules/
│       ├── core/fire_safety.md
│       └── sw_bridge/{midas_bridge,revit_import}.md
│
├── tests/
├── .env.example
└── requirements.txt
```

---

## 🛠️ 룰 작성 예시

`bimsample/rules/core/fire_safety.md` 발췌:

```markdown
## R_F9. 외벽 자재 + 색상 표준

- **id**: R_F9
- **target**: IfcWall
- **filter**: Pset_WallCommon.IsExternal == true
- **check**: 자재명이 "Concrete" 포함 여부
- **fix**: 자재 "Concrete" 적용 + RGB(0.5, 0.5, 0.5)
- **severity**: Medium
- **auto_fix**: 가능
- **reference**: 사내 시공 표준 v2026
```

→ Claude가 위 자연어를 다음 JSON으로 컴파일:

```json
{
  "id": "R_F9",
  "target": "IfcWall",
  "filter": {"pset": "Pset_WallCommon", "field": "IsExternal", "operator": "equals", "value": true},
  "check": {"type": "material_contains", "value": "Concrete"},
  "fix": {"type": "material_change", "value": "Concrete", "color": [0.5, 0.5, 0.5]},
  "severity": "Medium",
  "auto_fixable": true
}
```

---

## 🧩 룰셋 카테고리

| 카테고리 | 파일 | 룰 수 | 용도 |
|---------|------|------|------|
| **한국 건축법** | `bimsample/rules_korean_law.md` | 8 | 기본 데모 |
| **화재 안전** | `bimsample/rules/core/fire_safety.md` | 11 | 소방법 + 건축법 |
| **MIDAS 호환** | `bimsample/rules/sw_bridge/midas_bridge.md` | 8 | 구조해석 SW 이동 |
| **Revit Import** | `bimsample/rules/sw_bridge/revit_import.md` | 8 | ±32km 좌표 등 |

---

## 🔒 안전 규칙

자동 수정은 **화이트리스트 항목만**:

| Fix Type | 동작 | 위험도 |
|---------|------|--------|
| `pset_set_value` | Pset 값 채우기 (FireRating 등) | 낮음 ✅ |
| `set_attribute` | 속성 값 변경 (NominalWidth 등) | 낮음 ✅ |
| `material_change` | 자재명 + RGB 변경 | 중간 ✅ |
| `geometry_change` | 벽 두께 (YDim) 변경 | 중간 ✅ |
| 새 요소 추가/삭제 | **자동 X — 제안만** | 높음 ❌ |

모든 변경은 `changes.log.json`에 SHA-256 해시와 함께 기록됩니다.

---

## 📚 학술 베이스

- **TU 뮌헨 Borrmann 그룹** — Text2BIM (멀티 에이전트 LLM + BIM)
- **Anthropic MCP** — Model Context Protocol 표준
- **인호 외** — Dual-Layer Native Encoding (.bdna, SSRN #6532559)

---

## 🌱 로드맵

- [x] Mark 1: Anthropic Cloud (Claude Sonnet 4.6)
- [ ] Mark 2: Ollama 로컬 LLM (on-premise, 사내 보안)
- [ ] Mark 3: Revit 플러그인 연동
- [ ] Mark 4: 룰셋 마켓플레이스

---

## 📄 라이선스

MIT License

---

## 🔗 외부 자료

- IFC 표준: https://www.iso.org/standard/70303.html
- ifcopenshell: https://docs.ifcopenshell.org/
- Anthropic MCP: https://modelcontextprotocol.io/
- BuildingSMART 샘플: https://github.com/buildingsmart-community/Community-Sample-Test-Files
