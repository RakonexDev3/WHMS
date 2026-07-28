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
});