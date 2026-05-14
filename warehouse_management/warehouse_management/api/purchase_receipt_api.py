# Copyright (c) 2026, Rakonex and contributors
# For license information, please see license.txt

import frappe
from frappe import _
# from frappe.utils.response import build_response


@frappe.whitelist(methods=["POST"])
def create_purchase_receipt_from_po():
	"""
	Create a Purchase Receipt in draft status from a Purchase Order.
	
	Request body should contain:
	{
		"po_id": "PO-2026-001",
		"warehouse": "Warehouse-1",
		"items": [
			{
				"item_code": "ITEM-001",
				"quantity": 10,
				"uom": "Nos",
				"rack": "RACK-001",
				"bin": "BIN-001",
				"expiry_date": "2026-12-31"
			},
			...
		]
	}
	
	Returns:
	{
		"success": true,
		"message": "Purchase Receipt created successfully",
		"data": {
			"name": "PR-2026-001",
			"doctype": "Purchase Receipt",
			"status": "Draft"
		}
	}
	"""
	try:
		# Get request data
		data = frappe.local.request.get_json()
		
		po_id = data.get("po_id")
		warehouse = data.get("warehouse")
		items_data = data.get("items", [])
		
		# Validate required fields
		if not po_id:
			frappe.throw(_("Purchase Order ID is required"))
		if not warehouse:
			frappe.throw(_("Warehouse is required"))
		if not items_data:
			frappe.throw(_("Items data is required"))
		
		# Fetch the Purchase Order
		po = frappe.get_doc("Purchase Order", po_id)
		if not po:
			frappe.throw(_("Purchase Order {0} not found").format(po_id))
		
		# Create Purchase Receipt
		pr = frappe.get_doc({
			"doctype": "Purchase Receipt",
			"purchase_order": po_id,
			"supplier": po.supplier,
			"posting_date": frappe.utils.today(),
			"warehouse": warehouse,
			"items": []
		})
		
		# Create a mapping of PO items by item_code for easy lookup
		po_items_map = {item.item_code: item for item in po.items}
		
		# Process provided items
		for item_data in items_data:
			item_code = item_data.get("item_code")
			if not item_code:
				frappe.throw(_("Item code is required for all items"))
			
			# Get corresponding PO item
			po_item = po_items_map.get(item_code)
			if not po_item:
				frappe.throw(_("Item {0} not found in Purchase Order").format(item_code))
			
			# Create PR item with provided data + PO data
			pr_item = {
				"item_code": item_code,
				"qty": item_data.get("quantity", po_item.qty),
				"uom": item_data.get("uom", po_item.uom),
				"rate": po_item.rate,
				"purchase_order": po_id,
				"purchase_order_item": po_item.name,
				"received_qty": item_data.get("quantity", po_item.qty),
				"rack": item_data.get("rack"),
				"bin": item_data.get("bin"),
				"expiry_date": item_data.get("expiry_date"),
				"batch_no": item_data.get("batch_no"),
				"stock_uom": po_item.stock_uom if hasattr(po_item, "stock_uom") else po_item.uom,
			}
			
			# Optional fields from PO if not provided
			if not pr_item.get("batch_no"):
				pr_item["batch_no"] = po_item.get("batch_no")
			
			pr.append("items", pr_item)
		
		# Save the Purchase Receipt in draft status (no submit)
		pr.insert(ignore_permissions=True)
		
		frappe.db.commit()
		
		return {
			"status": "success",
			"message": _("Purchase Receipt created successfully"),
			"data": {
				"name": pr.name,
				"doctype": "Purchase Receipt",
				"status": pr.docstatus
			}
		}
		
	except frappe.ValidationError as e:
		frappe.log_error(frappe.get_traceback(), "Purchase Receipt Creation Error")
		return {
			"status": "error",
			"message": _("Validation Error: {0}").format(str(e)),
			"data": None
		}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Purchase Receipt Creation Error")
		return {
			"status": "error",
			"message": _("Error creating Purchase Receipt: {0}").format(str(e)),
			"data": None
		}
