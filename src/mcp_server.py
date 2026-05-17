"""BIMHarness MCP 서버

Claude Desktop, MCP Inspector 등 표준 AI 클라이언트에서 BIM 도구 호출.

도구:
  - list_rules(rules_md_path) — 사용 가능한 룰 목록
  - validate_ifc(ifc_path, rules_md_path) — IFC 검증
  - apply_fixes(ifc_path, violations_path) — 자동 수정
  - generate_report(violations_path, changes_path) — 한국어 보고서
  - run_full_pipeline(ifc_path, rules_md_path) — 전체 파이프라인

실행:
  python -m src.mcp_server                              # stdio 서버
  npx @modelcontextprotocol/inspector python -m src.mcp_server  # Inspector
"""

import contextlib
import functools
import io
import json
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# .env 자동 로드
try:
    from src.utils.env_loader import load_env
    load_env()
except ImportError:
    pass

from src.agents.agent_1_parser import parse_ifc
from src.agents.agent_2_interpreter import parse_rules_md, compile_all
from src.agents.agent_3_validator import validate
from src.agents.agent_4_autofix import apply_fixes as run_apply_fixes
from src.agents.agent_5_reporter import generate_report as run_generate_report
from src.agents.agent_ai import run as run_ai_agent
from src.agents.agent_ai_react import run_react_agent


mcp = FastMCP("bimharness")


# ============================================
# stdout 오염 방지
# MCP는 stdout으로 JSON-RPC만 통신해야 함.
# 우리 에이전트들이 사용하는 print()는 stderr로 리다이렉트.
# ============================================

@contextlib.contextmanager
def _silence_stdout():
    """도구 실행 중 stdout 출력을 stderr로 보냄"""
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old_stdout


def silent(func):
    """@mcp.tool() 데코된 함수에 추가로 적용: 내부 print를 stderr로"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with _silence_stdout():
            return func(*args, **kwargs)
    return wrapper


# ============================================
# 도구 1: list_rules
# ============================================

@mcp.tool()
@silent
def list_rules(rules_md_path: str) -> dict:
    """자연어 룰셋 파일에서 룰 목록을 추출합니다.

    Args:
        rules_md_path: 룰 마크다운 파일 경로 (예: bimsample/rules/core/fire_safety.md)

    Returns:
        룰 ID, 제목 목록
    """
    if not Path(rules_md_path).exists():
        return {"error": f"파일 없음: {rules_md_path}"}

    rules = parse_rules_md(rules_md_path)
    return {
        "count": len(rules),
        "rules": [{"id": r["id"], "title": r["title"]} for r in rules],
    }


# ============================================
# 도구 2: validate_ifc
# ============================================

@mcp.tool()
@silent
def validate_ifc(
    ifc_path: str,
    rules_compiled_path: str = "samples/rules_compiled.json",
) -> dict:
    """IFC 파일을 컴파일된 룰셋으로 검증합니다.

    Args:
        ifc_path: 검증할 IFC 파일 경로
        rules_compiled_path: 컴파일된 룰 JSON 경로 (Agent 2 출력)

    Returns:
        총 위반 건수, 룰별 통계, 위반 목록 (요약)
    """
    if not Path(ifc_path).exists():
        return {"error": f"IFC 파일 없음: {ifc_path}"}
    if not Path(rules_compiled_path).exists():
        return {"error": f"룰 파일 없음: {rules_compiled_path}. compile_rules 먼저 실행 필요."}

    parsed = parse_ifc(ifc_path)
    compiled_rules = json.loads(Path(rules_compiled_path).read_text(encoding="utf-8"))
    result = validate(parsed, compiled_rules)

    return {
        "ifc": ifc_path,
        "total_entities": parsed.get("total_entities", 0),
        "walls": len(parsed.get("walls", [])),
        "total_violations": result.get("total_violations", 0),
        "rule_summary": result.get("rule_summary", {}),
        "violations_sample": result.get("violations", [])[:10],
    }


# ============================================
# 도구 3: compile_rules (자연어 → JSON)
# ============================================

@mcp.tool()
@silent
def compile_rules(
    rules_md_path: str,
    output_path: str = "samples/rules_compiled.json",
    mock: bool = False,
) -> dict:
    """자연어 룰(.md)을 JSON으로 컴파일합니다 (Claude API 호출).

    Args:
        rules_md_path: 자연어 룰 마크다운 경로
        output_path: 컴파일 결과 저장 경로
        mock: True면 API 호출 없이 mock 데이터 사용 (테스트용)

    Returns:
        컴파일된 룰 수, 출력 경로
    """
    if not Path(rules_md_path).exists():
        return {"error": f"파일 없음: {rules_md_path}"}

    compiled = compile_all(
        rules_md_path=rules_md_path,
        output_path=output_path,
        mock=mock,
    )

    return {
        "compiled_count": len(compiled),
        "output_path": output_path,
        "rule_ids": [r["id"] for r in compiled],
    }


# ============================================
# 도구 4: apply_fixes (자동 수정)
# ============================================

@mcp.tool()
@silent
def apply_fixes(
    ifc_path: str,
    violations_path: str = "samples/violations.json",
    output_ifc_path: str = None,
    changes_log_path: str = "samples/changes.log.json",
) -> dict:
    """위반 사항을 자동 수정한 IFC를 생성합니다.

    Args:
        ifc_path: 원본 IFC 경로
        violations_path: 위반 사항 JSON (validate_ifc 결과)
        output_ifc_path: 출력 IFC 경로 (기본: {원본}_fixed.ifc)
        changes_log_path: 변경 로그 경로

    Returns:
        수정 성공/실패 수, 출력 파일 경로, SHA-256 해시
    """
    if not Path(ifc_path).exists():
        return {"error": f"IFC 파일 없음: {ifc_path}"}
    if not Path(violations_path).exists():
        return {"error": f"위반 파일 없음: {violations_path}"}

    if output_ifc_path is None:
        base = Path(ifc_path).stem
        output_ifc_path = f"samples/{base}_fixed.ifc"

    log = run_apply_fixes(
        ifc_path=ifc_path,
        violations_path=violations_path,
        output_ifc_path=output_ifc_path,
        changes_log_path=changes_log_path,
    )

    return {
        "output_ifc": output_ifc_path,
        "auto_fixed": log.get("auto_fixed", 0),
        "skipped": log.get("skipped", 0),
        "original_sha256": log.get("original_sha256", "")[:16],
        "fixed_sha256": log.get("fixed_sha256", "")[:16],
    }


# ============================================
# 도구 5: generate_report
# ============================================

@mcp.tool()
@silent
def generate_report(
    violations_path: str = "samples/violations.json",
    changes_log_path: str = "samples/changes.log.json",
    output_path: str = "samples/report.md",
    ifc_name: str = "Unknown",
) -> dict:
    """한국어 마크다운 보고서를 생성합니다.

    Args:
        violations_path: 위반 사항 JSON
        changes_log_path: 변경 로그 JSON
        output_path: 보고서 출력 경로
        ifc_name: 보고서 헤더에 표시할 IFC 이름

    Returns:
        보고서 경로, 미리보기 (처음 500자)
    """
    if not Path(violations_path).exists():
        return {"error": f"위반 파일 없음: {violations_path}"}

    md = run_generate_report(
        violations_path=violations_path,
        changes_log_path=changes_log_path,
        output_path=output_path,
        ifc_name=ifc_name,
    )

    preview = md[:500] + ("..." if len(md) > 500 else "")
    return {
        "output_path": output_path,
        "length_chars": len(md),
        "preview": preview,
    }


# ============================================
# 도구 6: run_full_pipeline (통합)
# ============================================

@mcp.tool()
@silent
def run_full_pipeline(
    ifc_path: str,
    rules_md_path: str,
    skip_compile: bool = False,
) -> dict:
    """전체 파이프라인 (compile → validate → fix → report)을 한 번에 실행합니다.

    Args:
        ifc_path: IFC 파일 경로
        rules_md_path: 자연어 룰 마크다운 경로
        skip_compile: True면 기존 rules_compiled.json 재사용 (API 호출 없음)

    Returns:
        각 단계 결과 요약
    """
    from src.main import run_pipeline

    if not Path(ifc_path).exists():
        return {"error": f"IFC 없음: {ifc_path}"}
    if not Path(rules_md_path).exists():
        return {"error": f"룰 없음: {rules_md_path}"}

    result = run_pipeline(
        ifc_path=ifc_path,
        rules_md_path=rules_md_path,
        skip_compile=skip_compile,
    )

    return result


# ============================================
# 도구 7: ai_agent_mode (AI Agent + Tools 패턴)
# ============================================

@mcp.tool()
@silent
def ai_agent_mode(
    ifc_path: str,
    rules_compiled_path: str = "samples/rules_compiled.json",
    output_ifc_path: str = None,
    report_path: str = "samples/report_ai.md",
) -> dict:
    """AI Agent 모드 — Claude가 IFC 분석/위반 판단/수정 결정, Python 도구가 실행.

    호출 흐름:
      1. Python: IFC 요약 추출
      2. Claude API #1: 위반 판단 + 수정 명령 결정
      3. Python 도구: 결정대로 IFC 수정
      4. Claude API #2: 한국어 보고서 작성

    Args:
        ifc_path: IFC 파일 경로
        rules_compiled_path: 컴파일된 룰 JSON
        output_ifc_path: 출력 IFC 경로
        report_path: AI 보고서 경로

    Returns:
        분석 내용, 결정 수, 수정 성공 수, 출력 파일 경로들
    """
    if not Path(ifc_path).exists():
        return {"error": f"IFC 없음: {ifc_path}"}
    if not Path(rules_compiled_path).exists():
        return {"error": f"룰 없음: {rules_compiled_path}. compile_rules 먼저 실행."}

    result = run_ai_agent(
        ifc_path=ifc_path,
        rules_compiled_path=rules_compiled_path,
        output_ifc_path=output_ifc_path,
        report_path=report_path,
    )
    # IFC 요약은 너무 크니까 일부만
    summary = result.get("ifc_summary", {})
    return {
        "ifc": summary.get("ifc_path"),
        "schema": summary.get("schema"),
        "total_walls": summary.get("total_walls"),
        "ai_analysis": result.get("ai_analysis"),
        "decisions_count": result.get("decisions_count"),
        "fixed_count": result.get("fixed_count"),
        "output_ifc": result.get("output_ifc"),
        "report_path": result.get("report_path"),
    }


# ============================================
# 도구 8: ai_react_agent (ReAct Tool Use 패턴)
# ============================================

@mcp.tool()
@silent
def ai_react_agent(
    ifc_path: str,
    output_ifc_path: str = None,
    user_request: str = None,
) -> dict:
    """ReAct AI Agent — Claude가 도구를 자율적으로 N번 호출하며 IFC 처리.

    옵션 F: Anthropic Tool Use API 기반. 산업 표준 Agentic 패턴.

    호출 흐름:
      1. Claude → list_walls (벽 목록 확인)
      2. Claude → fix_thickness/fix_firerating/fix_material (위반마다)
      3. Claude → save_ifc (마지막)

    Claude API 호출 횟수는 위반 사항에 따라 동적 (N+1번).

    Args:
        ifc_path: IFC 경로
        output_ifc_path: 출력 경로 (기본: samples/{name}_fixed.ifc)
        user_request: 사용자 자연어 명령 (기본: 한국 화재 룰 적용)

    Returns:
        Claude API 호출 횟수, 도구 호출 내역, 출력 IFC 경로
    """
    if not Path(ifc_path).exists():
        return {"error": f"IFC 없음: {ifc_path}"}

    result = run_react_agent(
        ifc_path=ifc_path,
        output_path=output_ifc_path,
        user_request=user_request,
        verbose=False,  # MCP에선 silent
    )
    return result


# ============================================
# 메인
# ============================================

if __name__ == "__main__":
    mcp.run()
