import frappe


@frappe.whitelist(methods=["GET"])
def get_racking_box_item(box_id=None):
    """Get item details from Box."""

    box_id = box_id or frappe.form_dict.get("box_id")

    if not box_id:
        frappe.throw("Box ID is required.")

    box_name = frappe.db.get_value(
        "Box",
        {"box_id": box_id},
        "name"
    )

    if not box_name:
        box_name = frappe.db.get_value(
            "Box",
            {"name": box_id},
            "name"
        )

    if not box_name:
        frappe.throw(f"Box '{box_id}' does not exist.")

    box = frappe.get_doc("Box", box_name)

    if not frappe.has_permission("Box", "read", doc=box):
        frappe.throw(
            "You do not have permission to view this Box.",
            frappe.PermissionError
        )

    items = []

    for row in box.items:
        item_details = frappe.db.get_value(
            "Item",
            row.item,
            ["item_code", "item_name", "stock_uom"],
            as_dict=True
        )

        if not item_details:
            frappe.throw(
                f"Item '{row.item}' linked to Box '{box_id}' does not exist."
            )

        items.append({
            "item_code": item_details.item_code,
            "item_name": item_details.item_name,
            "qty": row.qty,
            "racked_qty": (
                row.get("racked_qty")
                if row.meta.has_field("racked_qty")
                else None
            ),
            "uom": row.uom or item_details.stock_uom
        })

    return {"items": items}