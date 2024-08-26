from ariadne import ObjectType
from graphql import GraphQLResolveInfo
from stripe import (
    Invoice,
    InvoiceLineItem,
    ListObject,
    PaymentMethod,
)

invoice_bindable = ObjectType("Invoice")


@invoice_bindable.field("id")
def resolve_invoice_id(invoice: Invoice, info: GraphQLResolveInfo) -> str | None:
    return invoice["id"]


@invoice_bindable.field("number")
def resolve_invoice_number(invoice: Invoice, info: GraphQLResolveInfo) -> str | None:
    return invoice["number"]


@invoice_bindable.field("status")
def resolve_invoice_status(invoice: Invoice, info: GraphQLResolveInfo) -> str | None:
    return invoice["status"]


@invoice_bindable.field("created")
def resolve_invoice_created(invoice: Invoice, info: GraphQLResolveInfo) -> int:
    return invoice["created"]


@invoice_bindable.field("periodStart")
def resolve_invoice_period_start(invoice: Invoice, info: GraphQLResolveInfo) -> int:
    return invoice["period_start"]


@invoice_bindable.field("periodEnd")
def resolve_invoice_period_end(invoice: Invoice, info: GraphQLResolveInfo) -> int:
    return invoice["period_end"]


@invoice_bindable.field("dueDate")
def resolve_invoice_due_date(invoice: Invoice, info: GraphQLResolveInfo) -> int | None:
    return invoice["due_date"]


@invoice_bindable.field("customerName")
def resolve_invoice_customer_name(
    invoice: Invoice, info: GraphQLResolveInfo
) -> str | None:
    return invoice["customer_name"]


# NOTE: Not currently used in Gazebo, keep for address updates
@invoice_bindable.field("customerAddress")
def resolve_invoice_customer_address(
    invoice: Invoice, info: GraphQLResolveInfo
) -> str | None:
    if invoice["customer_address"]:
        return str(invoice["customer_address"])
    return None


# NOTE: Not currently used in Gazebo, keep for tax id updates
@invoice_bindable.field("currency")
def resolve_invoice_currency(invoice: Invoice, info: GraphQLResolveInfo) -> str:
    return invoice["currency"]


@invoice_bindable.field("amountPaid")
def resolve_invoice_amount_paid(invoice: Invoice, info: GraphQLResolveInfo) -> int:
    return invoice["amount_paid"]


@invoice_bindable.field("amountDue")
def resolve_invoice_amount_due(invoice: Invoice, info: GraphQLResolveInfo) -> int:
    return invoice["amount_due"]


@invoice_bindable.field("total")
def resolve_invoice_total(invoice: Invoice, info: GraphQLResolveInfo) -> int:
    return invoice["total"]


@invoice_bindable.field("subtotal")
def resolve_invoice_subtotal(invoice: Invoice, info: GraphQLResolveInfo) -> int:
    return invoice["subtotal"]


@invoice_bindable.field("lineItems")
def resolve_invoice_line_items(
    invoice: Invoice, info: GraphQLResolveInfo
) -> ListObject[InvoiceLineItem]:
    return invoice["lines"]["data"]


@invoice_bindable.field("footer")
def resolve_invoice_footer(invoice: Invoice, info: GraphQLResolveInfo) -> str | None:
    return invoice["footer"]


@invoice_bindable.field("customerEmail")
def resolve_invoice_customer_email(
    invoice: Invoice, info: GraphQLResolveInfo
) -> str | None:
    return invoice["customer_email"]


@invoice_bindable.field("defaultPaymentMethod")
def resolve_invoice_default_payment_method(
    invoice: Invoice, info: GraphQLResolveInfo
) -> PaymentMethod | None:
    return invoice["default_payment_method"]


@invoice_bindable.field("taxIds")
def resolve_invoice_tax_ids(invoice: Invoice, info: GraphQLResolveInfo) -> list:
    return invoice["customer_tax_ids"]
