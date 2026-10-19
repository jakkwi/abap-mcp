from abap_mcp.outline import outline
from tests.conftest import read


def test_outlines_public_class_with_signatures_and_bodies() -> None:
    [cls] = outline(read("shop/src/zcl_order_total.clas.abap"))
    assert (cls.name, cls.kind, cls.public, cls.final) == ("zcl_order_total", "class", True, True)
    assert cls.documented

    gross = cls.method("gross_total")
    assert gross is not None
    assert gross.visibility == "public"
    assert gross.importing == ["lines"]
    assert gross.returning == "result"
    assert gross.documented
    assert gross.implemented_at == (56, 61)
    assert gross.statements == 4

    line_net = cls.method("line_net")
    assert line_net is not None and line_net.visibility == "private"
    assert [a["name"] for a in cls.attributes] == ["tax_rate"]


def test_constructor_type_is_not_mistaken_for_a_parameter() -> None:
    [cls] = outline(read("shop/src/zcl_order_total.clas.abap"))
    constructor = cls.method("constructor")
    assert constructor is not None and constructor.importing == ["tax_rate"]


def test_outlines_test_classes_and_interface_implementations() -> None:
    double, tests = outline(read("shop/src/zcl_order_total.clas.testclasses.abap"))
    assert double.interfaces == ["zif_tax_rate"]
    assert double.method("zif_tax_rate~rate_for") is not None
    assert tests.for_testing
    assert [m.name for m in tests.methods if m.for_testing] == [
        "net_total_sums_all_lines",
        "gross_total_adds_tax",
        "empty_order_totals_zero",
    ]


def test_outlines_interface() -> None:
    [intf] = outline(read("shop/src/zif_tax_rate.intf.abap"))
    assert (intf.kind, intf.public) == ("interface", True)
    method = intf.method("rate_for")
    assert method is not None and method.importing == ["category"] and method.returning == "result"


def test_parses_complex_signatures() -> None:
    source = """
    CLASS lcl DEFINITION ABSTRACT INHERITING FROM zcl_base.
      PROTECTED SECTION.
        CLASS-METHODS m
          IMPORTING a TYPE STANDARD TABLE OF t WITH EMPTY KEY OPTIONAL
                    b TYPE i DEFAULT 5
                    !c TYPE REF TO data
          EXPORTING VALUE(d) TYPE string
          CHANGING  e TYPE x
          RAISING   cx_a RESUMABLE(cx_b).
    ENDCLASS."""
    [cls] = outline(source)
    assert cls.abstract and cls.superclass == "zcl_base"
    method = cls.methods[0]
    assert method.static and method.visibility == "protected"
    assert (method.importing, method.exporting, method.changing) == (["a", "b", "c"], ["d"], ["e"])
    assert method.raising == ["cx_a", "cx_b"]


def test_ignores_deferred_definitions() -> None:
    assert outline("CLASS lcl DEFINITION DEFERRED.") == []
