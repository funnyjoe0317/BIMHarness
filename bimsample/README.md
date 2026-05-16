# 📦 BIMHarness Sample Data

BIMHarness 시연용 IFC 샘플 + 자연어 룰셋.

---

## 📂 폴더 구조

```
bimsample/
├── SimpleWall.ifc          ← 작은 IFC (39KB, 데모용)
├── rules_korean_law.md     ← 한국 건축법 8개 룰
└── rules/
    ├── core/
    │   └── fire_safety.md  ← 화재 안전 11 룰
    └── sw_bridge/
        ├── midas_bridge.md ← MIDAS 호환 8 룰
        └── revit_import.md ← Revit Import 8 룰
```

---

## 🚀 빠른 시작

루트 폴더에서:

```bash
# 1. 기본 룰셋 (한국 건축법 8개)
.venv/bin/python -m src.main bimsample/SimpleWall.ifc \
  --rules bimsample/rules_korean_law.md

# 2. Fire Safety Pack (화재 안전 11개)
.venv/bin/python -m src.main bimsample/SimpleWall.ifc \
  --rules bimsample/rules/core/fire_safety.md

# 3. MIDAS Bridge Pack (구조해석 호환)
.venv/bin/python -m src.main bimsample/SimpleWall.ifc \
  --rules bimsample/rules/sw_bridge/midas_bridge.md
```

---

## 📋 룰셋 카테고리

### 🏛️ Core (도메인 안전)

- **fire_safety.md** — 한국 소방법 + 건축법 화재 11 룰
  - 방화구획, 비상계단 너비, FireRating, 비상등 간격
  - 스프링클러, 화재경보기, 피난거리, 방화문, 외벽 자재 + 색, 비상구 폭, 외벽 두께

### 🔄 SW Bridge (소프트웨어 이동)

- **revit_import.md** — IFC → Revit 호환 보강 (8 룰)
  - Revit Category 매핑, Phase, Family Type 등
  - ±32km 좌표 한계 자동 해결 ⭐

- **midas_bridge.md** — BIM → MIDAS 구조해석 (8 룰)
  - 설계기준 코드, 자재 등급 (SS400 등), 단면 정보
  - 한국 KDS 41 표준

---

## 🎯 새 룰 추가하기

`rules/` 폴더에 `.md` 파일 추가, 형식:

```markdown
## R_X1. 룰 제목

- **id**: R_X1
- **category**: 도메인
- **target**: IfcWall (검사 대상)
- **filter**: 조건
- **condition**: 통과 조건
- **severity**: High/Medium/Low
- **auto_fix**: 가능/제안만/불가
- **reference**: 법 조항 또는 표준

### 설명
왜 이 룰이 필요한지

### 검증 로직 힌트
Agent 2 컴파일러에 줄 힌트
```

---

## 🔬 시연 가능한 변화

`SimpleWall.ifc` 실행 시 (Fire Pack 적용):

```
[수정 전]
  Pset_WallCommon.FireRating: "_FIRE-RATING_" ❌
  벽 자재:                     "Basic Wall:Bearing Wall"
  벽 두께:                     200mm

[수정 후 - SimpleWall_fixed.ifc]
  Pset_WallCommon.FireRating: "2HR" ✅
  벽 자재:                     "Concrete" ✅
  벽 두께:                     250mm ✅ (R_F11 적용 시)
```

→ BIM Vision / Navisworks에서 시각 변화 확인 가능

---

## 📥 추가 IFC 다운로드 (선택)

큰 IFC 샘플은 별도 다운로드:

```bash
# BIM-Whale 저장소 (오픈소스)
curl -L -o bimsample/LargeBuilding.ifc \
  "https://raw.githubusercontent.com/andrewisen/bim-whale-ifc-samples/main/LargeBuilding/IFC/LargeBuilding.ifc"
```

Revit 사용자는 자체 모델 export → `bimsample/`에 두고 사용.

---

## 📚 학술 베이스

이 룰셋 시스템의 학술적 영감:

- **TU 뮌헨 Borrmann 그룹** — Text2BIM (멀티 에이전트)
- **Anthropic MCP 표준** — Model Context Protocol
- **한양대 동문** — .bdna 인코딩 (SSRN #6532559)

---

## 📄 라이선스

MIT License (BIMHarness 본체와 동일)
