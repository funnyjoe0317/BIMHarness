# 한국 건축법 룰 (BIMHarness MVP)

> 5개 핵심 룰. Agent 2가 이걸 자연어 그대로 읽어서 코드로 해석.
> 추가하려면 같은 형식으로 새 섹션 작성.

---

## R1. 방화구획

- **id**: R1
- **category**: 한국 건축법
- **target**: IfcBuildingStorey
- **filter**: all
- **condition**: 층 면적 ≤ 1500m²
- **severity**: High
- **auto_fix**: 가능 (방화벽 추가)
- **reference**: 건축법 시행령 제46조

### 설명
주요구조부가 내화구조로 된 건축물로서 연면적이 1,000m²를 넘는 것은
방화구획으로 구획하여야 한다. 본 룰에서는 단순화를 위해 층당 1,500m²
기준으로 검사한다.

### 검증 로직 힌트
- 각 IfcBuildingStorey에 포함된 IfcSlab들의 면적 합 계산
- 또는 IfcSpace 면적 합으로 대체 가능
- Pset `BaseQuantities.GrossFloorArea` 활용

---

## R2. 비상계단 너비

- **id**: R2
- **category**: 한국 건축법
- **target**: IfcStair
- **filter**: PredefinedType == "FIRE_EXIT" 또는 Name contains "비상"/"emergency"
- **condition**: NominalWidth ≥ 1200mm
- **severity**: High
- **auto_fix**: 가능 (Width 변경)
- **reference**: 건축물 피난·방화구조 등의 기준에 관한 규칙 제15조

### 설명
직통계단(돌음계단 포함)의 유효너비는 1.2m 이상이어야 한다.
비상계단은 반드시 1,200mm 이상.

### 검증 로직 힌트
- IfcStair.NominalWidth 속성 확인
- 없으면 Pset_StairCommon.NominalWidth 확인
- 그것도 없으면 BaseQuantities에서 너비 계산

---

## R3. 화재등급 (FireRating) 누락

- **id**: R3
- **category**: 한국 소방법
- **target**: IfcWall
- **filter**: Pset_WallCommon.LoadBearing == true 또는 IsExternal == true
- **condition**: Pset_WallCommon.FireRating 값이 유효 (빈값/_FIRE-RATING_ 같은 플레이스홀더 X)
- **severity**: Medium
- **auto_fix**: 가능 (기본값 "2HR" 추가)
- **reference**: 건축물의 피난·방화구조 등의 기준에 관한 규칙 제3조

### 설명
내력벽 및 외벽은 화재 저항 등급(Fire Rating) 정보가 필수.
플레이스홀더(`_FIRE-RATING_`)나 빈 문자열은 누락으로 간주.

### 검증 로직 힌트
- Pset_WallCommon["FireRating"] 추출
- 유효값 패턴: "1HR", "2HR", "3HR", "60min", "120min" 등
- 무효값: None, "", "_FIRE-RATING_", "TBD"

---

## R4. 외벽 자재 표준

- **id**: R4
- **category**: 사내 표준
- **target**: IfcWall
- **filter**: Pset_WallCommon.IsExternal == true
- **condition**: material in ["Concrete", "Brick", "Steel", "콘크리트", "벽돌", "철골"]
- **severity**: Low
- **auto_fix**: 제안만 (자재 변경은 구조 영향)
- **reference**: 사내 시공 표준 v2026

### 설명
외벽은 승인된 자재 목록 중에서 선택해야 한다.
승인되지 않은 자재는 검토 필요.

### 검증 로직 힌트
- _get_material_name() 결과 확인
- 부분 문자열 매칭 OK (예: "Basic Wall:Bearing Wall" → 매칭 실패)

---

## R5. 회의실 최소 면적

- **id**: R5
- **category**: 사내 표준
- **target**: IfcSpace
- **filter**: LongName contains "회의실"/"meeting" 또는 PredefinedType == "MEETING"
- **condition**: 면적 ≥ 6m²
- **severity**: Low
- **auto_fix**: 불가 (공간 재배치 필요)
- **reference**: 사내 공간 표준

### 설명
회의실은 최소 6m² 이상이어야 한다. 그 이하는 협의 부스로 분류.

### 검증 로직 힌트
- Pset.BaseQuantities.NetFloorArea
- 또는 Pset.Qto_SpaceBaseQuantities.GrossFloorArea
- 단위 확인 (m² vs mm²)

---

## R6. 한국어 자재 라벨

- **id**: R6
- **category**: 사내 표준 (다국어)
- **target**: IfcWall
- **filter**: all
- **condition**: Pset_KoreanLocalization.MaterialKR 값이 유효
- **severity**: Low
- **auto_fix**: 가능 (기본값 "콘크리트")
- **reference**: 사내 다국어 표준 v2026

### 설명
한국 사용자/유지보수 인력을 위해 한국어 자재 라벨 필수.
"Concrete" 등 영문만 있으면 한국 작업자가 이해 어려움.

### 검증 로직 힌트
- check.type: pset_value_valid
- pset: Pset_KoreanLocalization
- field: MaterialKR
- 무효값: None, ""
- fix.type: pset_set_value
- fix.value: "콘크리트"

---

## R7. 비용 단가 (BOM)

- **id**: R7
- **category**: 사내 표준 (물량 산출)
- **target**: IfcWall
- **filter**: all
- **condition**: Pset_Cost.UnitCostPerM2 값이 유효
- **severity**: Low
- **auto_fix**: 가능 (기본값 150000)
- **reference**: 사내 BOM/적산 표준

### 설명
자동 견적 + 물량 산출(BOM)을 위해 단가 정보 필수.
단위: KRW/m² (원/제곱미터).

### 검증 로직 힌트
- check.type: pset_value_valid
- pset: Pset_Cost
- field: UnitCostPerM2
- fix.value: 150000

---

## R8. Uniclass 분류 코드

- **id**: R8
- **category**: 글로벌 표준 (분류)
- **target**: IfcWall
- **filter**: all
- **condition**: Pset_Classification.UniclassCode 값이 유효
- **severity**: Low
- **auto_fix**: 가능 (기본값 "Ss_25_10_20")
- **reference**: Uniclass 2015 (NBS UK)

### 설명
영국 NBS Uniclass 2015는 BIM 객체 글로벌 분류 표준.
Ss_25_10_20 = Wall systems > Concrete > Reinforced (예).

### 검증 로직 힌트
- check.type: pset_value_valid
- pset: Pset_Classification
- field: UniclassCode
- fix.value: "Ss_25_10_20"

---

## 추가 룰 작성 가이드

새 룰 추가 시 아래 형식 따를 것:

```markdown
## R{번호}. {제목}

- **id**: R{번호}
- **category**: {한국 건축법 / 사내 표준 / 프로젝트 룰}
- **target**: {IfcWall / IfcDoor / IfcSlab / ...}
- **filter**: {조건 또는 "all"}
- **condition**: {검사 조건 자연어}
- **severity**: {Low / Medium / High}
- **auto_fix**: {가능 / 제안만 / 불가}
- **reference**: {법 조항 또는 표준 명}

### 설명
{왜 이 룰이 필요한지}

### 검증 로직 힌트
{Agent 2가 코드 만들 때 참고할 힌트}
```

---

## 정책

### 화이트리스트 (auto_fix 가능)
- 속성/메타데이터 추가 (Pset)
- 자재 이름 변경
- 단순 치수 변경 (벽 두께, 계단 너비)

### 제안만 (auto_fix 불가)
- 새 요소 추가 (방화벽 신설)
- 객체 삭제
- 공간 재배치
- 곡선/자유 형상 수정

### 절대 X
- 구조 부재 위치 변경
- 사용자 승인 없는 GUID 변경
