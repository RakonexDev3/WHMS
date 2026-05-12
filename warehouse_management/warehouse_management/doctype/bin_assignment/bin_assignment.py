# Copyright (c) 2026, Rakonex and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BinAssignment(Document):
	def after_insert(self):
		"""Set Storage Bin status to Occupied when Bin Assignment is created"""
		if self.bin:
			storage_bin = frappe.get_doc("Storage Bin", self.bin)
			storage_bin.status = "Occupied"
			storage_bin.save(ignore_permissions=True)

	def after_delete(self):
		"""Set Storage Bin status to Empty when Bin Assignment is deleted"""
		if self.bin:
			storage_bin = frappe.get_doc("Storage Bin", self.bin)
			storage_bin.status = "Empty"
			storage_bin.save(ignore_permissions=True)
