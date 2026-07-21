import frappe
from frappe.query_builder import DocType
from pypika.functions import Coalesce


def check_critical_stock():
    Item = DocType("Item")
    ItemReorder = DocType("Item Reorder")
    Bin = DocType("Bin")

    rows = (
        frappe.qb.from_(ItemReorder)
        .inner_join(Item)
        .on(Item.name == ItemReorder.parent)
        .left_join(Bin)
        .on(
            (Bin.item_code == Item.name)
            & (Bin.warehouse == ItemReorder.warehouse)
        )
        .select(
            Item.name.as_("item_code"),
            Item.item_name,
            ItemReorder.warehouse,
            ItemReorder.warehouse_reorder_level.as_("critical_qty"),
            Coalesce(Bin.actual_qty, 0).as_("current_stock"),
        )
        .where(Item.disabled == 0)
        .where(
            Coalesce(Bin.actual_qty, 0)
            <= ItemReorder.warehouse_reorder_level
        )
        .run(as_dict=True)
    )

    warehouse_data = {}

    for row in rows:
        warehouse_data.setdefault(
            row["warehouse"],
            []
        ).append(row)

    for warehouse, items in warehouse_data.items():
        send_notification(warehouse, items)


def send_notification(warehouse, items):
    employees = frappe.get_all(
        "Employee",
        filters={
            "active_warehouse": warehouse,
        },
        fields=["user_id"],
    )

    if not employees:
        return

    lines = [
        f"<b>{warehouse}</b>",
        "",
        "The following items are below critical stock:",
        "",
    ]

    for item in items:
        lines.append(
            f"• <b>{item['item_code']}</b> "
            f"(Current: {item['current_stock']}, "
            f"Critical: {item['critical_qty']})"
        )

    message = "<br>".join(lines)

    for employee in employees:
        roles = frappe.get_roles(frappe.session.user)

        if employee.user_id and "Warehouse Manager" in roles:
            frappe.get_doc(
                {
                    "doctype": "Notification Log",
                    "subject": f"Low Stock Alert - {warehouse}",
                    "email_content": message,
                    "for_user": employee.user_id,
                    "type": "Alert",
                }
            ).insert(ignore_permissions=True)