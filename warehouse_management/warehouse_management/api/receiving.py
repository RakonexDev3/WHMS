import json

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.stock.doctype.stock_entry.stock_entry import make_stock_in_entry


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
def get_transit_stock_entry_items(stock_entry):
    transit = frappe.get_doc("Stock Entry", stock_entry)

    end_transit = frappe.db.get_value(
        "Stock Entry",
        {
            "outgoing_stock_entry": transit.name,
            "add_to_transit": 0,
            "docstatus": ["<", 2],
        },
        "name",
        order_by="modified desc",
    )

    end_transit_doc = (
        frappe.get_doc("Stock Entry", end_transit)
        if end_transit
        else None
    )

    items = []

    for row in transit.items:
        received_qty = 0

        if end_transit_doc:
            received_qty = sum(
                flt(item.qty)
                for item in end_transit_doc.items
                if item.ste_detail == row.name
            )

        if received_qty == 0:
            status = "Pending"
        elif received_qty < flt(row.qty):
            status = "Partial"
        else:
            status = "Created"

        items.append({
            "item_code": row.item_code,
            "item_name": row.item_name,
            "uom": row.uom,
            "transit_qty": row.qty,
            "received_qty": received_qty,
            "status": status,
        })

    return {
        "material_request": transit.material_request,
        "stock_entry": transit.name,
        "end_transit_stock_entry": end_transit,
        "items": items,
    }


@frappe.whitelist()
def create_end_transit_stock_entry(data=None):
    """
    Create End Transit draft Stock Entry on receiving items.
    """

    if isinstance(data, str):
        data = json.loads(data)

    data = data or frappe.form_dict

    outward_se = data.get("stock_entry")
    destination_wh = data.get("destination_wh")
    item_code = data.get("item_code")
    qty = flt(data.get("qty"))
    rack = data.get("rack")
    bin = data.get("bin")

    outward = frappe.get_doc("Stock Entry", outward_se)

    # ---------------------------------------------------------
    # Find Bay Warehouse
    # ---------------------------------------------------------

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
            _("Bay warehouse not found for {0}.")
            .format(destination_wh)
        )

    # ---------------------------------------------------------
    # Find Existing Draft End Transit Stock Entry
    # ---------------------------------------------------------

    existing_stock_entry = frappe.db.exists(
        "Stock Entry",
        {
            "material_request": outward.material_request,
            "add_to_transit": 0,
            "docstatus": 0,
            "from_warehouse": outward.to_warehouse,
        },
    )

    if existing_stock_entry:
        stock_entry = frappe.get_doc("Stock Entry", existing_stock_entry)
    else:
        stock_entry = frappe.get_doc(make_stock_in_entry(outward.name))
        stock_entry.from_warehouse = outward.to_warehouse
        stock_entry.to_warehouse = bay_warehouse
        stock_entry.destination_warehouse = None
        stock_entry.add_to_transit = 0
        stock_entry.pick_list = outward.pick_list
        stock_entry.material_request = outward.material_request
        stock_entry.set("items", [])

    transit_qty = sum(
        flt(row.qty)
        for row in outward.items
        if row.item_code == item_code
    )

    received_qty = sum(
        flt(row.qty)
        for row in stock_entry.items
        if row.item_code == item_code
    )

    total_qty = received_qty + qty

    if total_qty > transit_qty:
        frappe.throw(
            _(
                "Received quantity for Item {0} cannot be "
                "greater than Transit quantity. "
                "Transit: {1}, Already Received: {2}, "
                "Current: {3}."
            ).format(
                item_code,
                transit_qty,
                received_qty,
                qty,
            )
        )

    existing_row = next(
        (row for row in stock_entry.items if row.item_code == item_code),
        None
    )

    if existing_row:
        existing_row.qty = total_qty
        existing_row.transfer_qty = total_qty

        if rack:
            existing_row.rack = rack
        if bin:
            existing_row.bin = bin

    else:
        transit_entry = make_stock_in_entry(outward.name)
        
        transit_row = next(
            row for row in transit_entry.items
            if row.item_code == item_code
        )

        new_row = stock_entry.append("items", {})
        new_row.update(transit_row.as_dict())

        new_row.qty = qty
        new_row.transfer_qty = qty
        new_row.s_warehouse = outward.to_warehouse
        new_row.t_warehouse = bay_warehouse
        new_row.pick_list_item = None

        if rack:
            new_row.rack = rack
        if bin:
            new_row.bin = bin

    if stock_entry.is_new():
        stock_entry.insert(ignore_permissions=True)
    else:
        stock_entry.save(ignore_permissions=True)

    return {
        "stock_entry": stock_entry.name,
        "material_request": outward.material_request,
        "from_warehouse": outward.to_warehouse,
        "to_warehouse": bay_warehouse,
        "status": "Draft",
    }


@frappe.whitelist()
def complete_end_transit_stock_entry(data=None):
    """
    Validate and submit the draft End Transit Stock Entry.
    """

    if isinstance(data, str):
        data = json.loads(data)

    data = data or frappe.form_dict

    stock_entry_name = data.get("stock_entry")
    stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)

    if stock_entry.docstatus == 1:
        return {
            "stock_entry": stock_entry.name,
            "status": "Submitted",
        }

    transit_stock_entry = frappe.db.get_value(
        "Stock Entry",
        {
            "material_request": stock_entry.material_request,
            "add_to_transit": 1,
            "docstatus": 1,
        },
        "name",
        order_by="modified desc",
    )

    transit_stock_entry = frappe.get_doc("Stock Entry", transit_stock_entry)

    transit_qty = {}
    received_qty = {}

    for row in transit_stock_entry.items:
        transit_qty[row.item_code] = (
            transit_qty.get(row.item_code, 0) + flt(row.qty)
        )

    for row in stock_entry.items:
        received_qty[row.item_code] = (
            received_qty.get(row.item_code, 0) + flt(row.qty)
        )

    for item_code, required_qty in transit_qty.items():
        received = received_qty.get(item_code, 0)

        if received != required_qty:
            frappe.throw(
                _(
                    "Received quantity for Item {0} does not "
                    "match Transit quantity. Required: {1}, Received: {2}."
                ).format(item_code, required_qty,received)
            )

    stock_entry.submit()

    return {
        "stock_entry": stock_entry.name,
        "status": "Submitted",
    }
