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