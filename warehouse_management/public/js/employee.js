frappe.ui.form.on("Employee", {
    setup(frm) {
        frm.set_query("active_warehouse", () => {
            return {
                filters: {
                    is_sub_warehouse: 0,
                    disabled: 0,
                },
            };
        });
    },
});