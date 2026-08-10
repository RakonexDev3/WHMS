import frappe
from frappe import _


def validate_material_requests(doc, method=None):
    """Only Approved Material Requests can be linked to a Pick List."""
    material_requests = {
        row.material_request
        for row in doc.locations
        if row.material_request
    }

    if not material_requests:
        return

    invalid_material_requests = frappe.get_all(
        "Material Request",
        filters={
            "name": ["in", list(material_requests)],
            "workflow_state": ["!=", "Approved"],
        },
        fields=["name", "workflow_state"],
    )

    if invalid_material_requests:
        frappe.throw(
            _("Only Approved Material Requests can be linked to a Pick List.")
        )


def update_material_requests_as_picked(doc, method=None):
    """Set linked Material Requests from Approved to Picked."""
    material_requests = {
        row.material_request
        for row in doc.locations
        if row.material_request
    }

    if not material_requests:
        return

    for material_request in material_requests:
        frappe.db.set_value(
            "Material Request",
            material_request,
            "workflow_state",
            "Picked",
            update_modified=False,
        )


def revert_material_requests_to_approved(doc, method=None):
    """Revert linked Material Requests from Picked to Approved when Pick List is cancelled."""

    material_requests = {
        row.material_request
        for row in doc.locations
        if row.material_request
    }

    if not material_requests:
        return

    for material_request in material_requests:
        current_state = frappe.db.get_value(
            "Material Request",
            material_request,
            "workflow_state",
        )

        if current_state == "Picked":
            frappe.db.set_value(
                "Material Request",
                material_request,
                "workflow_state",
                "Approved",
                update_modified=False,
            )


def delete_bin_assignments_on_pick_list_cancel(doc, method=None):
    bin_assignments = frappe.get_all(
        "Bin Assignment",
        filters={
            "pick_list": doc.name,
            "assignment_type": "Picking",
        },
        pluck="name",
    )

    for bin_assignment in bin_assignments:
        frappe.delete_doc(
            "Bin Assignment",
            bin_assignment,
            ignore_permissions=True,
        )