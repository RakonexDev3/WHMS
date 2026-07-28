import frappe

from warehouse_management.utils import get_managed_warehouses


def update_warehouse_user_permission(doc, method=None):
    """
    Maintain Warehouse User Permission from Employee based on 
    active_warehouse and allow_access_to_all_warehouses
    """

    if not frappe.db.get_single_value(
        "Warehouse Management Settings",
        "enable_warehouse_user_permission",
    ):
        return

    if not doc.user_id:
        return

    if "System Manager" in frappe.get_roles(doc.user_id):
        return

    existing_permissions = frappe.get_all(
        "User Permission",
        filters={
            "user": doc.user_id,
            "allow": "Warehouse",
        },
        fields=["name", "for_value"],
    )

    if doc.allow_access_to_all_warehouses or not doc.active_warehouse:

        for permission in existing_permissions:
            frappe.delete_doc(
                "User Permission",
                permission.name,
                ignore_permissions=True,
            )

        return

    allowed_warehouses = set(
        get_managed_warehouses(
            doc.active_warehouse,
            include_sub_warehouses=True,
        )
    )

    existing_by_warehouse = {
        permission.for_value: permission.name
        for permission in existing_permissions
    }

    for warehouse, permission_name in existing_by_warehouse.items():
        if warehouse not in allowed_warehouses:
            frappe.delete_doc(
                "User Permission",
                permission_name,
                ignore_permissions=True,
            )

    for warehouse in allowed_warehouses:
        if warehouse in existing_by_warehouse:
            continue

        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": doc.user_id,
                "allow": "Warehouse",
                "for_value": warehouse,
                "is_default": warehouse == doc.active_warehouse,
            }
        ).insert(ignore_permissions=True)