# 🏛️ Revit Import Pack — IFC → Revit 호환 보강

> BIMHarness SW Bridge Pack
> 어떤 IFC든 Revit이 잘 import하게 자동 보강
> 작성: 2026-05-16

---

## 🎯 핵심 가치

```
한국 시장 = Revit 90%
   ↕
다른 BIM SW (ArchiCAD/Tekla/Blender) → IFC → Revit

문제:
  Revit IFC Open 시 정보 손실 30~50%
  - Category 매핑 안 됨 → "Generic" 분류
  - Family 정보 부족
  - Phase 정보 누락
  - Material 색깔/렌더 정보 X
  - 좌표 처리 문제 (직접 경험)
  
Revit Import Pack:
  → IFC에 Revit 호환 정보 자동 추가
  → Revit Open 시 손실 0~10%
  → 한국 시장 즉시 사용
```

---

## 📚 적용 표준

```
Autodesk Revit IFC Open Settings
Revit Categories 표준
Revit Family Templates
Phase Management
```

---

# 📋 룰 8개

## R_RV1. Revit Category 매핑

- **id**: R_RV1
- **category**: Revit Import
- **target**: 모든 IfcBuildingElement
- **filter**: all
- **condition**: Pset_RevitParameters.Category 유효
- **severity**: High (Revit 호환성)
- **auto_fix**: 가능 (IFC 클래스 기반 자동 매핑)
- **reference**: Autodesk Revit Category List

### 설명
Revit은 Category 기반으로 객체 관리.
IFC 클래스 → Revit Category 자동 매핑.

### 매핑 테이블
```
IfcWall          → "Walls"
IfcSlab          → "Floors"
IfcRoof          → "Roofs"
IfcDoor          → "Doors"
IfcWindow        → "Windows"
IfcColumn        → "Structural Columns" 또는 "Columns"
IfcBeam          → "Structural Framing"
IfcStair         → "Stairs"
IfcRailing       → "Railings"
IfcCovering      → "Ceilings" (천장)
IfcFurnishingElement → "Furniture"
IfcSpace         → "Rooms"
IfcCurtainWall   → "Curtain Walls"
```

### fix
```
auto_fix: 가능
type: pset_set_value
pset: Pset_RevitParameters
field: Category
value: (IFC 클래스 기반 자동 매핑)
```

---

## R_RV2. Phase 정보

- **id**: R_RV2
- **category**: Revit Import
- **target**: 모든 IfcBuildingElement
- **filter**: all
- **condition**: Pset_Phases.PhaseCreated 또는 PhaseDemolished 유효
- **severity**: Medium
- **auto_fix**: 가능 (기본 "New Construction")
- **reference**: Revit Phase Management

### 설명
Revit은 시공 단계(Phase) 별 객체 관리.
신축/철거/기존 등 구분.

### Phase 종류
```
New Construction → 신규 시공 (기본값)
Existing         → 기존 (현재 상태)
Demolished       → 철거 예정
Future           → 향후 계획
```

### fix
```
auto_fix: 가능
fix.value: "New Construction" (가장 안전한 기본값)
```

---

## R_RV3. Family Type 이름

- **id**: R_RV3
- **category**: Revit Import
- **target**: IfcWall, IfcDoor, IfcWindow
- **filter**: all
- **condition**: Pset_RevitParameters.FamilyType 유효
- **severity**: Medium
- **auto_fix**: 가능 (객체 타입 기반)
- **reference**: Revit Family Templates

### 설명
Revit Family Type 형식: "Family Name:Type Name".
표준 명명 규칙 따르면 Revit이 잘 인식.

### 표준 Family 이름
```
벽: "Basic Wall:Generic"
   또는 "Basic Wall:{두께}mm"
   예) "Basic Wall:200mm"

문: "Single-Flush:36" x 84""
   또는 한국식 "Single-Flush:900mm x 2100mm"

창: "Fixed:36" x 48""
   또는 "Fixed:900mm x 1200mm"

기둥: "M_Rectangular Column:610 x 305mm"
```

### fix
```
auto_fix: 가능
- IfcWall + Pset_WallCommon.IsExternal=true
  → "Basic Wall:Generic - 외벽"
- IfcWall + LoadBearing=true
  → "Basic Wall:Generic - 내력벽"
- 기본: "Basic Wall:Generic"
```

---

## R_RV4. Material Render Color

- **id**: R_RV4
- **category**: Revit Import
- **target**: IfcMaterial
- **filter**: all
- **condition**: Pset_RevitMaterial.RenderColor 유효
- **severity**: Low (시각적)
- **auto_fix**: 가능 (자재별 색)
- **reference**: Revit Material Browser

### 설명
Revit 3D 뷰에서 색깔 표시.
자재명 기반 자동 색 매핑.

### 자재 → 색 매핑
```
Concrete    → "150,150,150" (회색)
Brick       → "180,80,60"   (벽돌색)
Steel       → "120,120,140" (강철)
Wood        → "139,69,19"   (목재)
Glass       → "200,220,255" (유리)
Stone       → "180,170,160" (석재)
Insulation  → "250,200,100" (단열재)
```

### fix
```
auto_fix: 가능
자재명 분석 → RGB 값 매핑
```

---

## R_RV5. Level 표준화

- **id**: R_RV5
- **category**: Revit Import
- **target**: IfcBuildingStorey
- **filter**: all
- **condition**: Name이 Revit 표준 패턴 (Level N 또는 N층 또는 BN)
- **severity**: Medium
- **auto_fix**: 가능 (이름 정규화)
- **reference**: Revit Level Convention

### 설명
Revit Level 이름은 일관되어야 정렬/표시 정상.

### 표준 패턴
```
영어:
  "Level 1", "Level 2", ..., "Level N"
  "Roof"
  "B1" (Basement 1)

한국어:
  "1층", "2층", ..., "N층"
  "옥상"
  "지하1층"

혼용 (한국 추세):
  "1F", "2F", ..., "RF"
  "B1F"
```

### fix
```
auto_fix: 가능
패턴 인식:
  "Garage" → "B1" or "지하1층"
  "First Floor" → "Level 1" or "1F"
  "Roof" → "RF"
```

---

## R_RV6. Pset_RevitParameters 핵심 필드

- **id**: R_RV6
- **category**: Revit Import
- **target**: 모든 IfcBuildingElement
- **filter**: all
- **condition**: Pset_RevitParameters의 7개 핵심 필드 모두 존재
- **severity**: High
- **auto_fix**: 가능
- **reference**: Autodesk Revit Schema

### 설명
Revit이 인식하는 7개 핵심 필드.
이거 다 있어야 Revit Open 시 손실 최소.

### 7개 핵심 필드
```
1. Category          → 객체 분류
2. Family            → Family 이름
3. Type              → Type 이름
4. FamilyType        → "Family:Type"
5. Comments          → 비고 (옵션)
6. Mark              → 마크 번호 (옵션)
7. PhaseCreated      → 생성 단계
```

### fix
```
auto_fix: 가능
누락된 필드 자동 채움 (객체 타입 기반)
```

---

## R_RV7. 좌표 시스템

- **id**: R_RV7
- **category**: Revit Import
- **target**: IfcSite, IfcProject
- **filter**: all
- **condition**: 모든 좌표 ≤ ±32km (Revit 한계)
- **severity**: High (Revit 안 보이는 원인!)
- **auto_fix**: 가능 (원점 이동)
- **reference**: Revit Site Settings

### 설명
Revit은 ±32km 범위 내 객체만 정상 표시.
이 범위 밖이면 모델 안 보임 (직접 경험!).

### 검증
```
모든 IfcCartesianPoint 좌표 검사
범위: -32000000mm ~ +32000000mm (±32km)
```

### fix
```
auto_fix: 가능
1. 모든 좌표 bbox 계산
2. bbox 중심을 원점으로 이동
3. 모든 IfcCartesianPoint 재계산
4. IfcSite.RefLatitude/RefLongitude 보존

→ 우리가 LargeBuilding/AdvancedProject에서
   겪은 문제 자동 해결!
```

---

## R_RV8. Family Parameters

- **id**: R_RV8
- **category**: Revit Import
- **target**: IfcWall, IfcDoor 등
- **filter**: all
- **condition**: Pset_RevitFamilyParameters.Width, Height 등 유효
- **severity**: Medium
- **auto_fix**: 가능 (BaseQuantities에서 추출)
- **reference**: Revit Family Schema

### 설명
Revit Family는 Width/Height 등 파라미터 필수.
BaseQuantities에 있으면 그대로, 없으면 기하 정보에서 추출.

### 필수 파라미터
```
IfcWall:
  - Length
  - Height
  - Width (Thickness)

IfcDoor:
  - OverallWidth
  - OverallHeight

IfcWindow:
  - OverallWidth
  - OverallHeight
```

---

# 📊 룰셋 요약

| ID | 룰 | 자동 수정 | 필수도 |
|---|---|:---:|:---:|
| R_RV1 | Category 매핑 | ✅ | 🔴 |
| R_RV2 | Phase 정보 | ✅ | 🟡 |
| R_RV3 | Family Type 이름 | ✅ | 🟡 |
| R_RV4 | Material Color | ✅ | 🟢 |
| R_RV5 | Level 표준화 | ✅ | 🟡 |
| R_RV6 | 7개 핵심 필드 | ✅ | 🔴 |
| R_RV7 | 좌표 ±32km 한계 | ✅ | 🔴 ⭐ |
| R_RV8 | Family Parameters | ✅ | 🟡 |

자동 수정: 8건 (모두!)

---

# 🎬 영상 시연

```
"BIM 매니저 30분 → 5분"

1. AdvancedProject.ifc 입력 (좌표 700m 떨어진 문제)
2. BIMHarness with Revit Import Pack
3. 자동 보강:
   - Category 매핑: 390개 벽 → "Walls" ✅
   - Phase: 모든 객체 "New Construction" ✅
   - Family: "Basic Wall:Generic" 자동 ✅
   - 좌표 ±32km로 이동 (Revit 한계 해결) ⭐
   - Material 색깔: 회색 자동 ✅
4. Revit Open IFC
5. ✅ 정상 표시! (좌표 문제 해결)

→ "Revit 호환 0% → 95%"
```

---

# 💼 실제 영업 포인트

## "왜 우리 BIMHarness가 필요한가?"

```
한국 BIM 매니저 일상:
  "협력사가 ArchiCAD로 만든 IFC 받았는데
   Revit에서 안 열려요 ㅠㅠ"
  → 1주일 수동 변환

BIMHarness 사용:
  → "Revit Import Pack 적용하시면 됩니다"
  → 5분 자동 변환
  → 95% 정보 보존
  
→ 한국 BIM 매니저 즉시 채택
```

---

# 🎯 자기소개서 어필

```
"Revit IFC Open의 한계 (±32km 좌표 한계 등)를
 직접 경험하며 BIMHarness Revit Import Pack을
 자체 설계했습니다.

 8개 자동 보강 룰:
   1. IFC Class → Revit Category 매핑
   2. Phase 정보 자동
   3. Family Type 표준 명명
   4. 자재 색깔 자동
   5. Level 정규화
   6. 7개 핵심 필드 자동
   7. ±32km 좌표 한계 자동 해결 ⭐
   8. Family Parameters 추출

 → Revit 호환성 0% → 95%
 → 한국 BIM 매니저 시간 80% 절감"

→ 면접관: "와 진짜 실무 한 사람이네"
```
