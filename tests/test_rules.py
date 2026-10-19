import pytest

from abap_mcp import rules
from tests.conftest import read


def rule_ids(source: str) -> set[str]:
    return {f.rule for f in rules.check(source)}


def test_clean_class_has_no_findings() -> None:
    assert rules.check(read("shop/src/zcl_order_total.clas.abap")) == []


def test_legacy_class_triggers_every_relevant_rule() -> None:
    findings = rules.check(read("shop/src/zcl_legacy_invoice.clas.abap"))
    assert {f.rule for f in findings} == {
        "document-public-api",
        "line-length",
        "no-empty-catch",
        "no-hungarian-notation",
        "no-obsolete-statements",
        "prefer-is-not",
        "prefer-returning",
    }
    assert findings == sorted(findings, key=lambda f: (f.line, f.rule))
    assert all(f.guide_section and f.suggestion for f in findings)


@pytest.mark.parametrize(
    ("statement", "label"),
    [
        ("MOVE a TO b.", "MOVE"),
        ("COMPUTE a = b + 1.", "COMPUTE"),
        ("ADD 1 TO counter.", "ADD ... TO"),
        ("REFRESH items.", "REFRESH"),
        ("DESCRIBE TABLE items LINES count.", "DESCRIBE TABLE ... LINES"),
        ("CALL METHOD obj->run.", "CALL METHOD"),
        ("PERFORM legacy_routine.", "FORM/PERFORM"),
        ("DATA items TYPE t OCCURS 0.", "OCCURS"),
    ],
)
def test_flags_obsolete_statements(statement: str, label: str) -> None:
    [finding] = [f for f in rules.check(statement) if f.rule == "no-obsolete-statements"]
    assert label in finding.message


@pytest.mark.parametrize(
    "statement",
    ["MOVE-CORRESPONDING a TO b.", "CALL METHOD (dynamic_name).", "result = a + b.", "counter += 1."],
)
def test_does_not_flag_modern_or_dynamic_code(statement: str) -> None:
    assert "no-obsolete-statements" not in rule_ids(statement)


def test_hungarian_notation_in_declarations_and_inline_data() -> None:
    findings = rules.check("DATA: lv_a TYPE i, total TYPE i.\nLOOP AT x INTO DATA(ls_row). ENDLOOP.")
    names = sorted(f.message.split("'")[1] for f in findings if f.rule == "no-hungarian-notation")
    assert names == ["ls_row", "lv_a"]


def test_long_method_is_reported_once() -> None:
    body = "\n".join(f"    x = {i}." for i in range(45))
    source = f"CLASS lcl IMPLEMENTATION.\n  METHOD big.\n{body}\n  ENDMETHOD.\nENDCLASS."
    findings = [f for f in rules.check(source) if f.rule == "method-length"]
    assert len(findings) == 1 and "45 statements" in findings[0].message
    assert rules.check(source, max_method_statements=50) == []


def test_every_rule_is_registered_with_a_guide_section() -> None:
    ids = [r.id for r in rules.RULES]
    assert len(ids) == len(set(ids)) == 8
    assert all(r.guide_section for r in rules.RULES)
