
import frappe

@frappe.whitelist(methods=["POST"])
def stock_repack_from_bay():
	"""
	Create a Draft Stock Entry (Repack).

	Request:
	{
		"source_warehouse": "Bay Main - HT",
		"source_item_code": "TRU-2297512",
		"source_item_qty": 10,
		"target_items": [
			{
				"target_warehouse": "Main - HT",
				"target_item_code": "TRU-2297512-RED",
				"target_item_qty": 4
			}
		]
	}
	"""

	try:
		data = frappe.local.request.get_json()

		source_warehouse = data.get("source_warehouse")
		source_item_code = data.get("source_item_code")
		source_item_qty = data.get("source_item_qty")
		target_items = data.get("target_items", [])

		# --------------------------------------------------
		# Validations
		# --------------------------------------------------
		if not source_warehouse:
			frappe.throw("source_warehouse is required")

		if not source_item_code:
			frappe.throw("source_item_code is required")

		if not source_item_qty:
			frappe.throw("source_item_qty is required")

		if not target_items:
			frappe.throw("target_items is required")

		if not frappe.db.exists("Warehouse", source_warehouse):
			frappe.throw("Warehouse {0} does not exist").format(source_warehouse)

		if not frappe.db.exists("Item", source_item_code):
			frappe.throw("Item {0} does not exist").format(source_item_code)

		# --------------------------------------------------
		# Fetch source item valuation/basic rate
		# --------------------------------------------------
		source_basic_rate = frappe.db.get_value(
			"Bin",
			{
				"item_code": source_item_code,
				"warehouse": source_warehouse
			},
			"valuation_rate"
		)

		source_basic_rate = source_basic_rate or 0

		# --------------------------------------------------
		# Create Stock Entry
		# --------------------------------------------------
		se = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Repack",
			"items": []
		})

		# --------------------------------------------------
		# Source Row
		# --------------------------------------------------
		se.append(
			"items",
			{
				"item_code": source_item_code,
				"s_warehouse": source_warehouse,
				"qty": source_item_qty
			}
		)

		# --------------------------------------------------
		# Target Rows
		# --------------------------------------------------
		for target in target_items:

			target_warehouse = target.get("target_warehouse")
			target_item_code = target.get("target_item_code")
			target_item_qty = target.get("target_item_qty")

			if not target_warehouse:
				frappe.throw("target_warehouse is required")

			if not target_item_code:
				frappe.throw("target_item_code is required")

			if not target_item_qty:
				frappe.throw("target_item_qty is required")

			if not frappe.db.exists("Warehouse", target_warehouse):
				frappe.throw("Warehouse {0} does not exist").format(target_warehouse)


			if not frappe.db.exists("Item", target_item_code):
				frappe.throw("Item {0} does not exist").format(target_item_code)

			se.append(
				"items",
				{
					"item_code": target_item_code,
					"t_warehouse": target_warehouse,
					"qty": target_item_qty,
					"set_basic_rate_manually": 1,
					"basic_rate": source_basic_rate
				}
			)

		# --------------------------------------------------
		# Save as Draft
		# --------------------------------------------------
		se.insert(ignore_permissions=True)

		frappe.db.commit()

		return {
			"status": "success",
			"message": "Stock Entry created successfully",
			"data": {
				"name": se.name,
				"doctype": "Stock Entry",
				"stock_entry_type": se.stock_entry_type,
				"status": se.docstatus
			}
		}

	except frappe.ValidationError as e:
		frappe.log_error(
			frappe.get_traceback(),
			"Stock Repack From Bay Error"
		)

		return {
			"status": "error",
			"message": ("Validation Error: {0}").format(str(e)),
			"data": None
		}

	except Exception as e:
		frappe.log_error(
			frappe.get_traceback(),
			"Stock Repack From Bay Error"
		)

		return {
			"status": "error",
			"message": ("Error creating Stock Entry: {0}").format(str(e)),
			"data": None
		}
