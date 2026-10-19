"! Calculates order totals with tax from a list of order lines.
CLASS zcl_order_total DEFINITION
  PUBLIC
  FINAL
  CREATE PUBLIC.

  PUBLIC SECTION.
    TYPES:
      BEGIN OF order_line,
        category TYPE string,
        quantity TYPE i,
        price    TYPE i,
      END OF order_line,
      order_lines TYPE STANDARD TABLE OF order_line WITH EMPTY KEY.

    "! @parameter tax_rate | Source of tax rates per category
    METHODS constructor
      IMPORTING tax_rate TYPE REF TO zif_tax_rate.

    "! Returns the net total of all lines, before tax.
    "! @parameter lines  | Order lines
    "! @parameter result | Net total
    METHODS net_total
      IMPORTING lines         TYPE order_lines
      RETURNING VALUE(result) TYPE i.

    "! Returns the gross total of all lines, tax included and rounded down.
    "! @parameter lines  | Order lines
    "! @parameter result | Gross total
    METHODS gross_total
      IMPORTING lines         TYPE order_lines
      RETURNING VALUE(result) TYPE i.

  PRIVATE SECTION.
    DATA tax_rate TYPE REF TO zif_tax_rate.

    METHODS line_net
      IMPORTING line          TYPE order_line
      RETURNING VALUE(result) TYPE i.

ENDCLASS.


CLASS zcl_order_total IMPLEMENTATION.

  METHOD constructor.
    me->tax_rate = tax_rate.
  ENDMETHOD.

  METHOD net_total.
    result = REDUCE i( INIT sum = 0
                       FOR line IN lines
                       NEXT sum = sum + line_net( line ) ).
  ENDMETHOD.

  METHOD gross_total.
    LOOP AT lines INTO DATA(line).
      DATA(net) = line_net( line ).
      result = result + net + net * tax_rate->rate_for( line-category ) DIV 100.
    ENDLOOP.
  ENDMETHOD.

  METHOD line_net.
    result = line-quantity * line-price.
  ENDMETHOD.

ENDCLASS.
