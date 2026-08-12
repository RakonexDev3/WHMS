frappe.ui.form.on("Warehouse", {
    setup(frm) {
        frm.set_query("main_warehouse", () => {
            return {
                filters: {
                    is_sub_warehouse: 0,
                    disabled: 0,
                },
            };
        });
    },
    warehouse_type(frm) {
		frm.set_value(
			"include_in_transaction",
			["Bay", "Storage"].includes(frm.doc.warehouse_type) ? 1 : 0
		);
	},

	refresh(frm) {
		if (frm.is_new() && frm.doc.warehouse_type) {
			frm.set_value(
				"include_in_transaction",
				["Bay", "Storage"].includes(frm.doc.warehouse_type) ? 1 : 0
			);
		}
	},
});