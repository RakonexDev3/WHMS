import frappe
from frappe import _


def notify_warehouse_manager(doc, method=None):
    if doc.material_request_type != "Material Transfer":
        return

    if not doc.has_value_changed("workflow_state"):
        return

    if doc.workflow_state == "Pending":
        notify_source_warehouse_manager(doc)

    elif doc.workflow_state in ("Approved", "Rejected"):
        notify_target_warehouse_manager(doc)


def notify_source_warehouse_manager(doc, method=None):
    """Notify Warehouse Managers when MR is pending for approval."""

    source_warehouses = {
        row.from_warehouse
        for row in doc.items
        if row.from_warehouse
    }

    if not source_warehouses:
        return

    employees = frappe.get_all(
        "Employee",
        filters={
            "status": "Active",
            "active_warehouse": ["is", "set"],
        },
        fields=["user_id", "active_warehouse"],
    )

    for employee in employees:
        if not employee.user_id:
            continue

        if "Warehouse Manager" not in frappe.get_roles(employee.user_id):
            continue

        if employee.active_warehouse not in source_warehouses:
            continue

        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"Material Request {doc.name} Requires Approval",
            "email_content": (
                f"Material Request {doc.name} is awaiting your approval. "
                "Please review and take the required action."
            ),
            "for_user": employee.user_id,
            "type": "Alert",
            "document_type": "Material Request",
            "document_name": doc.name
        }).insert(ignore_permissions=True)


def notify_target_warehouse_manager(doc, method=None):
    """
    Notify Warehouse Managers whose active_warehouse matches
    the target warehouse of the approved Material Request.
    """

    target_warehouses = {
        row.warehouse
        for row in doc.items
        if row.warehouse
    }

    if not target_warehouses:
        return

    employees = frappe.get_all(
        "Employee",
        filters={
            "status": "Active",
            "active_warehouse": ["in", list(target_warehouses)],
        },
        fields=["user_id", "active_warehouse"],
    )

    for employee in employees:
        if not employee.user_id:
            continue

        if "Warehouse Manager" not in frappe.get_roles(employee.user_id):
            continue

        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"Material Request {doc.name} {doc.workflow_state}",
            "email_content": (
                f"Material Request {doc.name} has been {doc.workflow_state}."
            ),
            "for_user": employee.user_id,
            "type": "Alert",
            "document_type": "Material Request",
            "document_name": doc.name
        }).insert(ignore_permissions=True)


def get_manager_details(user):
    return frappe.db.get_value(
        "Employee",
        {
            "user_id": user,
            "status": "Active",
        },
        ["active_warehouse", "allow_access_to_all_warehouses"],
        as_dict=True,
    )


def validate_warehouse_manager(doc, method=None):
    """Allow only the source Warehouse Manager to approve or reject."""

    if doc.material_request_type != "Material Transfer":
        return

    if not doc.has_value_changed("workflow_state"):
        return

    old_doc = doc.get_doc_before_save()

    if not old_doc or old_doc.workflow_state != "Pending":
        return

    if doc.workflow_state not in ("Approved", "Rejected"):
        return
    
    user = frappe.session.user

    if "Warehouse Manager" not in frappe.get_roles(user):
        return

    employee = get_manager_details(user)

    source_warehouses = {
        row.from_warehouse
        for row in doc.items
        if row.from_warehouse
    }

    if not employee or employee.active_warehouse not in source_warehouses:
        frappe.throw(_("You cannot approve or reject this Material Request."))


def get_permission_query_conditions(user=None):
    user = user or frappe.session.user

    if "Warehouse Manager" not in frappe.get_roles(user):
        return ""

    employee = get_manager_details(user)

    if not employee:
        return ""
    
    if employee.allow_access_to_all_warehouses:
        return ""
    
    if not employee.active_warehouse:
        return ""

    warehouse = frappe.db.escape(employee.active_warehouse)

    return f"""
        EXISTS (
            SELECT 1
            FROM `tabMaterial Request Item` AS mr_item
            WHERE
                mr_item.parent = `tabMaterial Request`.name
                AND mr_item.parenttype = 'Material Request'
                AND mr_item.warehouse = {warehouse}
        )
    """
