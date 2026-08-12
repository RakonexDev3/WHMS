import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_stock_availability(item_code, company=None, warehouse=None):
	"""Return stock separately for the selected warehouse and its included sub-warehouses."""
	if not item_code:
		frappe.throw(_("Item Code is required"))

	if not warehouse:
		return []

	if not company:
		company = frappe.defaults.get_user_default("company")

	if not company:
		frappe.throw(_("Please set a default company"))

	warehouse_data = frappe.db.get_value(
		"Warehouse",
		warehouse,
		[
			"name",
			"warehouse_name",
			"company",
			"is_sub_warehouse",
			"disabled",
			"include_in_transaction",
		],
		as_dict=True,
	)

	if (
		not warehouse_data
		or warehouse_data.company != company
		or warehouse_data.disabled
		or not warehouse_data.include_in_transaction
	):
		return []

	warehouses = frappe.get_all(
		"Warehouse",
		filters={
			"company": company,
			"disabled": 0,
			"include_in_transaction": 1,
		},
		fields=[
			"name",
			"warehouse_name",
			"is_sub_warehouse",
			"main_warehouse",
			"include_in_transaction",
		],
		order_by="name",
	)

	allowed_warehouses = [
		row
		for row in warehouses
		if row.name == warehouse
		or (
			row.is_sub_warehouse
			and row.main_warehouse == warehouse
		)
	]

	if not allowed_warehouses:
		return []

	bin_data = frappe.get_all(
		"Bin",
		filters={
			"item_code": item_code,
			"warehouse": [
				"in",
				[row.name for row in allowed_warehouses],
			],
		},
		fields=[
			"warehouse",
			"actual_qty",
		],
	)

	bin_dict = {
		row.warehouse: flt(row.actual_qty)
		for row in bin_data
	}

	stock_data = []

	for row in allowed_warehouses:
		stock_qty = bin_dict.get(row.name, 0.0)

		if stock_qty <= 0:
			continue

		stock_data.append(
			{
				"warehouse": row.name,
				"warehouse_name": (
					row.warehouse_name
					or row.name
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
	"""Return total stock from the selected warehouse and its transaction-enabled sub-warehouses."""
	if not item_code or not warehouse:
		return 0.0

	warehouses = frappe.get_all(
		"Warehouse",
		filters={
			"disabled": 0,
			"include_in_transaction": 1,
		},
		fields=[
			"name",
			"is_sub_warehouse",
			"main_warehouse",
		],
	)

	warehouse_names = [
		row.name
		for row in warehouses
		if row.name == warehouse
		or (
			row.is_sub_warehouse
			and row.main_warehouse == warehouse
		)
	]

	if not warehouse_names:
		return 0.0

	return flt(
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(actual_qty), 0)
			FROM `tabBin`
			WHERE item_code = %s
			AND warehouse IN %s
			""",
			(item_code, warehouse_names),
		)[0][0]
	)


@frappe.whitelist()
def get_active_warehouse():
	"""Return the active warehouse assigned to the current user's employee."""
	return frappe.db.get_value(
		"Employee",
		{
			"user_id": frappe.session.user,
			"status": "Active",
		},
		"active_warehouse",
	)