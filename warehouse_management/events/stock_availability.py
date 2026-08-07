import frappe
from frappe import _


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

	warehouse_names = [
		warehouse.name for warehouse in warehouses
	]

	bin_data = frappe.db.sql(
		"""
		SELECT
			warehouse,
			actual_qty
		FROM `tabBin`
		WHERE item_code = %s
			AND warehouse IN %s
		""",
		(item_code, warehouse_names),
		as_dict=True,
	)

	bin_dict = {
		row.warehouse: frappe.utils.flt(row.actual_qty)
		for row in bin_data
	}

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

	return frappe.utils.flt(
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