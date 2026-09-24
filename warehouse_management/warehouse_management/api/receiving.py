import json

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.stock.doctype.stock_entry.stock_entry import make_stock_in_entry


@frappe.whitelist()
def get_transit_packing_lists(destination_warehouse):
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
            "per_transferred",
        ],
    )

    return [
        {
            "material_request": entry.material_request,
            "transit_stock_entry": entry.name,
            "from_warehouse": entry.from_warehouse,
            "transit_warehouse": entry.to_warehouse,
            "status": (
                "To Receive"
                if entry.per_transferred == 0
                else "Partially Received"
            ),
        }
        for entry in stock_entries
    ]


@frappe.whitelist()
def get_transit_packing_list_details(transit_stock_entry):
    transit = frappe.get_doc("Stock Entry", transit_stock_entry)

    packing_list = frappe.db.get_value(
        "Packing List",
        {"pick_list": transit.pick_list},
        "name",
    )

    packing_list_items = []

    if packing_list:
        packing_list_items = frappe.get_all(
            "Packing List Box",
            filters={
                "parent": packing_list,
                "parenttype": "Packing List",
                "parentfield": "items",
            },
            fields=[
                "box_id",
                "total_item",
                "is_received",
            ],
            order_by="idx asc",
        )

    driver = frappe.db.get_value(
        "User",
        transit.owner,
        "full_name",
    )

    return {
        "material_request": transit.material_request,
        "driver": driver,
        "packing_list": packing_list,
        "total_box_count": len(packing_list_items),
        "items": packing_list_items,
    }


@frappe.whitelist()
def create_end_transit_stock_entry(data=None):
    """
    Create End Transit Stock Entry on receiving boxes.
    action:
        full_receive    -> receive all items
        partial_receive -> receive items from selected boxes
    """

    if isinstance(data, str):
        data = json.loads(data)

    data = data or frappe.form_dict

    transit_se = data.get("transit_stock_entry")
    destination_wh = data.get("destination_wh")
    select_all = data.get("select_all", 0)
    action = "full_receive" if select_all else "partial_receive"
    box_ids = data.get("box_ids") or []

    if isinstance(box_ids, str):
        box_ids = json.loads(box_ids)

    transit = frappe.get_doc("Stock Entry", transit_se)

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
            _("Bay warehouse not found for {0}.").format(destination_wh)
        )

    stock_entry = frappe.get_doc(make_stock_in_entry(transit.name))
    stock_entry.from_warehouse = transit.to_warehouse
    stock_entry.to_warehouse = bay_warehouse
    stock_entry.destination_warehouse = None
    stock_entry.add_to_transit = 0
    stock_entry.pick_list = transit.pick_list
    stock_entry.material_request = transit.material_request

    # ---------------------------------------------------------
    # FULL RECEIVE
    # ---------------------------------------------------------

    if action == "full_receive":
        stock_entry.submit()

        # Mark all boxes as received
        frappe.db.set_value(
            "Packing List Box",
            {
                "parent": frappe.db.get_value(
                    "Packing List",
                    {"pick_list": transit.pick_list},
                    "name",
                )
            },
            "is_received",
            1,
        )

        return {
            "end_transit_stock_entry": stock_entry.name,
            "material_request": transit.material_request,
            "from_warehouse": transit.to_warehouse,
            "to_warehouse": bay_warehouse,
        }

    # ---------------------------------------------------------
    # PARTIAL RECEIVE
    # ---------------------------------------------------------

    if not box_ids:
        frappe.throw(_("At least one box is required."))

    packing_list = frappe.db.get_value(
        "Packing List",
        {"pick_list": transit.pick_list},
        "name",
    )

    if not packing_list:
        frappe.throw(
            _("Packing List not found for Pick List {0}.").format(
                transit.pick_list
            )
        )

    packing_list_doc = frappe.get_doc(
        "Packing List",
        packing_list,
    )

    selected_box_ids = set(box_ids)

    received_items = {}
    selected_boxes = []

    for packing_box in packing_list_doc.items:

        if packing_box.box_id not in selected_box_ids:
            continue

        if packing_box.is_received:
            frappe.throw(
                _("Box {0} has already been received.")
                .format(packing_box.box_id)
            )

        selected_boxes.append(packing_box)

        box = frappe.get_doc(
            "Box",
            packing_box.box_id,
        )

        for row in box.items:
            received_items[row.item] = (
                received_items.get(row.item, 0)
                + flt(row.qty)
            )

    if not received_items:
        frappe.throw(_("No items found in the selected boxes."))

    for row in list(stock_entry.items):
        received_qty = received_items.get(row.item_code, 0)

        if not received_qty:
            stock_entry.remove(row)
            continue

        if received_qty > flt(row.qty):
            frappe.throw(
                _(
                    "Received quantity for Item {0} cannot "
                    "exceed transit quantity."
                ).format(row.item_code)
            )

        row.qty = received_qty
        row.transfer_qty = received_qty

    if not stock_entry.items:
        frappe.throw(_("No items available for receiving."))

    stock_entry.submit()

    for packing_box in selected_boxes:
        frappe.db.set_value(
            "Packing List Box",
            packing_box.name,
            "is_received",
            1,
        )

    return {
        "end_transit_stock_entry": stock_entry.name,
        "material_request": transit.material_request,
        "from_warehouse": transit.to_warehouse,
        "to_warehouse": bay_warehouse,
    }
