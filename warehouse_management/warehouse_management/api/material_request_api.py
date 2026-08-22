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

    if assignment_type != "Picking":
        frappe.throw(_("Assignment Type must be Picking."))

    mr = frappe.get_doc("Material Request", mr_id)

    picked_items = {}
    requested_bins = {}

    for item in items:
        item_code = item.get("item_code")
        bins = item.get("bins") or []

        if not bins:
            frappe.throw(
                _("Storage Bin is required for Item {0}.").format(item_code)
            )

        picked_items.setdefault(
            item_code,
            {
                "item_code": item_code,
                "item_name": item.get("item_name"),
                "uom": item.get("uom"),
                "qty": 0,
            },
        )

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

            requested_bins[bin_name] = {
                "item_code": item_code,
                "qty": picked_qty,
                "uom": uom,
            }

    storage_bins = frappe.get_all(
        "Storage Bin",
        filters={"name": ["in", list(requested_bins)]},
        fields=[
            "name",
            "rack",
            "assigned_item",
            "quantity",
            "status",
        ],
    )

    storage_bin_map = {row.name: row for row in storage_bins}
    bin_assignment_data = []

    for bin_name, request in requested_bins.items():
        item_code = request["item_code"]
        picked_qty = request["qty"]

        storage_bin = storage_bin_map.get(bin_name)

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

        picked_items[item_code]["qty"] += picked_qty

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

    # ---------------------------------------------------------
    # Validate Picked Quantity Against Material Request
    # ---------------------------------------------------------

    mr_requested_qty = {}

    for row in mr.items:
        mr_requested_qty[row.item_code] = (
            mr_requested_qty.get(row.item_code, 0) + flt(row.qty)
        )

    for item_code, picked_data in picked_items.items():
        picked_qty = flt(picked_data["qty"])
        requested_qty = flt(mr_requested_qty.get(item_code, 0))

        if picked_qty > requested_qty:
            frappe.throw(
                _(
                    "Picking quantity {0} for Item {1} cannot be greater "
                    "than Material Request quantity {2}."
                ).format(
                    picked_qty,
                    item_code,
                    requested_qty,
                )
            )

    # ---------------------------------------------------------
    # Create Pick List
    # ---------------------------------------------------------

    pick_list = make_pick_list(mr.name)
    pick_list.pick_manually = 1
    pick_list.source_warehouse = mr.set_from_warehouse
    pick_list.destination_warehouse = mr.set_warehouse

    picked_qty_by_item = {
        item_code: flt(item["qty"])
        for item_code, item in picked_items.items()
    }

    locations = {}

    for row in pick_list.locations:
        if row.item_code not in picked_qty_by_item:
            continue

        if row.item_code not in locations:
            locations[row.item_code] = row

        row.warehouse = mr.set_from_warehouse
        row.qty = picked_qty_by_item[row.item_code]
        row.stock_qty = row.qty * flt(row.conversion_factor or 1)

    pick_list.locations = list(locations.values())
    pick_list.insert()

    # ---------------------------------------------------------
    # Create Bin Assignments
    # ---------------------------------------------------------

    bin_assignment_names = []

    for assignment in bin_assignment_data:
        assignment["pick_list"] = pick_list.name

        bin_assignment = frappe.get_doc(
            {
                "doctype": "Bin Assignment",
                **assignment,
            }
        )

        bin_assignment.insert()
        bin_assignment_names.append(bin_assignment.name)

    pick_list.submit()

    return {
        "pick_list": pick_list.name,
        "bin_assignments": bin_assignment_names,
    }


@frappe.whitelist()
def create_packing_box(data=None):
    if isinstance(data, str):
        data = json.loads(data)

    data = data or frappe.form_dict

    pick_list_id = data.get("pick_list")
    items = data.get("items") or []
    box_id = data.get("box_id")

    pick_list = frappe.get_doc("Pick List", pick_list_id)

    outward_warehouse = frappe.db.get_value(
        "Warehouse",
        {
            "main_warehouse": pick_list.source_warehouse,
            "is_sub_warehouse": 1,
            "warehouse_type": "Outward",
            "is_group": 0,
        },
        "name",
    )

    if not outward_warehouse:
        frappe.throw(
            _("Outward Warehouse not found for Source Warehouse {0}.").format(
                pick_list.source_warehouse
            )
        )

    packing_list_name = frappe.db.exists(
        "Packing List",
        {
            "pick_list": pick_list.name,
            "docstatus": 0,
        },
    )

    if packing_list_name:
        packing_list = frappe.get_doc("Packing List", packing_list_name)
    else:
        # First box: create the draft Packing List automatically.
        packing_list = frappe.new_doc("Packing List")
        packing_list.pick_list = pick_list.name
        packing_list.material_request = pick_list.material_request
        packing_list.company = pick_list.company
        packing_list.outward_warehouse = outward_warehouse
        packing_list.insert(ignore_permissions=True)

    # ---------------------------------------------------------
    # Create Box
    # ---------------------------------------------------------
    box = frappe.new_doc("Box")
    box.box_id = box_id
    box.packing_list = packing_list.name

    for item in items:
        item_code = item.get("item_code")
        qty = flt(item.get("qty"))

        box.append(
            "items",
            {
                "item": item_code,
                "qty": qty,
                "uom": item.get("uom"),
            },
        )

    box.total_items = len(box.items)
    box.insert(ignore_permissions=True)

    return {
        "packing_list": packing_list.name,
        "box_id": box.box_id,
        "status": "Draft",
    }


@frappe.whitelist()
def complete_packing_list(data=None):
    if isinstance(data, str):
        data = json.loads(data)

    data = data or frappe.form_dict

    packing_list_name = data.get("packing_list")
    packing_list = frappe.get_doc("Packing List", packing_list_name)

    if packing_list.docstatus == 1:
        return {
            "packing_list": packing_list.name,
            "status": "Submitted",
        }

    pick_list = frappe.get_doc("Pick List", packing_list.pick_list)

    # ---------------------------------------------------------
    # Prevent duplicate Outward Stock Entry
    # ---------------------------------------------------------
    existing = frappe.db.exists(
        "Stock Entry",
        {
            "packing_list": packing_list.name,
            "docstatus": 1,
            "add_to_transit": 0,
        },
    )

    if existing:
        stock_entry = frappe.get_doc("Stock Entry", existing)
    else:
        # -----------------------------------------------------
        # Create Outward Stock Entry from Pick List
        # -----------------------------------------------------
        stock_entry = frappe.get_doc(
            make_outward_stock_entry(
                frappe.as_json(pick_list.as_dict())
            )
        )

        stock_entry.pick_list = pick_list.name
        stock_entry.material_request = pick_list.material_request
        stock_entry.from_warehouse = pick_list.source_warehouse
        stock_entry.destination_warehouse = pick_list.destination_warehouse
        stock_entry.to_warehouse = packing_list.outward_warehouse
        stock_entry.add_to_transit = 0

        boxes = frappe.get_all(
            "Box",
            filters={
                "packing_list": packing_list.name,
                "docstatus": 0,
            },
            pluck="name",
        )

        packing_qty = {}

        if boxes:
            box_items = frappe.get_all(
                "Box Items",
                filters={
                    "parent": ["in", boxes],
                    "parenttype": "Box",
                    "parentfield": "items",
                },
                fields=[
                    "item",
                    "qty",
                ],
            )

            for item in box_items:
                packing_qty[item.item] = (
                    packing_qty.get(item.item, 0) + flt(item.qty)
                )

        for row in stock_entry.items:
            qty = packing_qty.get(row.item_code)

            if qty:
                row.qty = qty
                row.transfer_qty = qty
                row.s_warehouse = pick_list.source_warehouse
                row.t_warehouse = packing_list.outward_warehouse

        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()

    packing_list.submit()

    return {
        "packing_list": packing_list.name,
        "stock_entry": stock_entry.name,
        "status": "Submitted",
    }


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
        # -----------------------------------------------------
        # Transit STOCK ENTRY
        # -----------------------------------------------------
        transit_wh = data.get("transit_wh")
        pl_id = data.get("pl_id")

        pick_list = frappe.get_doc("Pick List", pl_id)

        packing_list = frappe.get_doc(
            "Packing List",
            {
                "pick_list": pick_list.name,
                "docstatus": 1,
            },
        )

        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.update({
            "stock_entry_type": "Material Transfer",
            "purpose": "Material Transfer",
            "company": pick_list.company,
            "from_warehouse": packing_list.outward_warehouse,
            "to_warehouse": transit_wh,
            "destination_warehouse": pick_list.destination_warehouse,
            "pick_list": pick_list.name,
            "material_request": pick_list.material_request,
            "add_to_transit": 1,
        })

        item_map = {
            item.get("item_code"): item
            for item in items
            if item.get("item_code")
        }

        for row in pick_list.locations:
            request = item_map.get(row.item_code)

            if not request:
                continue

            qty = flt(request.get("qty"))

            if qty <= 0:
                continue

            picked_qty = flt(row.qty)

            if qty > picked_qty:
                frappe.throw(
                    _(
                        "Transit quantity {0} for Item {1} cannot be greater "
                        "than picked quantity {2}."
                    ).format(
                        qty,
                        row.item_code,
                        picked_qty,
                    )
                )

            stock_entry.append(
                "items",
                {
                    "item_code": row.item_code,
                    "item_name": row.item_name,
                    "description": row.description,
                    "qty": qty,
                    "transfer_qty": qty,
                    "uom": request.get("uom") or row.uom,
                    "stock_uom": row.stock_uom,
                    "conversion_factor": row.conversion_factor or 1,
                    "s_warehouse": packing_list.outward_warehouse,
                    "t_warehouse": transit_wh,
                    "material_request_item": row.material_request_item,
                },
            )

        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()

        response = {
            "action": action,
            "stock_entry": stock_entry.name,
            "pick_list": pick_list.name,
            "material_request": pick_list.material_request,
            "from_warehouse": packing_list.outward_warehouse,
            "to_warehouse": transit_wh,
            "destination_warehouse": pick_list.destination_warehouse,
        }

    else:
        # ---------------------------------------------------------
        # End Transit STOCK ENTRY
        # ---------------------------------------------------------
        destination_wh = data.get("destination_wh")
        outward_se = data.get("stock_entry")
        outward = frappe.get_doc("Stock Entry", outward_se)

        stock_entry = frappe.get_doc(make_stock_in_entry(outward.name))
        stock_entry.from_warehouse = outward.to_warehouse
        stock_entry.to_warehouse = destination_wh
        stock_entry.destination_warehouse = None
        stock_entry.add_to_transit = 0
        stock_entry.pick_list = outward.pick_list
        stock_entry.material_request = outward.material_request

        request_map = {}

        for request in items:
            item_code = request.get("item_code")

            if not item_code:
                request_map.setdefault(item_code, []).append(request)

        original_rows = list(stock_entry.items)
        stock_entry.set("items", [])

        for row in original_rows:
            requests = request_map.get(row.item_code, [{}])

            for request in requests:
                qty = flt(request.get("qty", row.qty))

                if qty <= 0:
                    continue

                new_row = stock_entry.append("items", row.as_dict())
                new_row.qty = qty
                new_row.transfer_qty = qty
                new_row.s_warehouse = outward.to_warehouse
                new_row.t_warehouse = destination_wh
                new_row.pick_list_item = None

                if request.get("rack"):
                    new_row.rack = request.get("rack")

                if request.get("bin"):
                    new_row.bin = request.get("bin")

        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()

        response = {
            "action": action,
            "stock_entry": stock_entry.name,
            "outward_stock_entry": outward.name,
            "pick_list": outward.pick_list,
            "material_request": outward.material_request,
            "from_warehouse": outward.to_warehouse,
            "to_warehouse": destination_wh,
        }

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
