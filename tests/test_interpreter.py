"""Agent 2 (룰 컴파일) 단위 테스트.

회귀 박제:
  - _extract_json: ```json 펜스 변형 모두 파싱 (Claude/Ollama 공통 후처리)
  - L8: 룰 ID 패턴 R1 + R_F1 (prefix) 모두 인식
  - validate_compiled_rule: 스키마 검증
  - backend 스위치(mock) 동작
"""

from src.agents.agent_2_interpreter import (
    _extract_json,
    parse_rules_md,
    validate_compiled_rule,
    compile_all,
)


# ── _extract_json (펜스 제거) ──────────────────────────────
def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_json_fence():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_with_bare_fence():
    assert _extract_json('```\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_with_whitespace():
    assert _extract_json('  \n {"a": 1}  \n ') == {"a": 1}


# ── parse_rules_md ID 패턴 (L8) ────────────────────────────
def test_parse_rules_md_id_patterns(tmp_path):
    md = tmp_path / "rules.md"
    md.write_text(
        "# 룰셋\n\n"
        "## R1. 방화구획\n- target: IfcBuildingStorey\n\n"
        "## R_F1. 외벽 화재등급\n- target: IfcWall\n\n"
        "## 가이드 섹션\n무시되어야 함\n",
        encoding="utf-8",
    )
    rules = parse_rules_md(str(md))
    ids = [r["id"] for r in rules]
    assert ids == ["R1", "R_F1"]          # prefix 있는 R_F1도 인식, 가이드는 제외


# ── validate_compiled_rule ─────────────────────────────────
def _valid_rule():
    return {"id": "R1", "target": "IfcWall",
            "check": {"type": "pset_value"}, "severity": "High"}


def test_validate_compiled_rule_ok():
    ok, _ = validate_compiled_rule(_valid_rule())
    assert ok is True


def test_validate_compiled_rule_missing_field():
    r = _valid_rule()
    del r["check"]
    ok, msg = validate_compiled_rule(r)
    assert ok is False and "check" in msg


def test_validate_compiled_rule_bad_target():
    r = _valid_rule()
    r["target"] = "Wall"                   # Ifc 로 시작 안 함
    ok, _ = validate_compiled_rule(r)
    assert ok is False


def test_validate_compiled_rule_bad_severity():
    r = _valid_rule()
    r["severity"] = "Critical"             # 허용값 아님
    ok, _ = validate_compiled_rule(r)
    assert ok is False


# ── backend=mock 컴파일 ────────────────────────────────────
def test_compile_all_mock(tmp_path):
    out = tmp_path / "compiled.json"
    compiled = compile_all(
        rules_md_path="bimsample/rules_korean_law.md",
        output_path=str(out),
        mock=True,
    )
    assert len(compiled) >= 1
    for r in compiled:                     # 전부 스키마 통과해야 함
        ok, _ = validate_compiled_rule(r)
        assert ok is True
    assert out.exists()


def test_compile_all_rejects_unknown_backend(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        compile_all(
            rules_md_path="bimsample/rules_korean_law.md",
            output_path=str(tmp_path / "x.json"),
            backend="gpt5",
        )
