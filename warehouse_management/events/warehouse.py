import frappe
from frappe import _


def validate_warehouse_type(doc, method=None):
    if doc.is_sub_warehouse and doc.warehouse_type == "Bay":
        frappe.throw(
            _("Sub warehouses cannot be marked as Bay")
        )

    if not doc.is_sub_warehouse and doc.warehouse_type in ["Storage", "Hold"]:
        frappe.throw(
            _("Main warehouses cannot be marked as Storage or Hold")
        )