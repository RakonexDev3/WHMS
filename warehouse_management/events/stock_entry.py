import frappe


def update_material_request_in_transit(doc, method=None):
    if not doc.pick_list or not doc.material_request:
        return

    frappe.db.set_value(
        "Material Request",
        doc.material_request,
        "workflow_state",
        "In Transit",
    )


def create_bin_assignments_on_stock_entry_submit(doc, method):
    """Create Bin Assignment records for Stock Entry items having Rack & Bin."""

    if doc.stock_entry_type != "Material Transfer":
        return

    for item in doc.items:
        if not (item.rack and item.bin):
            continue

        if frappe.db.exists(
            "Bin Assignment",
            {
                "stock_entry": doc.name,
                "item": item.item_code,
                "bin": item.bin,
            },
        ):
            continue

        frappe.get_doc({
            "doctype": "Bin Assignment",
            "assignment_type": "Placing",
            "stock_entry": doc.name,
            "material_request": doc.material_request,
            "item": item.item_code,
            "rack": item.rack,
            "bin": item.bin,
            "uom": item.uom,
            "quantity": item.transfer_qty or item.qty,
            "expiry_date": item.get("expiry_date"),
            "doa": item.get("date_of_assignment"),
            "batch_no": item.get("batch_no"),
            "notes": f"Auto-created from Stock Entry {doc.name}",
        }).insert(ignore_permissions=True)