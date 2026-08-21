# Copyright (c) 2026, Rakonex and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from frappe.model.document import Document


class Box(Document):
	def validate(self):
		self.update_total_items()

	def after_insert(self):
		self.update_pick_list_packed_qty()

	def on_update(self):
		self.update_pick_list_packed_qty()
		self.sync_with_packing_list()

	def on_trash(self):
		self.update_pick_list_packed_qty()
		self.remove_from_packing_list()

	def update_total_items(self):
		"""Calculate total quantity from all Box Items."""

		self.total_items = sum(
			row.qty or 0
			for row in self.items
		)

	def update_pick_list_packed_qty(self):
		"""Update packed quantities on the linked Pick List from all boxes."""

		if not self.packing_list:
			return

		pick_list_name = frappe.db.get_value(
			"Packing List",
			self.packing_list,
			"pick_list",
		)

		if not pick_list_name:
			return

		boxes = frappe.get_all(
			"Box",
			filters={
				"packing_list": self.packing_list,
				"docstatus": 0,
			},
			pluck="name",
		)

		packed_qty = {}

		if boxes:
			box_items = frappe.get_all(
				"Box Items",
				filters={
					"parent": ["in", boxes],
					"parenttype": "Box",
					"parentfield": "items",
				},
				fields=["item", "qty"],
			)

			for row in box_items:
				packed_qty[row.item] = (
					packed_qty.get(row.item, 0) + flt(row.qty)
				)

		pick_list = frappe.get_doc("Pick List", pick_list_name)

		for row in pick_list.locations:
			row.packed_qty = packed_qty.get(row.item_code, 0)

		pick_list.flags.ignore_validate_update_after_submit = True
		pick_list.save(ignore_permissions=True)

	def sync_with_packing_list(self):
		"""
		Add or update this Box in the Packing List.
		"""

		if not self.packing_list:
			return

		packing_list = frappe.get_doc(
			"Packing List",
			self.packing_list
		)

		if packing_list.docstatus != 0:
			return

		existing_row = None

		for row in packing_list.items:
			if row.box_id == self.name:
				existing_row = row
				break

		if existing_row:
			existing_row.total_item = self.total_items
		else:
			packing_list.append(
				"items",
				{
					"box_id": self.name,
					"total_item": self.total_items,
				}
			)

		packing_list.flags.ignore_validate = True
		packing_list.save(ignore_permissions=True)

	def remove_from_packing_list(self):
		"""
		Remove this Box from the Packing List when deleted.
		"""

		if not self.packing_list:
			return

		packing_list = frappe.get_doc(
			"Packing List",
			self.packing_list
		)

		if packing_list.docstatus != 0:
			return

		packing_list.items = [
			row
			for row in packing_list.items
			if row.box_id != self.name
		]

		packing_list.flags.ignore_validate = True
		packing_list.save(ignore_permissions=True)