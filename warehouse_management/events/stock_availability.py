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
def get_available_qty_for_items(item_codes, warehouse):
	"""Return total stock from the selected warehouse and its transaction-enabled sub-warehouses."""
	if not item_codes or not warehouse:
		return {}

	if isinstance(item_codes, str):
		item_codes = frappe.parse_json(item_codes)

	warehouses = frappe.get_all(
		"Warehouse",
		filters={
			"disabled": 0,
			"include_in_transaction": 1,
		},
		fields=["name", "is_sub_warehouse", "main_warehouse"],
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
		return {item_code: 0 for item_code in item_codes}

	rows = frappe.db.sql(
		"""
		SELECT
			item_code,
			COALESCE(SUM(actual_qty), 0) AS actual_qty
		FROM `tabBin`
		WHERE item_code IN %(item_codes)s
		AND warehouse IN %(warehouses)s
		GROUP BY item_code
		""",
		{
			"item_codes": item_codes,
			"warehouses": warehouse_names,
		},
		as_dict=True,
	)

	stock_map = {
		row.item_code: row.actual_qty
		for row in rows
	}

	return {
		item_code: stock_map.get(item_code, 0)
		for item_code in item_codes
	}

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