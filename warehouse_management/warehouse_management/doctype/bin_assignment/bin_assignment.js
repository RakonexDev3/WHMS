// Copyright (c) 2026, Rakonex and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bin Assignment", {
	rack(frm) {
		frm.set_query("bin", function () {
			if (!frm.doc.rack) {
				return {};
			}

			return {
				filters: {
					rack: frm.doc.rack
				}
			};
		});

		frm.set_value("bin", null);
	}
});