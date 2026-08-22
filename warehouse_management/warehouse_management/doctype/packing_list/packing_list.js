// // Copyright (c) 2026, Rakonex and contributors
// // For license information, please see license.txt

frappe.ui.form.on("Packing List", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 0) {
			return;
		}

		frm.add_custom_button(__("Create Box"), () => {
			frappe.route_options = {
				packing_list: frm.doc.name
			};

			frappe.set_route("Form", "Box", "new");
		}, __("Create"));
	}
});