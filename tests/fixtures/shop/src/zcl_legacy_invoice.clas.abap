CLASS zcl_legacy_invoice DEFINITION
  PUBLIC
  CREATE PUBLIC.

  PUBLIC SECTION.
    METHODS calculate
      IMPORTING iv_amount TYPE i
      EXPORTING ev_total  TYPE i.

    METHODS describe
      IMPORTING it_items       TYPE string_table
      RETURNING VALUE(rv_text) TYPE string.

ENDCLASS.


CLASS zcl_legacy_invoice IMPLEMENTATION.

  METHOD calculate.
    DATA lv_tax TYPE i.
    DATA lv_sum TYPE i.

    MOVE iv_amount TO lv_sum.
    COMPUTE lv_tax = lv_sum * 23 / 100.
    ADD lv_tax TO lv_sum.
    ev_total = lv_sum.
  ENDMETHOD.

  METHOD describe.
    DATA lv_count TYPE i.

    DESCRIBE TABLE it_items LINES lv_count.
    IF NOT lv_count IS INITIAL.
      rv_text = |Invoice with { lv_count } items, created by the legacy invoicing run, which nobody wants to touch any more|.
    ENDIF.
    TRY.
        rv_text = to_upper( rv_text ).
      CATCH cx_root.
    ENDTRY.
  ENDMETHOD.

ENDCLASS.
