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
 // Auto-set Consignment when External is checked
    external(frm) {
        if (frm.doc.external) {
            frm.set_value("warehouse_type", "Consignment");
        }
        else {
            frm.set_value("warehouse_type", "");
        }
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