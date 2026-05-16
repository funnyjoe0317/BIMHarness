"""
Agent 5: Reporter
violations + changes → Markdown 보고서 생성

흐름:
  violations.json (Agent 3)
  changes.log.json (Agent 4)
       ↓ generate_report()
  report.md
       ↓ (선택) markdown_to_pdf()
  report.pdf

특징:
  - 한국어 보고서
  - 위반 + 자동 수정 + 수동 검토 필요 사항 구분
  - PM에게 직접 전달 가능한 형식

사용:
  python -m src.agents.agent_5_reporter
"""

import json
import sys
from datetime import datetime
from pathlib import Path


SEVERITY_EMOJI = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}


def _format_value(v):
    if v is None:
        return "(없음)"
    if isinstance(v, str) and len(v) > 50:
        return v[:47] + "..."
    return str(v)


def generate_report(
    violations_path: str = "samples/violations.json",
    changes_log_path: str = "samples/changes.log.json",
    output_path: str = "samples/report.md",
    ifc_name: str = "Unknown",
) -> str:
    """전체 보고서 생성"""
    violations_data = json.loads(Path(violations_path).read_text(encoding="utf-8"))
    changes_data = json.loads(Path(changes_log_path).read_text(encoding="utf-8"))

    violations = violations_data.get("violations", [])
    rule_summary = violations_data.get("rule_summary", {})
    changes = changes_data.get("changes", [])
    skipped = changes_data.get("skipped_violations", [])

    lines = []

    # === 헤더 ===
    lines.append("# 📋 BIM 검토 보고서")
    lines.append("")
    lines.append(f"> 생성: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"> 대상 IFC: `{ifc_name}`")
    lines.append(f"> 검토 도구: BIMHarness (자연어 룰 기반)")
    lines.append("")
    lines.append("---")

    # === 요약 ===
    lines.append("")
    lines.append("## 📊 요약")
    lines.append("")
    lines.append(f"- **전체 위반**: {violations_data.get('total_violations', 0)}건")
    lines.append(f"- **자동 수정 완료**: {changes_data.get('auto_fixed', 0)}건")
    lines.append(f"- **수동 검토 필요**: {changes_data.get('skipped', 0)}건")
    lines.append("")

    # === 룰별 통계 ===
    lines.append("### 룰별 위반 현황")
    lines.append("")
    lines.append("| 룰 | 이름 | 심각도 | 위반 | 자동수정 |")
    lines.append("|---|---|:---:|---:|:---:|")
    for rule_id, summary in rule_summary.items():
        emoji = SEVERITY_EMOJI.get(summary.get("severity", "Medium"), "⚪")
        auto = "✅" if summary.get("auto_fixable") else "❌"
        lines.append(
            f"| {rule_id} | {summary.get('name', '')} | {emoji} | "
            f"{summary.get('violation_count', 0)} | {auto} |"
        )
    lines.append("")
    lines.append("---")

    # === 자동 수정 완료 ===
    success_changes = [c for c in changes if c["result"]["status"] == "success"]
    if success_changes:
        lines.append("")
        lines.append("## ✅ 자동 수정 완료")
        lines.append("")
        lines.append(f"총 {len(success_changes)}건이 자동으로 수정되었습니다.")
        lines.append("")
        lines.append("| # | 룰 | 객체 | 변경 사항 |")
        lines.append("|---:|---|---|---|")
        for i, c in enumerate(success_changes, 1):
            lines.append(
                f"| {i} | {c['rule_id']} | "
                f"{_format_value(c.get('element_name'))} | "
                f"{c['result'].get('action', '')} |"
            )
        lines.append("")
        lines.append("> 원본 IFC는 자동 백업되었습니다.")
        lines.append(f"> 백업 경로: `{changes_data.get('backup_path')}`")
        lines.append("")
        lines.append("---")

    # === 자동 수정 실패 ===
    failed_changes = [c for c in changes if c["result"]["status"] == "error"]
    if failed_changes:
        lines.append("")
        lines.append("## ⚠️ 자동 수정 실패")
        lines.append("")
        for c in failed_changes:
            lines.append(f"- **{c['rule_id']}** ({c.get('element_name')}): "
                         f"{c['result'].get('reason')}")
        lines.append("")
        lines.append("---")

    # === 수동 검토 필요 ===
    if skipped:
        lines.append("")
        lines.append("## 🔍 수동 검토 필요")
        lines.append("")
        lines.append(f"다음 {len(skipped)}건은 자동 수정이 불가능합니다.")
        lines.append("설계자가 직접 검토 후 수정이 필요합니다.")
        lines.append("")
        for i, s in enumerate(skipped, 1):
            lines.append(f"### {i}. {s['rule_id']} - {s.get('element_name', '')}")
            lines.append(f"- **위치**: {s.get('guid', '')}")
            lines.append(f"- **이유**: {s.get('reason', '')}")
            lines.append("")
        lines.append("---")

    # === 결과 파일 ===
    lines.append("")
    lines.append("## 📁 결과 파일")
    lines.append("")
    lines.append(f"- **수정된 IFC**: `{changes_data.get('output_ifc')}`")
    lines.append(f"- **원본 백업**: `{changes_data.get('backup_path')}`")
    lines.append(f"- **변경 로그**: `{Path(changes_log_path).name}`")
    lines.append("")
    lines.append("### 무결성 검증")
    lines.append(f"- 원본 SHA-256: `{changes_data.get('original_sha256', '')[:32]}...`")
    lines.append(f"- 수정 SHA-256: `{changes_data.get('output_sha256', '')[:32]}...`")
    lines.append("")
    lines.append("---")

    # === 푸터 ===
    lines.append("")
    lines.append("## 📚 사용 룰")
    lines.append("")
    lines.append("이 보고서는 다음 자연어 룰에서 생성되었습니다:")
    lines.append("- `samples/rules_korean_law.md`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*BIMHarness v0.1 — Claude Code의 CLAUDE.md 패턴을 BIM 검증에 적용*")
    lines.append("")

    # 저장
    text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    return text


def markdown_to_pdf(md_path: str, pdf_path: str) -> bool:
    """Markdown → PDF (선택, reportlab 등 추가 라이브러리 필요)"""
    # Phase 2에서 구현
    # pip install reportlab markdown
    print(f"⚠️  PDF 변환은 Phase 2에서 구현 예정")
    print(f"   현재는 Markdown ({md_path}) 만 생성")
    return False


# ============================================
# 메인 흐름
# ============================================

def run(
    ifc_path: str = "samples/SimpleWall.ifc",
    violations_path: str = "samples/violations.json",
    changes_log_path: str = "samples/changes.log.json",
    output_path: str = "samples/report.md",
) -> str:
    """Agent 5 실행"""
    print("=" * 60)
    print(f"📝 Agent 5: 보고서 생성 시작")
    print("=" * 60)

    ifc_name = Path(ifc_path).name
    text = generate_report(
        violations_path, changes_log_path, output_path, ifc_name
    )

    print(f"\n💾 저장: {output_path}")
    print(f"   {len(text.splitlines())}줄")
    print(f"\n미리보기 (처음 30줄):")
    print("=" * 60)
    for line in text.splitlines()[:30]:
        print(line)
    print("...")

    return text


if __name__ == "__main__":
    ifc_path = sys.argv[1] if len(sys.argv) > 1 else "samples/SimpleWall.ifc"
    run(ifc_path=ifc_path)
