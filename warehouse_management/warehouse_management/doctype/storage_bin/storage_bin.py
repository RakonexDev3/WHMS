# Copyright (c) 2026, Rakonex and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
# from frappe import _

class StorageBin(Document):

    def validate(self):
        self.validate_capacity()

    def validate_capacity(self):

        rack = frappe.get_doc("Rack", self.rack)

        occupied = frappe.db.sql("""
            SELECT COALESCE(SUM(cells_occupied), 0)
            FROM `tabStorage Bin`
            WHERE rack = %s
            AND name != %s
            AND docstatus < 2
        """, (self.rack, self.name))[0][0]

        available = rack.total_cells - occupied

        if self.cells_occupied > available:
            frappe.throw(_(
                f"Only {available} cells available in Rack {self.rack}"
            ))