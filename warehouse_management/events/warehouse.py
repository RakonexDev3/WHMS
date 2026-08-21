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

    if doc.warehouse_type in ["Bay", "Storage"]:
        doc.include_in_transaction = 1

    # Only one Outward warehouse is allowed under a main warehouse
    if doc.is_sub_warehouse and doc.warehouse_type == "Outward":
        existing_outward = frappe.db.exists(
            "Warehouse",
            {
                "parent_warehouse": doc.parent_warehouse,
                "warehouse_type": "Outward",
                "is_sub_warehouse": 1,
                "name": ["!=", doc.name],
            },
        )

        if existing_outward:
            frappe.throw(
                _("Only one Outward warehouse is allowed per main warehouse.")
                )