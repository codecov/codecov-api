from functools import cached_property
from typing import List, Optional

from ariadne import ObjectType
from stripe import (
    Customer,
    Invoice,
    InvoiceLineItem,
    ListObject,
    PaymentMethod,
)

invoice_bindable = ObjectType("Invoice")


@invoice_bindable.field("id")
def resolve_invoice_id(invoice: Invoice, info) -> str | None:
    return invoice.id


@invoice_bindable.field("number")
def resolve_invoice_number(invoice: Invoice, info) -> str | None:
    return invoice.number


@invoice_bindable.field("status")
def resolve_invoice_status(invoice: Invoice, info) -> str | None:
    return invoice.status


@invoice_bindable.field("created")
def resolve_invoice_created(invoice: Invoice, info) -> int:
    return invoice.created


@invoice_bindable.field("periodStart")
def resolve_invoice_period_start(invoice: Invoice, info) -> int:
    return invoice.period_start


@invoice_bindable.field("periodEnd")
def resolve_invoice_period_end(invoice: Invoice, info) -> int:
    return invoice.period_end


@invoice_bindable.field("dueDate")
def resolve_invoice_due_date(invoice: Invoice, info) -> int | None:
    return invoice.due_date


@invoice_bindable.field("customerName")
def resolve_invoice_customer_name(invoice: Invoice, info) -> str | None:
    return invoice.customer_name


# NOTE: This doesn't currently look to be used in gazebo, maybe can remove?
@invoice_bindable.field("customerAddress")
def resolve_invoice_customer_address(invoice: Invoice, info) -> str:
    return str(invoice.customer_address)


# NOTE: This doesn't currently look to be used in gazebo, maybe can remove?
@invoice_bindable.field("currency")
def resolve_invoice_currency(invoice: Invoice, info) -> str:
    return invoice.currency


@invoice_bindable.field("amountPaid")
def resolve_invoice_amount_paid(invoice: Invoice, info) -> int:
    return invoice.amount_paid


@invoice_bindable.field("amountDue")
def resolve_invoice_amount_due(invoice: Invoice, info) -> int:
    return invoice.amount_due


@invoice_bindable.field("amountRemaining")
def resolve_invoice_amount_remaining(invoice: Invoice, info) -> int:
    return invoice.amount_remaining


@invoice_bindable.field("total")
def resolve_invoice_total(invoice: Invoice, info) -> int:
    return invoice.total


# NOTE: This doesn't currently look to be used in gazebo, maybe can remove?
@invoice_bindable.field("subtotal")
def resolve_invoice_subtotal(invoice: Invoice, info) -> int:
    return invoice.subtotal


# NOTE: This doesn't currently look to be used in gazebo, maybe can remove?
@invoice_bindable.field("invoicePdf")
def resolve_invoice_pdf(invoice: Invoice, info) -> str | None:
    return invoice.invoice_pdf


@invoice_bindable.field("lineItems")
def resolve_invoice_line_items(invoice: Invoice, info) -> ListObject[InvoiceLineItem]:
    return invoice.lines


@invoice_bindable.field("footer")
def resolve_invoice_footer(invoice: Invoice, info) -> str | None:
    return invoice.footer


@invoice_bindable.field("customerEmail")
def resolve_invoice_customer_email(invoice: Invoice, info) -> str | None:
    return invoice.customer_email


# NOTE: This doesn't currently look to be used in gazebo, maybe can remove?
@invoice_bindable.field("customerShipping")
def resolve_invoice_customer_shipping(invoice: Invoice, info) -> str:
    return str(invoice.customer_shipping)


# NOTE: May need to create a separate type for this; FWIW this doesn't currently work on local
@invoice_bindable.field("defaultPaymentMethod")
def resolve_invoice_default_payment_method(
    invoice: Invoice, info
) -> PaymentMethod | None:
    return invoice.default_payment_method
