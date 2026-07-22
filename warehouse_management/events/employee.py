import frappe


def update_warehouse_user_permission(doc, method=None):
    """
    Create or remove Warehouse User Permission based on 
    active_warehouse and allow_access_to_all_warehouses
    """

    if not doc.user_id:
        return

    permission_name = frappe.db.get_value(
        "User Permission",
        {
            "user": doc.user_id,
            "allow": "Warehouse",
        },
        "name",
    )

    if doc.allow_access_to_all_warehouses or not doc.active_warehouse:

        if permission_name:
            frappe.delete_doc(
                "User Permission",
                permission_name,
                ignore_permissions=True,
            )

        return

    if permission_name:

        permission = frappe.get_doc(
            "User Permission",
            permission_name,
        )

        if permission.for_value == doc.active_warehouse:
            return

        permission.for_value = doc.active_warehouse
        permission.save(ignore_permissions=True)

        return

    frappe.get_doc({
        "doctype": "User Permission",
        "user": doc.user_id,
        "allow": "Warehouse",
        "for_value": doc.active_warehouse,
        "is_default": 1,
    }).insert(ignore_permissions=True)