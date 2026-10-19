CLASS ltd_flat_rate DEFINITION FINAL FOR TESTING.

  PUBLIC SECTION.
    INTERFACES zif_tax_rate.

ENDCLASS.


CLASS ltd_flat_rate IMPLEMENTATION.

  METHOD zif_tax_rate~rate_for.
    result = 23.
  ENDMETHOD.

ENDCLASS.


CLASS ltcl_order_total DEFINITION FINAL FOR TESTING
  DURATION SHORT
  RISK LEVEL HARMLESS.

  PRIVATE SECTION.
    DATA cut TYPE REF TO zcl_order_total.

    METHODS setup.
    METHODS net_total_sums_all_lines FOR TESTING.
    METHODS gross_total_adds_tax FOR TESTING.
    METHODS empty_order_totals_zero FOR TESTING.

ENDCLASS.


CLASS ltcl_order_total IMPLEMENTATION.

  METHOD setup.
    cut = NEW #( NEW ltd_flat_rate( ) ).
  ENDMETHOD.

  METHOD net_total_sums_all_lines.
    cl_abap_unit_assert=>assert_equals(
      exp = 250
      act = cut->net_total( VALUE #( ( category = `BOOK` quantity = 2 price = 100 )
                                     ( category = `PEN`  quantity = 5 price = 10 ) ) ) ).
  ENDMETHOD.

  METHOD gross_total_adds_tax.
    cl_abap_unit_assert=>assert_equals(
      exp = 123
      act = cut->gross_total( VALUE #( ( category = `BOOK` quantity = 1 price = 100 ) ) ) ).
  ENDMETHOD.

  METHOD empty_order_totals_zero.
    cl_abap_unit_assert=>assert_equals(
      exp = 0
      act = cut->gross_total( VALUE #( ) ) ).
  ENDMETHOD.

ENDCLASS.
