import frappe



@frappe.whitelist(methods=["POST"])

def get_purchase_order_item_details():

	"""

	Get item details for an item belonging to a Purchase Order.



	Request body must contain:

	{

		"po_id": "PO-2026-001",

		"item_code": "ITEM-001"

	}

	

	Returns item details including stock UOM, available UOMs, description, and PO-specific item fields.

	"""

	try:

		data = frappe.local.request.get_json()

		po_id = data.get("po_id")

		item_code = data.get("item_code")



		if not po_id:

			frappe.throw(f"Purchase Order ID is required")

		if not item_code:

			frappe.throw(f"Item Code is required")



		if not frappe.db.exists("Purchase Order", po_id):

			frappe.throw(f"Purchase Order {po_id} not found")



		po = frappe.get_doc("Purchase Order", po_id)

		po_item = next((item for item in po.items if item.item_code == item_code), None)

		if not po_item:

			frappe.throw(f"Item {item_code} is not part of Purchase Order {po_id}")



		item_data = {

			"item_code": item_code,

			"item_name": po_item.get("item_name") or po_item.get("item_code"),

			"stock_uom": po_item.get("stock_uom") or po_item.get("uom"),

			"description": po_item.get("description") or po_item.get("item_description") or "",

			"uom": po_item.get("uom"),

			"rate": po_item.get("rate"),

			"purchase_order_item": po_item.name,

			"purchase_order": po_id,

			"uoms": [],

		}



		if frappe.db.exists("Item", item_code):

			item_doc = frappe.get_doc("Item", item_code)

			item_data["item_name"] = item_doc.get("item_name") or item_data["item_name"]

			item_data["stock_uom"] = item_doc.get("stock_uom") or item_data["stock_uom"]

			item_data["description"] = (

				item_doc.get("description") or

				item_doc.get("item_description") or

				item_data["description"]

			)

			item_data["item_group"] = item_doc.get("item_group")

			item_data["brand"] = item_doc.get("brand")

			item_data["item_class"] = item_doc.get("item_class")

			item_data["default_supplier"] = item_doc.get("default_supplier")

			item_data["purchase_uom"] = item_doc.get("purchase_uom")

			item_data["uoms"] = []

			for uom_row in getattr(item_doc, "uoms", []):

				if uom_row.get("uom"):

					item_data["uoms"].append(uom_row.uom)


		return {

			"status": "success",

			"message": "Purchase Order item details fetched successfully",

			"data": item_data,

		}



	except frappe.ValidationError as e:

		frappe.log_error(frappe.get_traceback(), "Purchase Order Item Details Error")

		return {

			"status": "error",

			"message": f"Validation Error: {str(e)}",

			"data": None,

		}

	except Exception as e:

		frappe.log_error(frappe.get_traceback(), "Purchase Order Item Details Error")

		return {

			"status": "error",

			"message": f"Error fetching item details: {str(e)}",

			"data": None,

		}

@frappe.whitelist(methods=["GET"])
def get_templates_without_variants():
	"""
	Return all Item Templates that do not have any variants created.
	"""

	try:

		templates = frappe.db.sql(
			"""
			SELECT
				i.name,
				i.item_name
			FROM `tabItem` i
			WHERE
				i.has_variants = 1
				AND NOT EXISTS (
					SELECT 1
					FROM `tabItem` v
					WHERE v.variant_of = i.name
				)
			ORDER BY i.item_name
			""",
			as_dict=True
		)

		return {
			"status": "success",
			"data": templates
		}

	except Exception as e:
		frappe.log_error(
			frappe.get_traceback(),
			"Get Templates Without Variants Error"
		)

		return {
			"status": "error",
			"message": str(e),
			"data": []
		}

@frappe.whitelist(methods=["POST"])
def create_variant_creation_request():
	"""
	Create a Variant Creation Request.

	Request:
	{
		"item_template": "TRU-2297512-T",
		"variants": [
			{
				"variant_name": "Test A",
				"notes": "Test Notes A"
			},
			{
				"variant_name": "Test B",
				"notes": "Test Notes B"
			}
		]
	}
	"""

	try:
		data = frappe.local.request.get_json()

		item_template = data.get("item_template")
		variants = data.get("variants", [])

		# --------------------------------------------------
		# Validations
		# --------------------------------------------------
		if not item_template:
			frappe.throw("item_template is required")

		if not variants:
			frappe.throw("At least one variant is required")

		if not frappe.db.exists("Item", item_template):
			frappe.throw("Item Template {0} does not exist").format(item_template)

		# --------------------------------------------------
		# Create Variant Creation Request
		# --------------------------------------------------
		vcr = frappe.get_doc({
			"doctype": "Variant Creation Request",
			"item_template": item_template,
			"variants": []
		})

		for variant in variants:

			variant_name = variant.get("variant_name")
			notes = variant.get("notes")

			if not variant_name:
				frappe.throw("variant_name is required for all variants")

			vcr.append(
				"variants",
				{
					"variant_name": variant_name,
					"notes": notes
				}
			)

		# --------------------------------------------------
		# Save
		# --------------------------------------------------
		vcr.insert(ignore_permissions=True)

		frappe.db.commit()

		return {
			"status": "success",
			"message": ("Variant Creation Request created successfully"),
			"data": {
				"name": vcr.name,
				"doctype": "Variant Creation Request",
				"status": vcr.docstatus
			}
		}

	except frappe.ValidationError as e:
		frappe.log_error(
			frappe.get_traceback(),
			"Variant Creation Request Error"
		)

		return {
			"status": "error",
			"message": ("Validation Error: {0}").format(str(e)),
			"data": None
		}

	except Exception as e:
		frappe.log_error(
			frappe.get_traceback(),
			"Variant Creation Request Error"
		)

		return {
			"status": "error",
			"message": ("Error creating Variant Creation Request: {0}")
			.format(str(e)),
			"data": None
		}