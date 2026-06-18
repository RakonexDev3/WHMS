# Copyright (c) 2026, Rakonex and contributors
# For license information, please see license.txt

import frappe
from frappe import _
# from frappe.utils.response import build_response


@frappe.whitelist(methods=["POST"])
def create_purchase_receipt_from_po():
	"""
	Create a Purchase Receipt in draft status from a Purchase Order.
	Creates new Item template if item has surprise_variant enabled.
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

		# Fetch Purchase Order
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

		# Create PO item lookup map
		po_items_map = {item.item_code: item for item in po.items}

		# Process incoming items
		for item_data in items_data:

			item_code = item_data.get("item_code")

			if not item_code:
				frappe.throw(_("Item code is required for all items"))

			# Get corresponding PO item
			po_item = po_items_map.get(item_code)

			if not po_item:
				frappe.throw(
					_("Item {0} not found in Purchase Order").format(item_code)
				)

			# ----------------------------------------------------------
			# Create Item Template if surprise variant is enabled
			# ----------------------------------------------------------
			if item_data.get("surprise_variant"):

				variant_attributes = item_data.get("variant_attribute")

				if not variant_attributes:
					frappe.throw(
						_("variant_attribute is required when surprise_variant is enabled for item {0}")
						.format(item_code)
					)

				if not isinstance(variant_attributes, list):
					frappe.throw(
						_("variant_attribute must be a list for item {0}")
						.format(item_code)
					)

				template_item_code = f"{item_code}-T"

				# Create template only if it doesn't already exist
				if not frappe.db.exists("Item", template_item_code):

					source_item = frappe.get_doc("Item", item_code)

					template_item = frappe.copy_doc(source_item)

					# Reset identifiers
					template_item.name = None

					# Convert copied item into template
					template_item.item_code = template_item_code
					template_item.item_name = (
						f"{source_item.item_name} - Template"
					)

					template_item.has_variants = 1
					template_item.variant_based_on = "Item Attribute"

					# Remove any existing attributes
					template_item.attributes = []

					# Add requested attributes
					for attribute in variant_attributes:

						if not attribute:
							continue

						template_item.append(
							"attributes",
							{
								"attribute": attribute
							}
						)

					if not template_item.attributes:
						frappe.throw(
							_("At least one valid variant attribute is required for item {0}")
							.format(item_code)
						)

					template_item.insert(ignore_permissions=True)

			# ----------------------------------------------------------
			# Create Purchase Receipt Item
			# ----------------------------------------------------------

			# Determine target warehouse
			target_warehouse = warehouse

			if item_data.get("surprise_variant"):
				target_warehouse = f"Bay {warehouse}"

			pr_item = {
				"item_code": item_code,
				"qty": item_data.get("quantity", po_item.qty),
				"uom": item_data.get("uom", po_item.uom),
				"rate": po_item.rate,
				"purchase_order": po_id,
				"purchase_order_item": po_item.name,
				"received_qty": item_data.get(
					"quantity",
					po_item.qty
				),
				"warehouse": target_warehouse,
				"rack": item_data.get("rack"),
				"bin": item_data.get("bin"),
				"expiry_date": item_data.get("expiry_date"),
				"batch_no": item_data.get("batch_no"),
				"stock_uom": (
					po_item.stock_uom
					if hasattr(po_item, "stock_uom")
					else po_item.uom
				),
			}

			# Optional batch number from PO
			if not pr_item.get("batch_no"):
				pr_item["batch_no"] = po_item.get("batch_no")

			pr.append("items", pr_item)

		# Save PR in draft status
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
		frappe.log_error(
			frappe.get_traceback(),
			"Purchase Receipt Creation Error"
		)

		return {
			"status": "error",
			"message": _("Validation Error: {0}").format(str(e)),
			"data": None
		}

	except Exception as e:
		frappe.log_error(
			frappe.get_traceback(),
			"Purchase Receipt Creation Error"
		)

		return {
			"status": "error",
			"message": _("Error creating Purchase Receipt: {0}").format(str(e)),
			"data": None
		}
