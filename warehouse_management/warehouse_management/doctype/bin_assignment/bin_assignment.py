# Copyright (c) 2026, Rakonex and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class BinAssignment(Document):
	def after_insert(self):
		"""Set Storage Bin status to Occupied when Bin Assignment is created"""
		if not self.bin:
			return

		storage_bin = frappe.get_doc("Storage Bin", self.bin)

		if self.assignment_type == "Picking":
			storage_bin.quantity = (
				flt(storage_bin.quantity) + flt(self.quantity)
			)

			if storage_bin.quantity <= 0:
				storage_bin.quantity = 0
				storage_bin.status = "Empty"
				storage_bin.bin_assignment_record = None
				storage_bin.assigned_item = None
				storage_bin.uom = None
				storage_bin.assigned_on = None

			else:
				storage_bin.status = "Occupied"
				storage_bin.bin_assignment_record = self.name

		else:

			storage_bin.quantity = (
				flt(storage_bin.quantity) + flt(self.quantity)
			)

			storage_bin.status = "Occupied"
			storage_bin.bin_assignment_record = self.name
			storage_bin.assigned_item = self.item
			storage_bin.uom = self.uom
			storage_bin.assigned_on = self.doa
			storage_bin.expiry_date = self.expiry_date

		storage_bin.save(ignore_permissions=True)

	def after_delete(self):
		"""Set Storage Bin status to Empty when Bin Assignment is deleted"""
		if not self.bin:
			return

		storage_bin = frappe.get_doc("Storage Bin", self.bin)

		storage_bin.quantity = max(
			flt(storage_bin.quantity) - flt(self.quantity),
			0,
		)

		if storage_bin.quantity > 0:
			storage_bin.status = "Occupied"

		else:
			storage_bin.status = "Empty"
			storage_bin.bin_assignment_record = None
			storage_bin.assigned_item = None
			storage_bin.uom = None
			storage_bin.assigned_on = None
			storage_bin.expiry_date = None

		storage_bin.save(ignore_permissions=True)

def create_bin_assignments_on_purchase_receipt_submit(doc, method):
	"""Create Bin Assignment records for Purchase Receipt items that have rack and bin assigned"""
	for item in doc.items:
		if item.get("rack") and item.get("bin"):
			# Create Bin Assignment
			bin_assignment = frappe.get_doc({
				"doctype": "Bin Assignment",
				"assignment_type": "Placing",
				"purchase_receipt": doc.name,
				"item": item.item_code,
				"rack": item.rack,
				"bin": item.bin,
				"uom": item.uom,
				"quantity": item.qty,
				"expiry_date": item.get("expiry_date"),
				"doa": item.get("date_of_assignment"),
				"batch_no": item.get("batch_no"),
				"notes": f"Auto-created from Purchase Receipt {doc.name}"
			})
			bin_assignment.insert(ignore_permissions=True)