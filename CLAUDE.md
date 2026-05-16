# CLAUDE.md — BIMHarness 프로젝트 가이드라인

> Claude Code 자동 로드 파일. 세션 시작 시 자동으로 적용됨.
> 일반 가이드라인 + 우리 프로젝트 특화 규칙 + 실수 학습.

---

## 🚨 새 세션 시작 시 무조건

```
1. PROGRESS.md 읽기 (현재 D-day + 진행 상황)
2. LESSONS.md 읽기 (과거 실수 + 배운 점)
3. 위 둘 기반으로 작업 시작
```

→ **이 두 파일을 안 읽고 시작하면 같은 실수 반복 가능**

---

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

구현 전:
- 가정을 명시. 불확실하면 묻기.
- 여러 해석 가능하면 모두 제시 — 혼자 결정 X
- 더 간단한 방법 있으면 말하기. 필요하면 푸시백.
- 헷갈리는 점 있으면 멈추고 묻기.

### BIMHarness 특화
- IFC 구조 헷갈리면 → `docs/papers/논문_해설.md` 참조
- 룰 형식 헷갈리면 → `samples/rules_korean_law.md` 참조
- Agent 설계 모르겠으면 → `docs/Agent_2_설계.md`

---

## 2. Simplicity First

**문제 해결 최소 코드. 추측 X.**

- 요청 안 한 기능 추가 X
- 1회용 코드에 추상화 X
- "유연성"·"설정 가능"·"확장성" — 요청 안 했으면 X
- 불가능한 시나리오 에러 처리 X
- 200줄 짜리 50줄로 가능하면 다시 쓰기

질문: "시니어 엔지니어가 과설계라 할까?" 예 → 단순화

### BIMHarness 특화
- 12일 MVP — 완벽함보다 동작
- Mock 모드 우선 — 실제 API 호출 최소화
- 화이트리스트 패턴 — 안전 카테고리만 자동 수정

---

## 3. Surgical Changes

**필요한 부분만 수정. 자기 똥만 치우기.**

기존 코드 편집 시:
- 인접 코드/주석/포맷 "개선" 금지
- 안 고장났으면 리팩터링 X
- 기존 스타일 따라가기 — 본인 취향 무관
- 무관한 dead code 발견 시 — 말로 알리고 삭제는 X

본인 변경이 고아 만들면:
- 본인 변경으로 안 쓰이게 된 import/변수/함수 제거
- 기존 dead code는 요청 없으면 건드리지 X

테스트: 모든 변경 줄이 사용자 요청에 직결되나?

### BIMHarness 특화
- src/agents/ 구조 유지 (agent_1~5 + utils)
- 새 기능 추가 시 새 파일 또는 명확한 섹션
- ifcopenshell API 호출은 항상 try/except 안에

---

## 4. Goal-Driven Execution

**성공 기준 정의. 검증까지 루프.**

작업을 검증 가능한 목표로:
- "검증 추가" → "잘못된 입력 테스트 작성 + 통과"
- "버그 수정" → "재현 테스트 작성 + 통과"
- "리팩터링" → "전후 모두 테스트 통과 보장"

다단계 작업은 짧은 계획:
```
1. [단계] → 검증: [체크]
2. [단계] → 검증: [체크]
3. [단계] → 검증: [체크]
```

강한 성공 기준이면 자율 루프 가능.
약한 기준("작동하게 해주세요")은 매번 명확화 필요.

### BIMHarness 특화
- 새 Agent 작성 시: 입력 → 출력 명확히
- IFC 수정 시: 원본 백업 + SHA-256 검증
- 새 룰 추가 시: SimpleWall.ifc로 단위 테스트

---

# 🏗️ BIMHarness 프로젝트 특화 규칙

## 환경

```bash
# 가상환경 사용 (시스템 Python 절대 X)
.venv/bin/python <스크립트>

# 환경변수 자동 로드
.env 파일에 ANTHROPIC_API_KEY 있음
src/utils/env_loader.py가 자동 로드
```

## 폴더 구조

```
src/
  agents/       ← 5 에이전트 (1~5)
  utils/        ← env_loader, compare_ifc
  main.py       ← 통합 진입점

samples/
  *.ifc                    ← IFC 샘플
  rules_korean_law.md      ← 자연어 룰 (사용자 작성)
  rules_compiled.json      ← Agent 2 컴파일 결과 (캐시)
  violations.json          ← Agent 3 검증 결과
  *_fixed.ifc             ← Agent 4 수정 결과
  changes.log.json         ← 변경 로그
  report.md               ← Agent 5 보고서

docs/
  BIMHarness_프로젝트.md  ← 메인 문서
  코드_해설_Agent1.md     ← Agent 1 한 줄 한 줄
  Agent_2_설계.md         ← Agent 2 설계
  papers/                  ← 학습 논문
```

## 코딩 컨벤션

- Python 3.12+, 타입 힌트 권장
- 들여쓰기 4칸 (PEP 8)
- 함수명: snake_case
- private 함수: _underscore_prefix
- Pset/IFC 클래스명: 원본 그대로 (IfcWall, Pset_WallCommon)

## API 호출 규칙

- Claude API 호출은 Agent 2만 (룰 컴파일)
- Agent 3~5는 LLM 호출 X (Python only)
- 비용 절약: `--skip-compile` 활용

## 안전 규칙

- IFC 수정 전 무조건 백업 (Agent 4)
- 화이트리스트만 자동 수정 (pset_set_value, set_attribute)
- SHA-256 해시로 무결성 검증
- 위험 작업: 새 요소 추가/삭제 → 제안만

---

# 📚 참조

- 진행 상황: `PROGRESS.md`
- 실수 학습: `LESSONS.md` ⭐
- 메인 설계: `docs/BIMHarness_프로젝트.md`
- 영상 기획: `docs/유튜브_영상_기획.md`

---

**이 가이드라인이 작동하면:** 불필요한 diff 변경 ↓, 과설계로 인한 재작성 ↓, 명확화 질문이 실수 후가 아닌 구현 전에.
