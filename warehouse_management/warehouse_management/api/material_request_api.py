import json

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from erpnext.stock.doctype.material_request.material_request import create_pick_list as make_pick_list
from erpnext.stock.doctype.pick_list.pick_list import create_stock_entry as make_outward_stock_entry
from erpnext.stock.doctype.stock_entry.stock_entry import make_stock_in_entry


@frappe.whitelist()
def get_material_requests(source_warehouse):
    material_requests = frappe.get_all(
        "Material Request",
        filters={
            "workflow_state": "Approved",
            "material_request_type": "Material Transfer",
            "set_from_warehouse": source_warehouse,
        },
        fields=["name", "set_from_warehouse", "set_warehouse"],
        order_by="modified desc",
    )

    if not material_requests:
        return {"data": []}

    mr_names = [mr.name for mr in material_requests]

    pick_lists = frappe.get_all(
        "Pick List",
        filters={
            "material_request": ["in", mr_names],
            "docstatus": ["<", 2],
        },
        fields=["name", "material_request", "modified"],
        order_by="modified desc",
    )

    pick_list_map = {}

    for row in pick_lists:
        if row.material_request not in pick_list_map:
            pick_list_map[row.material_request] = row.name

    return {
        "data": [
            {
                "mr_id": mr.name,
                "source_warehouse": mr.set_from_warehouse,
                "target_warehouse": mr.set_warehouse,
                "pick_list": pick_list_map.get(mr.name),
                "status": (
                    "In Progress"
                    if mr.name in pick_list_map
                    else "To Start"
                ),
            }
            for mr in material_requests
        ]
    }


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

    pick_lists = frappe.get_all(
        "Pick List",
        filters={
            "material_request": mr.name,
            "docstatus": ["<", 2],
        },
        fields=["name", "docstatus", "modified"],
        order_by="modified desc",
    )

    pick_list = pick_lists[0] if pick_lists else None
    picked_by_item = {}

    if pick_list:
        locations = frappe.get_all(
            "Pick List Item",
            filters={
                "parent": pick_list.name,
                "item_code": ["in", item_codes],
            },
            fields=["item_code", "qty"],
        )

        for row in locations:
            picked_by_item[row.item_code] = (
                picked_by_item.get(row.item_code, 0) + flt(row.qty)
            )

    return {
        "mr_id": mr.name,
        "warehouse": warehouse,
        "pick_list": pick_list.name if pick_list else None,
        "items": [
            {
                "item_code": row.item_code,
                "item_name": row.item_name,
                "req_qty": row.qty,
                "wh_stock_bal": stock_by_item.get(row.item_code, 0),
                "picked_qty": picked_by_item.get(row.item_code, 0),
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
    items = data.get("items") or []

    mr = frappe.get_doc("Material Request", mr_id)

    pick_list_name = frappe.db.exists(
        "Pick List",
        {
            "material_request": mr.name,
            "docstatus": 0,
        },
    )

    if pick_list_name:
        pick_list = frappe.get_doc("Pick List", pick_list_name)
    else:
        pick_list = make_pick_list(mr.name)
        pick_list.pick_manually = 1
        pick_list.source_warehouse = mr.set_from_warehouse
        pick_list.destination_warehouse = mr.set_warehouse
        pick_list.locations = []

    mr_qty = {}
    mr_items = {}

    for row in mr.items:
        mr_qty[row.item_code] = (
            mr_qty.get(row.item_code, 0) + flt(row.qty)
        )
        mr_items[row.item_code] = row

    picked_qty = {}

    for row in pick_list.locations:
        picked_qty[row.item_code] = (
            picked_qty.get(row.item_code, 0) + flt(row.qty)
        )

    requested_bins = {}
    current_qty = {}

    for item in items:
        item_code = item.get("item_code")
        bins = item.get("bins") or []

        for bin_row in bins:
            bin_name = bin_row.get("bin")
            qty = flt(bin_row.get("qty"))

            requested_bins[bin_name] = {
                "item_code": item_code,
                "qty": qty,
                "uom": bin_row.get("uom") or mr_items[item_code].uom,
            }

            current_qty[item_code] = (
                current_qty.get(item_code, 0) + qty
            )

    for item_code, qty in current_qty.items():
        total_qty = picked_qty.get(item_code, 0) + qty

        if total_qty > mr_qty[item_code]:
            frappe.throw(
                _(
                    "Picking quantity {0} for Item {1} cannot be greater "
                    "than Material Request quantity {2}."
                ).format(
                    total_qty,
                    item_code,
                    mr_qty[item_code],
                )
            )

    storage_bins = frappe.get_all(
        "Storage Bin",
        filters={"name": ["in", list(requested_bins)]},
        fields=["name", "rack", "assigned_item", "quantity", "status"],
    )

    storage_bin_map = {row.name: row for row in storage_bins}

    for bin_name, request in requested_bins.items():
        storage_bin = storage_bin_map.get(bin_name)

        if not storage_bin:
            frappe.throw(
                _("Storage Bin {0} does not exist.").format(bin_name)
            )

        if storage_bin.assigned_item != request["item_code"]:
            frappe.throw(
                _("Storage Bin {0} is not assigned to Item {1}.")
                .format(bin_name, request["item_code"])
            )

        if storage_bin.status != "Occupied":
            frappe.throw(
                _("Storage Bin {0} is not occupied.").format(bin_name)
            )

        if request["qty"] > flt(storage_bin.quantity):
            frappe.throw(
                _(
                    "Insufficient quantity in Storage Bin {0}. "
                    "Available: {1}, Requested: {2}"
                ).format(
                    bin_name,
                    storage_bin.quantity,
                    request["qty"],
                )
            )

    location_map = {row.item_code: row for row in pick_list.locations}

    for item_code, qty in current_qty.items():
        row = location_map.get(item_code)

        if row:
            row.qty += qty
            row.stock_qty = row.qty * flt(row.conversion_factor or 1)
            continue

        mr_item = mr_items[item_code]

        pick_list.append(
            "locations",
            {
                "item_code": item_code,
                "item_name": mr_item.item_name,
                "description": mr_item.description,
                "qty": qty,
                "stock_qty": qty * flt(mr_item.conversion_factor or 1),
                "uom": mr_item.uom,
                "stock_uom": mr_item.stock_uom,
                "conversion_factor": mr_item.conversion_factor or 1,
                "warehouse": mr.set_from_warehouse,
                "material_request": mr.name,
                "material_request_item": mr_item.name,
            },
        )

    pick_list.pick_manually = 1
    pick_list.source_warehouse = mr.set_from_warehouse
    pick_list.destination_warehouse = mr.set_warehouse

    if pick_list.is_new():
        pick_list.insert(ignore_permissions=True)
    else:
        pick_list.save(ignore_permissions=True)

    bin_assignment_names = []

    for bin_name, request in requested_bins.items():
        storage_bin = storage_bin_map[bin_name]

        bin_assignment = frappe.get_doc({
            "doctype": "Bin Assignment",
            "item": request["item_code"],
            "uom": request["uom"],
            "rack": storage_bin.rack,
            "bin": bin_name,
            "quantity": -request["qty"],
            "doa": nowdate(),
            "assignment_type": "Picking",
            "material_request": mr.name,
            "pick_list": pick_list.name,
        })

        bin_assignment.insert(ignore_permissions=True)
        bin_assignment_names.append(bin_assignment.name)

    return {
        "pick_list": pick_list.name,
        "bin_assignments": bin_assignment_names,
        "status": "Draft",
    }


@frappe.whitelist()
def complete_picking(pick_list):
    pick_list = frappe.get_doc("Pick List", pick_list)
    mr = frappe.get_doc("Material Request", pick_list.material_request)

    required = {}
    picked = {}

    for row in mr.items:
        required[row.item_code] = (
            required.get(row.item_code, 0) + flt(row.qty)
        )

    for row in pick_list.locations:
        picked[row.item_code] = (
            picked.get(row.item_code, 0) + flt(row.qty)
        )

    for item_code, required_qty in required.items():
        picked_qty = picked.get(item_code, 0)

        if picked_qty != required_qty:
            frappe.throw(
                _(
                    "Picking is incomplete for Item {0}. "
                    "Required: {1}, Picked: {2}."
                ).format(item_code, required_qty, picked_qty)
            )

    pick_list.submit()

    return {
        "pick_list": pick_list.name,
        "status": "Submitted",
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

        for row in pick_list.locations:
            qty = flt(row.qty)

            if qty <= 0:
                continue

            stock_entry.append(
                "items",
                {
                    "item_code": row.item_code,
                    "item_name": row.item_name,
                    "description": row.description,
                    "qty": qty,
                    "transfer_qty": qty,
                    "uom": row.uom,
                    "stock_uom": row.stock_uom,
                    "conversion_factor": row.conversion_factor or 1,
                    "s_warehouse": packing_list.outward_warehouse,
                    "t_warehouse": transit_wh,
                    "material_request_item": row.material_request_item,
                },
            )

        if not stock_entry.items:
            frappe.throw(
                _("No valid items found in Pick List {0}.").format(
                    pick_list.name
                )
            )

        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()

        response = {
            "stock_entry": stock_entry.name,
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

        bay_warehouse = frappe.db.get_value(
            "Warehouse",
            {
                "main_warehouse": destination_wh,
                "warehouse_type": "Bay",
                "is_sub_warehouse": 1,
            },
            "name",
        )

        if not bay_warehouse:
            frappe.throw(
                _("Bay warehouse not found for {0}").format(destination_wh)
            )

        stock_entry = frappe.get_doc(make_stock_in_entry(outward.name))
        stock_entry.from_warehouse = outward.to_warehouse
        stock_entry.to_warehouse = bay_warehouse
        stock_entry.destination_warehouse = None
        stock_entry.add_to_transit = 0
        stock_entry.pick_list = outward.pick_list
        stock_entry.material_request = outward.material_request

        request_map = {}

        for request in items:
            item_code = request.get("item_code")

            if item_code:
                request_map.setdefault(item_code, []).append(request)

        original_rows = list(stock_entry.items)
        stock_entry.set("items", [])

        for row in original_rows:
            requests = request_map.get(row.item_code, [{}])

            for request in requests:
                qty = flt(request.get("qty", row.qty))

                if qty <= 0:
                    continue

                new_row = stock_entry.append("items", {})
                new_row.update(row.as_dict())
                new_row.qty = qty
                new_row.transfer_qty = qty
                new_row.s_warehouse = outward.to_warehouse
                new_row.t_warehouse = bay_warehouse
                new_row.pick_list_item = None

                if request.get("rack"):
                    new_row.rack = request.get("rack")

                if request.get("bin"):
                    new_row.bin = request.get("bin")

        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()

        response = {
            "stock_entry": stock_entry.name,
            "material_request": outward.material_request,
            "from_warehouse": outward.to_warehouse,
            "to_warehouse": bay_warehouse,
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
            "material_request",
            "from_warehouse",
            "to_warehouse",
        ],
    )

    return [
        {
            "stock_entry": entry.name,
            "material_request": entry.material_request,
            "from_warehouse": entry.from_warehouse,
            "transit_warehouse": entry.to_warehouse,
        }
        for entry in stock_entries
    ]


@frappe.whitelist()
def get_pick_lists():
    """Return open Pick Lists for the logged-in Picker's active warehouse."""

    if "Picker" not in frappe.get_roles(frappe.session.user):
        frappe.throw(_("Only users with Picker role can access Pick Lists."))

    active_warehouse = frappe.db.get_value(
        "Employee",
        {"user_id": frappe.session.user},
        "active_warehouse",
    )

    if not active_warehouse:
        frappe.throw(_("Active Warehouse is not set for the user."))

    pick_lists = frappe.get_all(
        "Pick List",
        filters={
            "docstatus": 1,
            "status": "Open",
            "source_warehouse": active_warehouse,
        },
        order_by="modified desc",
    )

    if not pick_lists:
        return {"data": []}

    pick_list_names = [row.name for row in pick_lists]

    packing_lists = frappe.get_all(
        "Packing List",
        filters={
            "pick_list": ["in", pick_list_names],
        },
        fields=["name", "pick_list", "docstatus"],
        order_by="creation desc",
    )

    packing_list_map = {}

    for row in packing_lists:
        if row.pick_list not in packing_list_map:
            packing_list_map[row.pick_list] = row

    result = []

    for pick_list in pick_lists:
        packing_list = packing_list_map.get(pick_list.name)

        if packing_list and packing_list.docstatus == 1:
            continue

        pick_list["packing_list"] = (
            packing_list.name if packing_list else None
        )
        pick_list["status"] = (
            "In Progress" if packing_list else "To Start"
        )

        result.append(pick_list)

    return {"data": result}


@frappe.whitelist()
def get_pick_list_items(pick_list):
    """Return Pick List items with packed qty."""

    packing_list = frappe.db.get_value(
        "Packing List",
        {
            "pick_list": pick_list,
        },
        "name",
        order_by="creation desc",
    )

    items = frappe.get_all(
        "Pick List Item",
        filters={
            "parent": pick_list,
            "parenttype": "Pick List",
            "parentfield": "locations",
        },
        fields=[
            "name",
            "item_code",
            "item_name",
            "qty",
            "picked_qty",
            "packed_qty",
            "uom",
        ],
        order_by="idx asc",
    )

    return {
        "packing_list": packing_list,
        "data": items,
    }


@frappe.whitelist()
def get_driver_packing_lists(source_warehouse):
    """Return submitted Packing Lists available for driver acceptance."""

    packing_lists = frappe.get_all(
        "Packing List",
        filters={
            "docstatus": 1,
            "source_warehouse": source_warehouse,
        },
        fields=["name"],
        order_by="modified desc",
    )

    if not packing_lists:
        return {"data": []}

    pick_list_names = {
        row.pick_list
        for row in packing_lists
        if row.pick_list
    }

    if not pick_list_names:
        return {"data": packing_lists}

    # Find Pick Lists that already have a submitted Add-to-Transit Stock Entry.
    transit_stock_entries = frappe.get_all(
        "Stock Entry",
        filters={
            "pick_list": ["in", list(pick_list_names)],
            "add_to_transit": 1,
            "docstatus": 1,
        },
        fields=["pick_list"],
    )

    transit_pick_lists = {
        row.pick_list
        for row in transit_stock_entries
        if row.pick_list
    }

    # Exclude Packing Lists whose Pick List is already moved to transit.
    result = [
        row
        for row in packing_lists
        if row.pick_list not in transit_pick_lists
    ]

    return {"data": result}