import frappe


def update_material_request_workflow(doc, method=None):
    if not doc.material_request:
        return

    if doc.pick_list and doc.add_to_transit:
        frappe.db.set_value(
            "Material Request",
            doc.material_request,
            "workflow_state",
            "In Transit",
            update_modified=False,
        )

    elif doc.outgoing_stock_entry:
        frappe.db.set_value(
            "Material Request",
            doc.material_request,
            "workflow_state",
            "Completed",
            update_modified=False,
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
            "batch_no": item.get("batch_no"),
            "notes": f"Auto-created from Stock Entry {doc.name}",
        }).insert(ignore_permissions=True)


def delete_bin_assignments_on_stock_entry_cancel(doc, method):
    """Delete Bin Assignment records linked to a cancelled Stock Entry."""

    bin_assignments = frappe.get_all(
        "Bin Assignment",
        filters={
            "stock_entry": doc.name
        },
        pluck="name"
    )

    for name in bin_assignments:
        frappe.delete_doc(
            "Bin Assignment",
            name,
            ignore_permissions=True
        )


def revert_material_request_workflow(doc, method=None):
    """Revert Material Request workflow state when a Stock Entry is cancelled."""

    if not doc.material_request:
        return

    material_request = doc.material_request

    current_state = frappe.db.get_value(
        "Material Request",
        material_request,
        "workflow_state",
    )

    if doc.pick_list and doc.add_to_transit:
        if current_state == "In Transit":
            frappe.db.set_value(
                "Material Request",
                material_request,
                "workflow_state",
                "Picked",
                update_modified=False,
            )

    elif doc.outgoing_stock_entry:
        if current_state == "Completed":
            frappe.db.set_value(
                "Material Request",
                material_request,
                "workflow_state",
                "In Transit",
                update_modified=False,
            )
