# Copyright (c) 2026, Rakonex and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from collections import defaultdict


class PackingList(Document):
	def before_submit(self):
		pick_list_doc = frappe.get_doc("Pick List", self.pick_list)
		self.validate_packing_quantities(pick_list_doc)

	def on_submit(self):
		self.update_material_request_status()

	def validate_packing_quantities(self, pick_list_doc):
		"""
		Validate total quantity packed across all Boxes
		against the quantities in the Pick List.
		"""

		packed_qty = defaultdict(float)

		for box_row in self.items:
			if not box_row.box_id:
				continue

			box = frappe.get_doc("Box", box_row.box_id)

			for item_row in box.items:
				if not item_row.item:
					continue

				packed_qty[item_row.item] += item_row.qty or 0

		pick_qty = defaultdict(float)

		for row in pick_list_doc.locations:
			if not row.item_code:
				continue

			pick_qty[row.item_code] += row.qty or 0

		for item_code, required_qty in pick_qty.items():
			packed = packed_qty.get(item_code, 0)

			if packed != required_qty:
				frappe.throw(
					_(
						"Packed quantity for item {0} is {1}, "
						"but Pick List quantity is {2}."
					).format(
						item_code,
						packed,
						required_qty
					)
				)

		for item_code in packed_qty:
			if item_code not in pick_qty:
				frappe.throw(
					_(
						"Item {0} exists in the Boxes "
						"but not in the Pick List."
					).format(item_code)
				)

	def update_material_request_status(self):
		if not self.material_request:
			return

		frappe.db.set_value(
			"Material Request",
			self.material_request,
			"workflow_state",
			"Packed",
			update_modified=False,
		)
