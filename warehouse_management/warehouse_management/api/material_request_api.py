import json

import frappe
from frappe import _
from frappe.utils import flt, nowdate
from erpnext.stock.doctype.material_request.material_request import create_pick_list as make_pick_list
from erpnext.stock.doctype.pick_list.pick_list import create_stock_entry as make_outward_stock_entry
from erpnext.stock.doctype.stock_entry.stock_entry import make_stock_in_entry


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
def get_item_storage_bins(item_code, warehouse):
    item_name = frappe.db.get_value("Item", item_code, "item_name")

    bins = frappe.get_all(
        "Storage Bin",
        filters={
            "assigned_item": item_code,
            "warehouse": warehouse,
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
        "warehouse": warehouse,
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
    bin_assignment_data = []

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

            bin_assignment_data.append(
                {
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

    for assignment in bin_assignment_data:
        assignment["pick_list"] = pick_list.name

        bin_assignment = frappe.get_doc(
            {
                "doctype": "Bin Assignment",
                **assignment,
            }
        )

        bin_assignment.insert()
        bin_assignments.append(bin_assignment.name)

    pick_list.submit()

    return {
        "mr_id": mr.name,
        "assignment_type": assignment_type,
        "bin_assignments": bin_assignments,
        "pick_list": pick_list.name,
    }


def create_pick_list(mr, picked_items):
    pick_list = make_pick_list(mr.name)
    pick_list.pick_manually = 1
    pick_list.source_warehouse = mr.set_from_warehouse
    pick_list.destination_warehouse = mr.set_warehouse

    picked_qty_by_item = {
        item["item_code"]: flt(item["qty"])
        for item in picked_items.values()
    }

    pick_list.locations = [
        row for row in pick_list.locations
        if row.item_code in picked_qty_by_item
    ]

    for row in pick_list.locations:
        picked_qty = picked_qty_by_item[row.item_code]
        row.warehouse = mr.set_from_warehouse
        row.qty = picked_qty
        row.stock_qty = picked_qty * flt(row.conversion_factor or 1)

    pick_list.insert()

    return pick_list


@frappe.whitelist()
def create_stock_entry(data=None):
    if isinstance(data, str):
        data = json.loads(data)

    data = data or frappe.form_dict

    action = data.get("action")
    items = data.get("items", [])

    if action not in ("add_to_transit", "end_transit"):
        frappe.throw(_("Action must be 'add_to_transit' or 'end_transit'"))

    if action == "add_to_transit":
        transit_wh = data.get("transit_wh")
        pl_id = data.get("pl_id")

        if not transit_wh:
            frappe.throw(_("Transit Warehouse is required"))

        if not pl_id:
            frappe.throw(_("Pick List is required"))

        pick_list = frappe.get_doc("Pick List", pl_id)

        stock_entry = frappe.get_doc(make_outward_stock_entry(
            frappe.as_json(pick_list.as_dict())
        ))

        stock_entry.material_request = pick_list.material_request
        stock_entry.from_warehouse = pick_list.source_warehouse
        stock_entry.to_warehouse = transit_wh
        stock_entry.destination_warehouse = pick_list.destination_warehouse
        stock_entry.add_to_transit = 1

        response = {
            "pick_list": pl_id,
            "material_request": pick_list.material_request,
        }

        item_map = {d.get("item_code"): d for d in items}

        for row in stock_entry.items:
            req = item_map.get(row.item_code)

            if not req:
                continue

            qty = flt(req.get("qty", row.qty))
            row.qty = qty
            row.transfer_qty = qty
            row.t_warehouse = stock_entry.to_warehouse

    else:
        outward_se = data.get("stock_entry")
        destination_wh = data.get("destination_wh")

        if not outward_se:
            frappe.throw(_("Outward Stock Entry is required"))

        if not destination_wh:
            frappe.throw(_("Destination Warehouse is required"))

        outward = frappe.get_doc("Stock Entry", outward_se)

        stock_entry = frappe.get_doc(make_stock_in_entry(outward.name))
        stock_entry.from_warehouse = outward.to_warehouse
        stock_entry.to_warehouse = destination_wh
        stock_entry.destination_warehouse = None

        response = {
            "outward_stock_entry": outward.name,
        }

        original_rows = list(stock_entry.items)
        stock_entry.set("items", [])

        for row in original_rows:
            requests = [d for d in items if d.get("item_code") == row.item_code]

            if not requests:
                requests = [{}]

            for req in requests:
                new_row = stock_entry.append("items", {})
                new_row.update(row.as_dict())

                qty = flt(req.get("qty", row.qty))
                new_row.qty = qty
                new_row.transfer_qty = qty
                new_row.t_warehouse = destination_wh

                if req.get("rack"):
                    new_row.rack = req.get("rack")

                if req.get("bin"):
                    new_row.bin = req.get("bin")

    stock_entry.insert()
    stock_entry.submit()

    response.update(
        {
            "action": action,
            "stock_entry": stock_entry.name,
        }
    )

    return response


@frappe.whitelist()
def get_transit_stock_entries(destination_warehouse):
    stock_entries = frappe.get_all(
        "Stock Entry",
        filters={
            "docstatus": 1,
            "add_to_transit": 1,
            "stock_entry_type": "Material Transfer",
            "destination_warehouse": destination_warehouse,
            "per_transferred": ("<", 100),
        },
        fields=[
            "name",
            "pick_list",
            "material_request",
            "from_warehouse",
            "to_warehouse",
            "destination_warehouse"
        ],
    )

    return [
        {
            "stock_entry": entry.name,
            "pick_list": entry.pick_list,
            "material_request": entry.material_request,
            "from_warehouse": entry.from_warehouse,
            "transit_warehouse": entry.to_warehouse,
            "destination_warehouse": destination_warehouse
        }
        for entry in stock_entries
    ]
