"""
BIMHarness 메인 파이프라인
Agent 1 → 2 → 3 → 4 → 5 통합

입력: ifc 파일 + rules.md
출력: fixed.ifc + report.md + changes.log

사용:
  # 전체 파이프라인
  python -m src.main samples/SimpleWall.ifc

  # Mock 모드 (API 키 없이)
  python -m src.main samples/SimpleWall.ifc --mock

  # 룰 컴파일 건너뛰기 (이미 컴파일된 게 있으면)
  python -m src.main samples/SimpleWall.ifc --skip-compile
"""

import sys
from pathlib import Path

# .env 자동 로드 (다른 import 전에)
from .utils.env_loader import load_env, check_api_key
load_env()

from .agents import agent_2_interpreter, agent_3_validator
from .agents import agent_4_autofix, agent_5_reporter


def run_pipeline(
    ifc_path: str,
    rules_md_path: str = "samples/rules_korean_law.md",
    output_dir: str = "samples",
    mock: bool = False,
    skip_compile: bool = False,
    backend: str = "claude",
    model: str = None,
) -> dict:
    """전체 BIMHarness 파이프라인

    backend: 룰 컴파일 LLM — "claude"(클라우드) | "ollama"(온프레미스) | "mock"
    """
    if mock:
        backend = "mock"
    backend_label = {
        "claude": "REAL API (Anthropic 클라우드)",
        "ollama": "온프레미스 (Ollama 로컬)",
        "mock": "MOCK",
    }.get(backend, backend)
    print("\n" + "█" * 60)
    print(f"  BIMHarness — BIM 자동 검증·수정 시스템")
    print(f"  입력 IFC: {ifc_path}")
    print(f"  룰 파일: {rules_md_path}")
    print(f"  컴파일 백엔드: {backend_label}")
    print("█" * 60)

    # 경로 설정
    rules_compiled_path = f"{output_dir}/rules_compiled.json"
    violations_path = f"{output_dir}/violations.json"
    base = Path(ifc_path).stem
    fixed_ifc_path = f"{output_dir}/{base}_fixed.ifc"
    changes_log_path = f"{output_dir}/changes.log.json"
    report_path = f"{output_dir}/report.md"

    # ============================================
    # Phase 1: Agent 2 (룰 컴파일)
    # ============================================
    if skip_compile and Path(rules_compiled_path).exists():
        print(f"\n⏩ Agent 2 건너뜀 (이미 {rules_compiled_path} 있음)")
    else:
        print("\n" + "─" * 60)
        print("Phase 1/4: 룰 컴파일 (Agent 2)")
        print("─" * 60)
        agent_2_interpreter.compile_all(
            rules_md_path=rules_md_path,
            output_path=rules_compiled_path,
            backend=backend,
            model=model,
        )

    # ============================================
    # Phase 2: Agent 1 + 3 (파싱 + 검증)
    # ============================================
    print("\n" + "─" * 60)
    print("Phase 2/4: IFC 파싱 + 검증 (Agent 1 + 3)")
    print("─" * 60)
    validation_result = agent_3_validator.run(
        ifc_path=ifc_path,
        rules_compiled_path=rules_compiled_path,
        output_path=violations_path,
    )

    # ============================================
    # Phase 3: Agent 4 (자동 수정)
    # ============================================
    print("\n" + "─" * 60)
    print("Phase 3/4: 자동 수정 (Agent 4)")
    print("─" * 60)
    if validation_result["total_violations"] == 0:
        print("⚪ 위반 없음 → Agent 4 건너뜀")
        changes_log = {
            "auto_fixed": 0,
            "skipped": 0,
            "changes": [],
            "skipped_violations": [],
        }
    else:
        changes_log = agent_4_autofix.run(
            ifc_path=ifc_path,
            violations_path=violations_path,
            output_ifc_path=fixed_ifc_path,
            changes_log_path=changes_log_path,
        )

    # ============================================
    # Phase 4: Agent 5 (보고서)
    # ============================================
    print("\n" + "─" * 60)
    print("Phase 4/4: 보고서 생성 (Agent 5)")
    print("─" * 60)
    if validation_result["total_violations"] == 0:
        # 빈 보고서라도 생성
        from pathlib import Path as _P
        _P(changes_log_path).write_text(
            '{"auto_fixed": 0, "skipped": 0, "changes": [], '
            '"skipped_violations": []}',
            encoding="utf-8"
        )

    agent_5_reporter.run(
        ifc_path=ifc_path,
        violations_path=violations_path,
        changes_log_path=changes_log_path,
        output_path=report_path,
    )

    # ============================================
    # 최종 요약
    # ============================================
    print("\n" + "█" * 60)
    print("  ✅ BIMHarness 파이프라인 완료")
    print("█" * 60)
    print(f"\n📁 결과 파일:")
    print(f"  - 컴파일된 룰: {rules_compiled_path}")
    print(f"  - 위반 사항: {violations_path}")
    if validation_result["total_violations"] > 0:
        print(f"  - 수정된 IFC: {fixed_ifc_path}")
        print(f"  - 변경 로그: {changes_log_path}")
    print(f"  - 보고서: {report_path}")
    print()

    return {
        "ifc_path": ifc_path,
        "validation": validation_result,
        "changes_log": changes_log,
        "files": {
            "rules_compiled": rules_compiled_path,
            "violations": violations_path,
            "fixed_ifc": fixed_ifc_path,
            "changes_log": changes_log_path,
            "report": report_path,
        }
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    mock = "--mock" in args
    skip_compile = "--skip-compile" in args

    # 컴파일 백엔드: --ollama | --backend <name>
    backend = "claude"
    if "--ollama" in args:
        backend = "ollama"
    if "--backend" in args:
        i = args.index("--backend")
        if i + 1 < len(args):
            backend = args[i + 1]
    model = None
    if "--model" in args:
        i = args.index("--model")
        if i + 1 < len(args):
            model = args[i + 1]

    # --rules <경로> 옵션 처리
    rules_md_path = "samples/rules_korean_law.md"
    if "--rules" in args:
        idx = args.index("--rules")
        if idx + 1 < len(args):
            rules_md_path = args[idx + 1]

    # IFC 경로 (--로 시작하지 않는 첫 인자, --rules의 값 제외)
    # 값을 받는 플래그들 (다음 인자를 IFC 경로로 오인하지 않게 건너뜀)
    value_flags = {"--rules", "--backend", "--model"}
    skip_next = False
    ifc_args = []
    for a in args:
        if skip_next:
            skip_next = False
            continue
        if a in value_flags:
            skip_next = True
            continue
        if not a.startswith("--"):
            ifc_args.append(a)
    ifc_path = ifc_args[0] if ifc_args else "samples/SimpleWall.ifc"

    run_pipeline(
        ifc_path=ifc_path,
        rules_md_path=rules_md_path,
        mock=mock,
        skip_compile=skip_compile,
        backend=backend,
        model=model,
    )
