# Copyright (c) 2026, Rakonex and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Box(Document):
	def validate(self):
		self.validate_items()
		self.update_total_items()

	def on_update(self):
		self.sync_with_packing_list()

	def on_trash(self):
		self.remove_from_packing_list()

	def validate_items(self):
		if not self.items:
			frappe.throw(_("At least one item is required in the Box."))

		for row in self.items:
			if not row.item:
				frappe.throw(_("Item is required in Box."))

			if not row.qty or row.qty <= 0:
				frappe.throw(
					_("Quantity must be greater than zero for item {0}.")
					.format(row.item)
				)

			if not row.uom:
				frappe.throw(
					_("UOM is required for item {0}.")
					.format(row.item)
				)

	def update_total_items(self):
		"""Calculate total quantity from all Box Items."""

		self.total_items = sum(
			row.qty or 0
			for row in self.items
		)

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