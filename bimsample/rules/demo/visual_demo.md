# Visual Demo Pack — 시각 변화 데모용 룰셋

> 목적: BIMHarness 시연 영상용. 실제 법규가 아니라 **시각 임팩트**를 위한 데모 룰.
> 외벽을 두껍게 + 높게 + 빨갛게 만들어 AI가 BIM을 수정하는 모습을 한눈에 보여줌.
> ⚠️ 실제 건축 기준 아님. 데모 전용.

---

## D_V1. 외벽 두께 강조 (시각 데모)

- **id**: D_V1
- **category**: 시각 데모
- **target**: IfcWall
- **filter**: Pset_WallCommon.IsExternal == true
- **condition**: 두께 1000mm 이상
- **severity**: High
- **auto_fix**: 가능 (두께 1000mm로 변경)
- **reference**: 데모 전용 (실제 기준 아님)

### 설명
외벽을 1000mm(1m)로 두껍게 만들어 3D 뷰에서 두께 변화를 명확히 보이게 함.

### 검증 로직 힌트
- check.type: geometry_dim
- check.field: thickness
- check.operator: gte
- check.value: 1000
- fix.type: set_geometry
- fix.field: thickness
- fix.value: 1000

---

## D_V2. 외벽 높이 강조 (시각 데모)

- **id**: D_V2
- **category**: 시각 데모
- **target**: IfcWall
- **filter**: Pset_WallCommon.IsExternal == true
- **condition**: 높이 6000mm 이상
- **severity**: High
- **auto_fix**: 가능 (높이 6000mm로 변경)
- **reference**: 데모 전용 (실제 기준 아님)

### 설명
외벽 높이를 6m로 높여 3D 뷰에서 벽이 확 높아지는 모습을 보여줌. 시각 임팩트 가장 큼.

### 검증 로직 힌트
- check.type: geometry_dim
- check.field: height
- check.operator: gte
- check.value: 6000
- fix.type: set_geometry
- fix.field: height
- fix.value: 6000

---

## D_V3. 외벽 색상 강조 (시각 데모)

- **id**: D_V3
- **category**: 시각 데모
- **target**: IfcWall
- **filter**: Pset_WallCommon.IsExternal == true
- **condition**: 자재 "Concrete" + 빨간색 표시
- **severity**: Medium
- **auto_fix**: 가능 (자재 Concrete + RGB 빨강)
- **reference**: 데모 전용 (실제 기준 아님)

### 설명
외벽 자재를 Concrete로 바꾸고 빨간색(RGB 1,0,0)을 입혀 수정된 벽을 한눈에 구분.

### 검증 로직 힌트
- check.type: material_in
- check.value: ["Concrete"]
- fix.type: set_material
- fix.value: "Concrete"
- fix.color: [1.0, 0.0, 0.0]
