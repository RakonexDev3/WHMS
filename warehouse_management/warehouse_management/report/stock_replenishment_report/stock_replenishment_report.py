# Copyright (c) 2026, Rakonex and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import parse_json
from frappe.query_builder import DocType
from pypika.functions import Coalesce

from warehouse_management.utils import get_managed_warehouses


def execute(filters=None):
    filters = filters or {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {
            "label": "Item",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150,
        },
        {
            "label": "Item Name",
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": "Warehouse",
            "fieldname": "warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 180,
        },
        {
            "label": "Critical Qty",
            "fieldname": "critical_qty",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": "Current Stock",
            "fieldname": "current_stock",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": "Reorder Qty",
            "fieldname": "reorder_qty",
            "fieldtype": "Float",
            "width": 120,
        },
        {
            "label": "Stock UOM",
            "fieldname": "stock_uom",
            "fieldtype": "Link",
            "options": "UOM",
            "width": 120,
        },
    ]


def get_data(filters):
    Item = DocType("Item")
    ItemReorder = DocType("Item Reorder")
    Bin = DocType("Bin")
    Warehouse = DocType("Warehouse")

    query = (
        frappe.qb.from_(ItemReorder)
        .inner_join(Item)
        .on(Item.name == ItemReorder.parent)
        .inner_join(Warehouse)
        .on(Warehouse.name == ItemReorder.warehouse)
        .left_join(Bin)
        .on(
            (Bin.item_code == Item.name)
            & (Bin.warehouse == ItemReorder.warehouse)
        )
        .select(
            Item.name.as_("item_code"),
            Item.item_name,
            Item.stock_uom,
            ItemReorder.warehouse,
            ItemReorder.warehouse_reorder_level.as_("critical_qty"),
            ItemReorder.warehouse_reorder_qty.as_("reorder_qty"),
            Coalesce(Bin.actual_qty, 0).as_("current_stock"),
        )
        .where(Item.disabled == 0)
        .where(Warehouse.disabled == 0)
        .where(Warehouse.is_sub_warehouse == 0)
    )

    roles = frappe.get_roles(frappe.session.user)

    if "System Manager" in roles:
        pass

    elif "Warehouse Manager" in roles:
        employee = frappe.db.get_value(
            "Employee",
            {
                "user_id": frappe.session.user,
                "status": "Active",
            },
            ["active_warehouse", "allow_access_to_all_warehouses"],
            as_dict=True,
        )

        if not employee:
            return []

        if not employee.allow_access_to_all_warehouses:
            if not employee.active_warehouse:
                return []

            allowed_warehouses = get_managed_warehouses(employee.active_warehouse)

            if not allowed_warehouses:
                return []

            query = query.where(
                ItemReorder.warehouse.isin(allowed_warehouses)
            )
    else:
        return []

    if filters.get("warehouse"):
        warehouses = get_managed_warehouses(filters["warehouse"])

        if not warehouses:
            return []

        query = query.where(
            ItemReorder.warehouse.isin(warehouses)
        )

    rows = query.run(as_dict=True)

    if filters.get("critical_only"):
        rows = [
            row
            for row in rows
            if row["current_stock"] <= row["critical_qty"]
        ]

    return rows


@frappe.whitelist()
def get_material_request(items):
    if isinstance(items, str):
        items = parse_json(items)

    target_warehouses = {
        row.get("warehouse")
        for row in items
        if row.get("warehouse")
    }

    target_warehouse = next(iter(target_warehouses))

    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Material Transfer"
    mr.set_warehouse = target_warehouse

    for row in items:
        mr.append(
            "items",
            {
                "item_code": row["item_code"],
                "warehouse": target_warehouse,
                "qty": row["reorder_qty"],
                "stock_uom": row["stock_uom"],
                "uom": row["stock_uom"],
            },
        )

    return mr.as_dict()


@frappe.whitelist()
def get_warehouse_query(doctype, txt, searchfield, start, page_len, filters):
    roles = frappe.get_roles(frappe.session.user)

    if "System Manager" not in roles and "Warehouse Manager" not in roles:
        return []

    warehouse_filters = {
        "disabled": 0,
        "is_sub_warehouse": 0,
    }

    if "System Manager" not in roles:
        employee = frappe.db.get_value(
            "Employee",
            {
                "user_id": frappe.session.user,
                "status": "Active",
            },
            ["active_warehouse", "allow_access_to_all_warehouses"],
            as_dict=True,
        )

        if not employee:
            return []

        if not employee.allow_access_to_all_warehouses:
            if not employee.active_warehouse:
                return []

            warehouse_filters["name"] = employee.active_warehouse

    if txt:
        warehouse_filters["name"] = ["like", f"%{txt}%"]

    warehouses = frappe.get_all(
        "Warehouse",
        filters=warehouse_filters,
        pluck="name",
        order_by="name",
        limit_start=start,
        limit_page_length=page_len,
    )

    return [(warehouse,) for warehouse in warehouses]