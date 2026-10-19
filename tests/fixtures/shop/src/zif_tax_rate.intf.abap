"! Supplies the tax rate that applies to an order line.
INTERFACE zif_tax_rate PUBLIC.

  "! Returns the tax rate in percent for a product category.
  "! @parameter category | Product category
  "! @parameter result   | Tax rate in percent, e.g. 23
  METHODS rate_for
    IMPORTING category      TYPE string
    RETURNING VALUE(result) TYPE i.

ENDINTERFACE.
