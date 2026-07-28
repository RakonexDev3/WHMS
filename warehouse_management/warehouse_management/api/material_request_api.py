import json

import frappe
from frappe import _
from frappe.utils import flt, nowdate


@frappe.whitelist()
def get_material_request_stock(mr_id):
    mr = frappe.get_doc("Material Request", mr_id)

    warehouse = mr.set_from_warehouse

    item_codes = [row.item_code for row in mr.items]

    stock_by_item = {}

    if warehouse and item_codes:
        bins = frappe.get_all(
            "Bin",
            filters={
                "warehouse": warehouse,
                "item_code": ["in", item_codes],
            },
            fields=["item_code", "actual_qty"],
        )

        stock_by_item = {
            row.item_code: row.actual_qty or 0
            for row in bins
        }

    return {
        "mr_id": mr.name,
        "warehouse": warehouse,
        "items": [
            {
                "item_code": row.item_code,
                "item_name": row.item_name,
                "req_qty": row.qty,
                "wh_stock_bal": stock_by_item.get(row.item_code, 0),
                "uom": row.uom,
            }
            for row in mr.items
        ],
    }


@frappe.whitelist()
def get_item_storage_bins(item_code):
    item_name = frappe.db.get_value("Item", item_code, "item_name")

    bins = frappe.get_all(
        "Storage Bin",
        filters={
            "assigned_item": item_code,
            "status": "Occupied",
        },
        fields=[
            "name",
            "rack",
            "quantity",
            "uom",
        ],
        order_by="name asc",
    )

    return {
        "item_code": item_code,
        "item_name": item_name,
        "storage_bins": [
            {
                "bin": row.name,
                "rack": row.rack,
                "qty": row.quantity,
                "uom": row.uom,
            }
            for row in bins
        ],
    }


@frappe.whitelist()
def create_pick_list_from_bins(data=None):
    if isinstance(data, str):
        data = json.loads(data)

    data = data or frappe.form_dict

    mr_id = data.get("mr_id")
    assignment_type = data.get("assgn_type")
    items = data.get("items") or []

    if not mr_id:
        frappe.throw(_("Material Request ID is required."))

    if not frappe.db.exists("Material Request", mr_id):
        frappe.throw(_("Material Request {0} does not exist.").format(mr_id))

    if assignment_type != "Picking":
        frappe.throw(_("Assignment Type must be Picking."))

    if not items:
        frappe.throw(_("Items are required."))

    mr = frappe.get_doc("Material Request", mr_id)

    picked_items = {}
    bin_assignments = []

    for item in items:
        item_code = item.get("item_code")
        bins = item.get("bins") or []

        if not item_code:
            frappe.throw(_("Item Code is required."))

        if not bins:
            frappe.throw(
                _("Storage Bin is required for Item {0}.").format(item_code)
            )

        total_picked_qty = 0

        for bin_row in bins:
            bin_name = bin_row.get("bin")
            picked_qty = flt(bin_row.get("qty"))
            uom = bin_row.get("uom") or item.get("uom")

            if not bin_name:
                frappe.throw(
                    _("Storage Bin is required for Item {0}.").format(item_code)
                )

            if picked_qty <= 0:
                frappe.throw(
                    _("Picking quantity must be greater than zero for Bin {0}.").format(
                        bin_name
                    )
                )

            storage_bin = frappe.db.get_value(
                "Storage Bin",
                bin_name,
                [
                    "name",
                    "rack",
                    "warehouse",
                    "assigned_item",
                    "quantity",
                    "uom",
                    "status",
                ],
                as_dict=True,
            )

            if not storage_bin:
                frappe.throw(
                    _("Storage Bin {0} does not exist.").format(bin_name)
                )

            if storage_bin.assigned_item != item_code:
                frappe.throw(
                    _("Storage Bin {0} is not assigned to Item {1}.").format(
                        bin_name, item_code
                    )
                )

            if storage_bin.status != "Occupied":
                frappe.throw(
                    _("Storage Bin {0} is not occupied.").format(bin_name)
                )

            if picked_qty > flt(storage_bin.quantity):
                frappe.throw(
                    _(
                        "Insufficient quantity in Storage Bin {0}. "
                        "Available: {1}, Requested: {2}"
                    ).format(
                        bin_name,
                        storage_bin.quantity,
                        picked_qty,
                    )
                )

            bin_assignment = frappe.get_doc(
                {
                    "doctype": "Bin Assignment",
                    "item": item_code,
                    "uom": uom,
                    "rack": storage_bin.rack,
                    "bin": storage_bin.name,
                    "quantity": -picked_qty,
                    "doa": nowdate(),
                    "assignment_type": assignment_type,
                    "material_request": mr_id,
                }
            )

            bin_assignment.insert()

            bin_assignments.append(bin_assignment.name)
            total_picked_qty += picked_qty

        if item_code not in picked_items:
            picked_items[item_code] = {
                "item_code": item_code,
                "item_name": item.get("item_name"),
                "uom": item.get("uom"),
                "qty": 0,
            }

        picked_items[item_code]["qty"] += total_picked_qty

    pick_list = create_pick_list(mr, picked_items)

    return {
        "mr_id": mr.name,
        "assignment_type": assignment_type,
        "bin_assignments": bin_assignments,
        "pick_list": pick_list.name,
    }


def create_pick_list(mr, picked_items):
    pick_list = frappe.new_doc("Pick List")

    pick_list.purpose = "Material Transfer"
    pick_list.material_request = mr.name
    pick_list.source_warehouse = mr.set_from_warehouse
    pick_list.destination_warehouse = mr.set_warehouse

    for item in picked_items.values():
        pick_list.append(
            "locations",
            {
                "item_code": item["item_code"],
                "qty": item["qty"],
                "stock_qty": item["qty"],
                "stock_uom": item["uom"],
                "conversion_factor": 1,
            },
        )

    pick_list.insert()
    pick_list.submit()

    return pick_list