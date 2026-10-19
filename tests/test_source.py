from abap_mcp.source import split_statements


def texts(source: str) -> list[str]:
    return [s.text for s in split_statements(source)]


def test_splits_on_periods_and_collapses_whitespace() -> None:
    assert texts("DATA x TYPE i.\nx   =\n  1.") == ["DATA x TYPE i", "x = 1"]


def test_ignores_periods_inside_literals_and_templates() -> None:
    source = "out = 'a. b'. msg = |Total: { amount }. Done.|. str = `x.y`."
    assert texts(source) == ["out = 'a. b'", "msg = |Total: { amount }. Done.|", "str = `x.y`"]


def test_handles_escaped_quotes() -> None:
    assert texts("x = 'it''s. fine'. y = 1.") == ["x = 'it''s. fine'", "y = 1"]


def test_drops_comments_but_keeps_abap_doc() -> None:
    source = '* full line comment\n"! Adds things.\nMETHODS add. " trailing. comment\nDATA y TYPE i.'
    statements = split_statements(source)
    assert [s.text for s in statements] == ["METHODS add", "DATA y TYPE i"]
    assert statements[0].abap_doc == ("Adds things.",)
    assert statements[1].abap_doc == ()


def test_records_line_numbers_of_multiline_statements() -> None:
    statements = split_statements("x = 1.\nMETHODS m\n  IMPORTING a TYPE i.\n")
    assert (statements[1].start_line, statements[1].end_line) == (2, 3)


def test_member_access_does_not_end_statement() -> None:
    assert texts("x = me->y. z = cl=>c-field.") == ["x = me->y", "z = cl=>c-field"]


def test_keyword_is_uppercased_first_word() -> None:
    assert split_statements("data: a type i.")[0].keyword == "DATA"
