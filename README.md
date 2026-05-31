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

- **자연어 룰** — `.md` 파일에 한국어로 룰 작성, LLM이 JSON으로 컴파일
- **온프레미스 옵션** — 클라우드(Claude) ↔ 로컬 LLM(Ollama) 백엔드 스위치. 사내망 밖으로 IFC/룰 안 나감
- **5 에이전트 분업** — Parser · Interpreter · Validator · AutoFix · Reporter
- **AI Agent + Tools 패턴** — Claude가 IFC 분석/위반 판단/수정 결정, Python 도구가 IFC 조작
- **MCP 서버** — Claude Desktop, Cursor 등 표준 AI 클라이언트에서 자연어로 BIM 작업 호출
- **안전한 자동 수정** — 화이트리스트 정책 (`pset_set_value`, `set_attribute`, `material_change`, `geometry_change`)
- **단위 자동 변환** — IFC 단위(mm/피트/m)에 맞춰 수치 자동 변환
- **시각 변화** — IfcMaterial + RGB 색 + 형상 두께 자동 적용 (Navisworks/BIM Vision 확인 가능)
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

## 🤖 AI Agent 모드 (2가지 패턴)

### 옵션 E: 1-shot Batch (`agent_ai.py`)

Claude가 한 번에 모든 위반 판단 + 수정 명령 결정. Python이 일괄 실행.

```bash
.venv/bin/python -m src.agents.agent_ai bimsample/SimpleWall.ifc
```

- Claude API 호출: 항상 2번 (판단 + 보고서)
- 비용 / 시간: 낮음 / 빠름
- 결정적 흐름 (디버깅 쉬움)

### 옵션 F: ReAct Tool Use (`agent_ai_react.py`) ⭐ 산업 표준

**Anthropic Tool Use API** 기반. Claude가 도구를 자율적으로 N번 호출.

```bash
.venv/bin/python -m src.agents.agent_ai_react bimsample/SimpleWall.ifc
```

출력 예:
```
👤 User: 이 IFC 파일을 한국 화재 안전 표준으로 검사하고 수정해줘

💬 Claude: 알겠습니다! 먼저 벽 목록을 확인하겠습니다.
🔧 list_walls()
   ← {total_walls: 1, walls: [...]}

💬 Claude: 외벽 1개에서 3가지 위반 발견:
   - 두께 200mm (기준 500mm 미달)
   - FireRating 비표준
   - 자재 미지정
   동시에 수정합니다.
🔧 fix_thickness(guid='...', thickness_mm=500)
   ← success
🔧 fix_firerating(guid='...', rating='2HR')
   ← success
🔧 fix_material(guid='...', material_name='Concrete', color_rgb=[1,0,0])
   ← success

💬 Claude: 저장합니다.
🔧 save_ifc(output_path='samples/SimpleWall_fixed.ifc')
   ← success

📊 Claude API 호출: 4번 / 도구 호출: 5번
```

**도구 (Claude가 자율적으로 호출):**
- `list_walls()` — 벽 목록 + 속성 반환
- `fix_thickness(guid, thickness_mm)` — 두께 변경
- `fix_firerating(guid, rating)` — FireRating Pset 설정
- `fix_material(guid, material_name, color_rgb)` — 자재 + RGB 색깔
- `save_ifc(output_path)` — IFC 저장

이게 ChatGPT, Claude Code, Cursor 등이 사용하는 **표준 ReAct Agentic 패턴**.

---

## 🔌 MCP 서버 (Model Context Protocol)

BIMHarness를 Claude Desktop, Cursor 등 표준 AI 클라이언트에서 호출할 수 있습니다.

```bash
# MCP 서버 실행 (stdio)
.venv/bin/python -m src.mcp_server

# MCP Inspector로 도구 테스트
npx @modelcontextprotocol/inspector .venv/bin/python -m src.mcp_server
```

노출된 도구 9개:
| 도구 | 설명 |
|------|------|
| `list_rules` | 자연어 룰셋에서 룰 목록 추출 |
| `compile_rules` | 자연어 룰 → JSON 컴파일 (claude/ollama/mock 백엔드) |
| `check_ollama` | 온프레미스 로컬 LLM 상태 + 설치 모델 확인 |
| `validate_ifc` | IFC를 컴파일된 룰셋으로 검증 |
| `apply_fixes` | 위반 사항 자동 수정 |
| `generate_report` | 한국어 보고서 생성 |
| `run_full_pipeline` | 전체 파이프라인 한 번에 실행 |
| `ai_agent_mode` | AI Agent (옵션 E) — 1-shot Batch |
| `ai_react_agent` | ReAct AI Agent (옵션 F) — Claude가 도구 자율 호출 |

### Claude Desktop 등록 (선택)

`claude_desktop_config.json`에 추가:
```json
{
  "mcpServers": {
    "bimharness": {
      "command": "/path/to/BIMHarness/.venv/bin/python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/path/to/BIMHarness",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

등록 후 Claude Desktop 채팅창에서 자연어로 호출:
> "samples/SimpleWall.ifc를 화재 안전 룰로 검사하고 수정해줘"

---

## 🔒 온프레미스 모드 (로컬 LLM · Ollama)

설계 데이터(IFC)와 사내 룰을 **클라우드로 보낼 수 없는 보안 환경**을 위해,
룰 컴파일 LLM을 로컬 Ollama로 전환할 수 있습니다. 출력 JSON 스키마는 동일 —
검증·수정·보고 파이프라인은 그대로 재사용됩니다.

```bash
# 1. 로컬 LLM 준비 (한 번만)
ollama serve &
ollama pull llama3.1

# 2. 클라우드 대신 로컬 모델로 룰 컴파일
.venv/bin/python -m src.main bimsample/SimpleWall.ifc \
  --rules bimsample/rules/core/fire_safety.md --ollama

# 모델 지정도 가능
.venv/bin/python -m src.agents.agent_2_interpreter \
  --rules bimsample/rules/core/fire_safety.md --ollama --model qwen2.5
```

백엔드 비교:

| 백엔드 | 호출 | 데이터 경로 | 용도 |
|--------|------|------------|------|
| `claude` (기본) | Anthropic API | 클라우드 | 고품질 컴파일 |
| `ollama` | `localhost:11434` | **사내망 내부** | 보안·비용·자율성 |
| `mock` | 없음 | 로컬 | 테스트 (API 키 불필요) |

MCP에서도 동일하게 호출:
> "이 룰을 **로컬 모델로** 컴파일해줘" → `compile_rules(backend="ollama")`
> "로컬 LLM 켜져 있어?" → `check_ollama` (서버 상태 + 설치 모델 목록)

> 구현: 백엔드는 `agent_2_interpreter.compile_rule_via_*`로 추상화돼 있고,
> 모든 백엔드가 같은 `SYSTEM_PROMPT`·출력 스키마를 공유합니다. HTTP는 stdlib(`urllib`)만 사용 — 추가 의존성 없음.

---

## 📂 폴더 구조

```
BIMHarness/
├── src/
│   ├── agents/
│   │   ├── agent_1_parser.py        # IFC → JSON 파싱
│   │   ├── agent_2_interpreter.py   # 자연어 룰 → JSON (Claude API)
│   │   ├── agent_3_validator.py     # JSON 룰 검증
│   │   ├── agent_4_autofix.py       # 화이트리스트 자동 수정
│   │   ├── agent_5_reporter.py      # 한국어 보고서 생성
│   │   ├── agent_ai.py              # AI Agent (옵션 E) — 1-shot Batch
│   │   └── agent_ai_react.py        # ReAct AI Agent (옵션 F) — Tool Use API
│   ├── utils/
│   │   ├── env_loader.py            # .env 자동 로드
│   │   └── compare_ifc.py           # 원본/수정 비교
│   ├── main.py                      # 통합 파이프라인
│   └── mcp_server.py                # MCP 서버 (Claude Desktop/Cursor 연동)
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
- [x] Mark 2: Ollama 로컬 LLM (on-premise, 사내 보안) — `--ollama` 백엔드 스위치
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
