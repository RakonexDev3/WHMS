import frappe
from frappe.model.document import Document


class StockQualityCheck(Document):

    def on_submit(self):
        if self.packing_list:
            frappe.db.set_value(
                "Packing List",
                self.packing_list,
                "stock_status",
                "Verified",
                update_modified=True,
            )