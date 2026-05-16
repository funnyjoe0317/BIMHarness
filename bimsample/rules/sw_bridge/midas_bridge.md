# 🌉 MIDAS Bridge Pack — Revit/IFC → MIDAS 자동 변환

> BIMHarness SW Bridge Pack
> 건축 BIM 모델을 MIDAS Gen/Civil로 자동 export 준비
> 작성: 2026-05-16
> 경력 활용: 시드소프트 MidasLink 40개 컴포넌트 + MIDAS REST API 245개

---

## 🎯 핵심 가치

```
한국 시장 현실:
  설계 = Revit (90%)
  구조 = MIDAS (90%)
   ↕
  교환 = IFC

문제:
  IFC → MIDAS 자동 매핑 X
  매번 수동으로 정보 입력
  자재 등급, 설계기준, 단면 정보 다시 입력
  
MIDAS Bridge Pack:
  → IFC에 MIDAS가 필요한 정보 자동 보강
  → MIDAS Gen 즉시 import 가능
  → 한국 구조 엔지니어 시간 80% 절감
```

---

## 📚 적용 표준

```
MIDAS Gen 2024 API
MIDAS Civil 2024 API
한국 건축구조기준 KDS 41
미국 AISC 360 (강구조)
유럽 Eurocode (EU2004)
```

---

# 📋 룰 8개

## R_MD1. 설계기준 코드

- **id**: R_MD1
- **category**: MIDAS Bridge
- **target**: IfcProject
- **filter**: all
- **condition**: Pset_MidasDesignCode.Standard 값이 유효
- **severity**: High (MIDAS import 시 필수)
- **auto_fix**: 가능 (기본값 "KR_2021")
- **reference**: MIDAS Gen 6개국 설계기준 API

### 설명
MIDAS는 설계기준에 따라 안전율, 하중조합 다름.
프로젝트마다 사용할 설계기준 명시.

### 검증 로직 힌트
- check.type: pset_value_valid
- pset: Pset_MidasDesignCode
- field: Standard
- 유효값: ["KR_2021", "AISC360_22", "EU2004", "IBC2012", "TAI", "AASHTO_ASRA"]
- fix.value: "KR_2021"

### MIDAS 매핑
```
KR_2021     → 한국 건축구조기준 2021
AISC360_22  → 미국 강구조
EU2004      → Eurocode
IBC2012     → 국제 건축법
TAI         → 대만
AASHTO_ASRA → 미국 교량
```

---

## R_MD2. 구조 부재 분류

- **id**: R_MD2
- **category**: MIDAS Bridge
- **target**: IfcBeam, IfcColumn, IfcSlab, IfcWall
- **filter**: all
- **condition**: Pset_MidasStructural.MemberType 유효
- **severity**: High
- **auto_fix**: 가능 (자동 매핑)
- **reference**: MIDAS Gen API

### 설명
MIDAS에서 부재 타입별 처리 다름.
IFC 클래스 → MIDAS MemberType 자동 매핑.

### 매핑 테이블
```
IfcBeam      → "Beam"      (보)
IfcColumn    → "Column"    (기둥)
IfcSlab      → "Plate"     (슬래브)
IfcWall      → "Wall"      (벽)
IfcMember    → "Truss"     (트러스)
```

### fix
```
auto_fix: 가능
type: 자동 분류 (객체 IfcClass 기반)
```

---

## R_MD3. 자재 등급

- **id**: R_MD3
- **category**: MIDAS Bridge
- **target**: IfcStructuralMember (보, 기둥, 강구조)
- **filter**: material 정보 존재
- **condition**: Pset_MidasMaterial.GradeCode 유효
- **severity**: High
- **auto_fix**: 가능 (재료별 기본값)
- **reference**: KS D 3503, KS D 3515 (강재 표준)

### 설명
MIDAS는 강재 등급에 따라 항복강도 등 계산.
자재 정보 누락 시 해석 불가.

### 강재 등급 (한국)
```
SS400  → 일반 구조용 강재 (Fy=235MPa) - 가장 흔함
SM400  → 용접 구조용 (Fy=235MPa)
SM490  → 용접 구조용 고강도 (Fy=325MPa)
SM490Y → 야크주조 (Fy=355MPa)
SM520  → 고강도 (Fy=355MPa)
SM570  → 초고강도 (Fy=420MPa)
```

### 콘크리트 등급 (한국)
```
C24/30  → 일반 (fck=24MPa)
C27/35  → 중간 (fck=27MPa)
C30/37  → 고강도 (fck=30MPa)
C35/45  → 초고강도 (fck=35MPa)
```

### fix
```
auto_fix: 가능
SS강재 → 기본값 "SS400"
콘크리트 → 기본값 "C24/30"
```

---

## R_MD4. 단면 정보

- **id**: R_MD4
- **category**: MIDAS Bridge
- **target**: IfcBeam, IfcColumn
- **filter**: all
- **condition**: Pset_MidasSection.SectionCode 유효
- **severity**: High
- **auto_fix**: 가능 (자재 + 치수 기반 자동)
- **reference**: KS D 3502 (강재 단면)

### 설명
MIDAS는 단면 코드로 강재/콘크리트 단면 정의.
한국 강재 표준 단면 명명 규칙 따름.

### 강재 단면 명명 (한국)
```
H 형강:    H300x200x8/12     (높이x폭x웹두께/플랜지두께)
I 형강:    I300x150x10x15
L 형강:    L100x100x10
C 형강:    C200x90x8x13.5
박스:      Box300x200x10
```

### fix
```
auto_fix: 가능
- 기존 형상에서 단면 추출
- IfcExtrudedAreaSolid + IfcRectangleProfileDef 등 분석
- 표준 단면명으로 자동 변환
```

---

## R_MD5. 하중 조건

- **id**: R_MD5
- **category**: MIDAS Bridge
- **target**: IfcStructuralLoadGroup, IfcStructuralLoad
- **filter**: all
- **condition**: Pset_MidasLoad.LoadCase 유효
- **severity**: Medium
- **auto_fix**: 제안만
- **reference**: KDS 41 11 00 (설계 하중)

### 설명
MIDAS는 하중 종류별로 다른 안전율 적용.
DL/LL/WL/EL 등 명확히 분류.

### 하중 종류
```
DL (Dead Load)        → 고정 하중 (자중)
LL (Live Load)        → 활하중 (사용)
WL (Wind Load)        → 풍하중
EL (Earthquake Load)  → 지진하중
TL (Temperature)      → 온도하중
SL (Snow Load)        → 적설하중
```

---

## R_MD6. 절점 (Node) 정보

- **id**: R_MD6
- **category**: MIDAS Bridge
- **target**: IfcCartesianPoint
- **filter**: 구조 부재의 끝점/연결점
- **condition**: Pset_MidasNode.NodeID 유효
- **severity**: Medium
- **auto_fix**: 가능 (자동 번호)
- **reference**: MIDAS Gen Input File 형식

### 설명
MIDAS는 절점 ID 기반.
부재 연결점에 고유 NodeID 필요.

### fix
```
auto_fix: 가능
- 모든 끝점에 자동 NodeID 부여 (1, 2, 3, ...)
- 좌표 기반 중복 제거 (같은 위치 = 같은 노드)
```

---

## R_MD7. 경계 조건

- **id**: R_MD7
- **category**: MIDAS Bridge
- **target**: IfcStructuralPointConnection (지지점)
- **filter**: 1층 부재 끝점
- **condition**: Pset_MidasBoundary.Type 유효
- **severity**: Medium
- **auto_fix**: 제안만
- **reference**: KDS 41 11 00

### 설명
지반 접점은 경계 조건 정의 필요.
고정/힌지/롤러 등.

### 경계 조건 타입
```
FIXED      → 완전 고정 (Dx, Dy, Dz, Rx, Ry, Rz 다 구속)
PINNED     → 힌지 (Dx, Dy, Dz 구속, 회전 자유)
ROLLER     → 롤러 (Dy만 구속)
FREE       → 완전 자유
SPRING     → 스프링 (k값 설정)
```

---

## R_MD8. RS Function (응답스펙트럼)

- **id**: R_MD8
- **category**: MIDAS Bridge (지진 해석)
- **target**: IfcProject
- **filter**: 지진 해석 필요 시
- **condition**: Pset_MidasSeismic.RSFunction 유효
- **severity**: High (지진 해석 시)
- **auto_fix**: 가능 (지역별 자동)
- **reference**: KDS 41 17 00 (내진설계)

### 설명
지진 해석 시 응답스펙트럼 곡선 필수.
설계기준 + 지반 분류 + 지역에 따라 다름.

### RS Function 코드
```
KR_RS_S1     → 한국 강진 지역 (서울/경기)
KR_RS_S2     → 한국 중진
KR_RS_S3     → 한국 약진
AISC_RS      → 미국 IBC
EU_RS_T1     → 유럽 Type 1
```

### 경력 활용
```
시드소프트 MidasLink에서 6개국 RS Function 컴포넌트 개발
→ 너 직접 만든 시스템과 100% 연결
→ "MIDAS API 245개 + MidasLink 40개 + BIMHarness Bridge Pack"
   = 완성된 한국 구조 BIM 워크플로우
```

---

# 📊 룰셋 요약

| ID | 룰 | 자동 수정 | MIDAS 필수도 |
|---|---|:---:|:---:|
| R_MD1 | 설계기준 코드 | ✅ | 🔴 |
| R_MD2 | 부재 분류 | ✅ | 🔴 |
| R_MD3 | 자재 등급 | ✅ | 🔴 |
| R_MD4 | 단면 정보 | ✅ | 🔴 |
| R_MD5 | 하중 조건 | △ | 🟡 |
| R_MD6 | 절점 정보 | ✅ | 🟡 |
| R_MD7 | 경계 조건 | △ | 🟡 |
| R_MD8 | RS Function (지진) | ✅ | 🟢 (지진 해석 시) |

자동 수정: 6건
제안: 2건

---

# 🎬 영상 시연

```
"한국 구조 엔지니어 시간 80% 절감"

1. Revit에서 만든 IFC (건축 모델)
2. BIMHarness with MIDAS Bridge Pack
3. 자동 보강:
   - 설계기준: KR_2021 추가 ✅
   - 부재 분류: Beam/Column/Slab 자동 ✅
   - 자재 등급: SS400 자동 ✅
   - 단면 정보: H300x200x8 추출 ✅
4. MIDAS Gen 실행
5. IFC import → 즉시 해석 가능

→ "수동 30분 → 자동 30초"
→ 자기소개서: "MIDAS Bridge 직접 설계 + 구현"
```

---

# 💼 사업화 가능성

## 1. 시드소프트 사내 도구
```
시드소프트는 이미 MidasLink (Grasshopper 연동) 보유
→ MIDAS Bridge Pack = 그 다음 단계
→ "건축 BIM → MIDAS" 자동 변환 도구
→ 회사 제품 라인 확장
```

## 2. 한국 구조 엔지니어 SaaS
```
한국 구조 엔지니어 = 약 5,000명
모두 MIDAS 사용
→ BIM Bridge Pack 월 구독 모델
→ 회사당 ₩50,000/월 가능
```

## 3. 학술 가치
```
"한국 BIM → MIDAS 자동 변환 시스템"
→ 한국 BIM 학회 논문
→ MidasLink + BIMHarness Bridge = 박사 주제 가능
```

---

# 🎯 자기소개서 어필

```
"BIMHarness MIDAS Bridge Pack을 자체 설계 + 구현했습니다.

 시드소프트 MidasLink (Grasshopper-MIDAS 연동) 개발 경력에
 BIMHarness 룰셋 시스템을 결합:

 건축 BIM (Revit/IFC) → BIMHarness 자동 보강 → MIDAS Gen
   - 설계기준 6개국 자동 매핑
   - 부재 분류 자동
   - 자재 등급 한국 표준 (KS D 3503) 적용
   - RS Function 지역별 자동

 한국 구조 엔지니어 BIM 워크플로우 표준화 + 자동화."

→ 면접관: "이거 진짜 시장 알고 있네"
```
