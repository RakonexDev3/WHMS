import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_stock_availability(item_code, company=None):
	if not item_code:
		frappe.throw(_("Item Code is required"))

	if not company:
		company = frappe.defaults.get_user_default("company")

	if not company:
		frappe.throw(_("Please set a default company"))

	warehouses = frappe.get_all(
		"Warehouse",
		filters={
			"company": company,
			"is_group": 0,
			"disabled": 0,
			"is_sub_warehouse": 0,
			"warehouse_type": ["!=", "Transit"],
		},
		fields=["name", "warehouse_name"],
		order_by="name",
	)

	if not warehouses:
		return []

	bin_data = frappe.db.sql(
		"""
		SELECT
			b.warehouse,
			w.main_warehouse,
			w.is_sub_warehouse,
			w.warehouse_type,
			b.actual_qty
		FROM `tabBin` b
		INNER JOIN `tabWarehouse` w
			ON w.name = b.warehouse
		WHERE
			b.item_code = %s
			AND w.company = %s
			AND w.disabled = 0
			AND IFNULL(w.warehouse_type, '') != 'Transit'
		""",
		(item_code, company),
		as_dict=True,
	)

	bin_dict = {}

	for row in bin_data:
		if (
			row.is_sub_warehouse
			and row.main_warehouse
			and row.warehouse_type == "Storage"
		):
			key = row.main_warehouse

		elif not row.is_sub_warehouse:
			key = row.warehouse

		else:
			continue

		bin_dict[key] = bin_dict.get(key, 0) + flt(row.actual_qty)

	stock_data = []

	for warehouse in warehouses:
		stock_qty = bin_dict.get(warehouse.name, 0.0)

		if stock_qty <= 0:
			continue

		stock_data.append(
			{
				"warehouse": warehouse.name,
				"warehouse_name": (
					warehouse.warehouse_name
					or warehouse.name
				),
				"stock_qty": stock_qty,
			}
		)

	stock_data.sort(
		key=lambda row: row["stock_qty"],
		reverse=True,
	)

	return stock_data


@frappe.whitelist()
def get_available_qty(item_code: str, warehouse: str) -> float:
	if not item_code or not warehouse:
		return 0.0

	return flt(
		frappe.db.get_value(
			"Bin",
			{
				"item_code": item_code,
				"warehouse": warehouse,
			},
			"actual_qty",
		)
		or 0
	)