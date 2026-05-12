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

def create_bin_assignments_on_purchase_receipt_submit(doc, method):
	"""Create Bin Assignment records for Purchase Receipt items that have rack and bin assigned"""
	for item in doc.items:
		if item.get("rack") and item.get("bin"):
			# Create Bin Assignment
			bin_assignment = frappe.get_doc({
				"doctype": "Bin Assignment",
				"purchase_receipt": doc.name,
				"item": item.item_code,
				"rack": item.rack,
				"bin": item.bin,
				"quantity": item.qty,
				"expiry_date": item.get("expiry_date"),
				"doa": item.get("date_of_assignment"),
				"batch_no": item.get("batch_no"),
				"notes": f"Auto-created from Purchase Receipt {doc.name}"
			})
			bin_assignment.insert(ignore_permissions=True)