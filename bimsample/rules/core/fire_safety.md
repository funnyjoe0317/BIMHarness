# 🔥 Fire Safety Pack — 화재 안전 룰셋

> BIMHarness Core Pack
> 한국 건축법 + 소방법 화재 관련 통합 검증
> 작성: 2026-05-16

---

## 📚 적용 법규

```
건축법 시행령 제46조 (방화구획)
건축물의 피난·방화구조 등의 기준에 관한 규칙 (제3조, 제8조, 제15조)
화재예방, 소방시설 설치·유지 및 안전관리에 관한 법률
소방시설법 시행규칙
NFPA (National Fire Protection Association) 글로벌 참조
```

---

## 🎯 사용 시나리오

```
1. 한국 건축사가 화재 검토 자동화
2. 소방감리 사전 검증
3. 시공사 BIM 매니저 자가 검수
4. 인허가 전 자동 사전 검토

→ 1주일 → 5분 자동화
```

---

# 📋 룰 10개

## R_F1. 방화구획 (Compartmentation)

- **id**: R_F1
- **category**: 한국 건축법
- **target**: IfcBuildingStorey
- **filter**: all
- **condition**: 층 면적 ≤ 1500m²
- **severity**: High
- **auto_fix**: 불가 (방화벽 추가 = 형상 변경, 인간 판단)
- **reference**: 건축법 시행령 제46조

### 설명
주요구조부가 내화구조로 된 건축물로서 연면적 1,000m² 초과 시
방화구획으로 구획해야 한다. 본 룰은 단순화를 위해 1,500m² 기준.

### 검증 로직 힌트
- 각 IfcBuildingStorey의 슬래브 면적 합 계산
- Pset BaseQuantities.GrossFloorArea 활용
- 또는 IfcSpace.NetFloorArea 합

---

## R_F2. 비상계단 너비

- **id**: R_F2
- **category**: 한국 건축법
- **target**: IfcStair
- **filter**: PredefinedType == "FIRE_EXIT" 또는 Name contains "비상"/"emergency"
- **condition**: NominalWidth ≥ 1200mm
- **severity**: High
- **auto_fix**: 가능 (Width 변경)
- **reference**: 건축물 피난·방화구조 등의 기준 규칙 제15조

### 설명
직통계단(돌음계단 포함)의 유효너비는 1.2m 이상이어야 한다.
비상계단은 반드시 1,200mm 이상.

### 검증 로직 힌트
- IfcStair.NominalWidth 속성 확인
- 없으면 Pset_StairCommon.NominalWidth 확인

---

## R_F3. 화재등급 (FireRating) 누락

- **id**: R_F3
- **category**: 한국 소방법
- **target**: IfcWall
- **filter**: Pset_WallCommon.LoadBearing == true 또는 IsExternal == true
- **condition**: Pset_WallCommon.FireRating 값이 유효
- **severity**: Medium
- **auto_fix**: 가능 (기본값 "2HR")
- **reference**: 건축물의 피난·방화구조 등의 기준 규칙 제3조

### 설명
내력벽 및 외벽은 화재 저항 등급 정보 필수.
플레이스홀더("_FIRE-RATING_")나 빈 문자열은 누락으로 간주.
유효값 패턴: "1HR", "2HR", "3HR", "60min", "120min"

### 검증 로직 힌트
- check.type: pset_value_valid
- pset: Pset_WallCommon
- field: FireRating
- invalid_values: [null, "", "_FIRE-RATING_", "TBD"]

---

## R_F4. 비상등 간격

- **id**: R_F4
- **category**: 소방법
- **target**: IfcDistributionElement
- **filter**: PredefinedType == "EMERGENCY_LIGHT" 또는 Name contains "비상등"
- **condition**: 인접 비상등 간격 ≤ 10m
- **severity**: High
- **auto_fix**: 불가 (배치 = 인간 판단)
- **reference**: 소방시설법 시행규칙

### 설명
복도/통로의 비상등은 10m 이내 간격으로 배치.
화재 시 어두운 환경에서 피난 경로 확보.

### 검증 로직 힌트
- 비상등 GUID 별 좌표 수집
- 최근접 비상등과의 거리 계산
- 같은 층/공간에서만 비교

---

## R_F5. 스프링클러 커버리지

- **id**: R_F5
- **category**: 소방법
- **target**: IfcSpace
- **filter**: NetFloorArea > 20m² (소형 공간 제외)
- **condition**: 스프링클러 1개당 커버 면적 ≤ 20m²
- **severity**: High
- **auto_fix**: 불가
- **reference**: 소방시설법 (스프링클러설비의 화재안전기준)

### 설명
스프링클러 1개가 커버해야 하는 면적은 최대 20m².
사무실/거실 공간 모두 적용.

### 검증 로직 힌트
- IfcSpace의 면적 / 포함된 스프링클러 수
- 스프링클러: IfcFlowTerminal (PredefinedType=SPRINKLER)

---

## R_F6. 화재경보기 배치

- **id**: R_F6
- **category**: 소방법
- **target**: IfcSpace
- **filter**: Type in [OFFICE, MEETING_ROOM, LIVING_ROOM]
- **condition**: 공간 내 화재경보기 ≥ 1개 존재
- **severity**: High
- **auto_fix**: 제안만 (배치 위치는 인간 판단)
- **reference**: 자동화재탐지설비의 화재안전기준

### 설명
사무실, 거실, 회의실 등 사람 활동 공간은 화재경보기 필수.

---

## R_F7. 피난거리 (Exit Distance)

- **id**: R_F7
- **category**: 한국 건축법
- **target**: IfcSpace
- **filter**: 거실 (Living, Office)
- **condition**: 가장 가까운 비상구까지 거리 ≤ 30m
- **severity**: High
- **auto_fix**: 불가
- **reference**: 피난·방화구조 등의 기준 규칙 제8조

### 설명
거실에서 비상구까지 보행 거리는 30m 이내.
스프링클러 설치 시 50m까지 완화 가능.

### 검증 로직 힌트
- IfcSpace 중심 ↔ IfcDoor (EXIT) 직선 거리
- 정확하려면 경로 탐색 알고리즘 필요 (Phase 2)
- 단순 검사: 직선 거리만

---

## R_F8. 방화문 자동 닫힘

- **id**: R_F8
- **category**: 한국 건축법
- **target**: IfcDoor
- **filter**: 방화구획 경계 (FireRating 존재)
- **condition**: Pset_DoorCommon.SelfClosing == true
- **severity**: High
- **auto_fix**: 가능 (true로 설정)
- **reference**: 건축물의 피난·방화구조 규칙

### 설명
방화구획에 설치되는 방화문은 자동 닫힘 장치 필수.
화재 시 자동으로 닫혀야 함.

### 검증 로직 힌트
- check.type: pset_value
- pset: Pset_DoorCommon
- field: SelfClosing
- operator: equals
- value: true
- fix.value: true

---

## R_F9. 외벽 자재 (불연) — 자동 자재 변경 + 색깔

- **id**: R_F9
- **category**: 화재 안전 자재
- **target**: IfcWall
- **filter**: Pset_WallCommon.IsExternal == true
- **condition**: material in ["Concrete", "Brick", "Steel", "콘크리트", "벽돌", "철골"]
- **severity**: Medium
- **auto_fix**: 가능 (자재명을 "Concrete"로 + 회색 RGB 설정) ⭐ 시각 변화
- **reference**: 건축법 시행령 제61조

### 설명
외벽은 불연성/준불연성 재료 사용.
샌드위치 패널 등 가연성 자재 외벽 X.
(2019년 의정부 화재 이후 강화)

자동 수정: 비표준 자재 → "Concrete"로 변경 + 콘크리트 회색
(시각적 변화: Navisworks 3D 뷰에서 색깔 바뀜)

### 검증 로직 힌트
- check.type: material_in
- check.value: ["Concrete", "Brick", "Steel", "콘크리트", "벽돌", "철골"]
- fix.type: set_material
- fix.value: "Concrete"
- fix.color: [0.6, 0.6, 0.6]  ← 회색 RGB

---

## R_F11. 외벽 두께 (내화 구조) — 형상 변경 ⭐

- **id**: R_F11
- **category**: 화재 안전 + 구조
- **target**: IfcWall
- **filter**: Pset_WallCommon.IsExternal == true
- **condition**: 외벽 두께 ≥ 200mm
- **severity**: High
- **auto_fix**: 가능 (200mm 미만이면 250mm로 자동 변경) ⭐ 형상 변경!
- **reference**: 건축법 시행령 제57조 (내화구조)

### 설명
2시간 내화 외벽 = 콘크리트 두께 200mm 이상.
얇은 외벽은 화재 시 빠르게 붕괴 위험.

자동 수정: 두께 < 200mm → 250mm로 자동 조정
(시각적 변화: 3D 뷰에서 진짜 두꺼워짐)

### 검증 로직 힌트
- check.type: geometry_dim
- check.field: thickness (또는 width)
- check.operator: gte
- check.value: 200
- fix.type: set_geometry
- fix.field: thickness
- fix.value: 250

---

## R_F10. 비상구 폭

- **id**: R_F10
- **category**: 한국 건축법
- **target**: IfcDoor
- **filter**: PredefinedType == "FIRE_EXIT" 또는 Name contains "비상구"
- **condition**: OverallWidth ≥ 900mm
- **severity**: High
- **auto_fix**: 가능 (900mm로 조정)
- **reference**: 피난·방화구조 등의 기준 규칙

### 설명
비상구/출구의 폭은 900mm 이상.
대피 시 한 사람이 통과 가능한 최소 폭.

### 검증 로직 힌트
- check.type: geometry_dim
- field: OverallWidth
- operator: gte
- value: 900

---

# 📊 룰셋 요약

| ID | 룰 | 자동 수정 | 심각도 | 출처 |
|---|---|:---:|:---:|---|
| R_F1 | 방화구획 (1500m²) | ❌ | 🔴 | 시행령 46조 |
| R_F2 | 비상계단 너비 (1200mm) | ✅ | 🔴 | 규칙 15조 |
| R_F3 | 화재등급 누락 | ✅ | 🟡 | 규칙 3조 |
| R_F4 | 비상등 간격 (10m) | ❌ | 🔴 | 소방법 |
| R_F5 | 스프링클러 (20m²) | ❌ | 🔴 | 소방법 |
| R_F6 | 화재경보기 | △ | 🔴 | 화재안전기준 |
| R_F7 | 피난거리 (30m) | ❌ | 🔴 | 규칙 8조 |
| R_F8 | 방화문 자동 닫힘 | ✅ | 🔴 | 피난·방화 규칙 |
| R_F9 | 외벽 불연 자재 | △ | 🟡 | 시행령 61조 |
| R_F10 | 비상구 폭 (900mm) | ✅ | 🔴 | 피난·방화 규칙 |

자동 수정 가능: 4건
제안만: 2건
검출만 (인간 판단): 4건

---

# 🎬 영상 시연

```
"한국 건축사가 화재 검토 자동화"

1. 빌딩 IFC 입력
2. Fire Safety Pack 적용
3. 10개 룰 자동 검사
4. 결과:
   - 방화구획 위반 1건 (5층 1820m²)
   - 비상계단 1100mm → 1200mm 자동 수정
   - 화재등급 누락 87건 → "2HR" 자동 수정
   - 피난거리 위반 3건 (인간 검토)
5. 한국 소방법 자동 보고서

→ "소방감리 사전 통과율 70% → 95%"
```
