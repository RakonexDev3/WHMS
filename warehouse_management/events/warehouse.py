import frappe
from frappe import _


def validate_warehouse_type(doc, method=None):
    if doc.is_sub_warehouse and doc.warehouse_type == "Storage":
        frappe.throw(
            _("Sub warehouses cannot be marked as Storage")
        )

    if not doc.is_sub_warehouse and doc.warehouse_type in ["Bay", "Hold"]:
        frappe.throw(
            _("Main warehouses cannot be marked as Bay or Hold")
        )