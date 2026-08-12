frappe.ui.form.on("Material Request", {
	set_from_warehouse(frm) {
		update_available_stock(frm);
	},
});

frappe.ui.form.on("Material Request Item", {
	item_code(frm, cdt, cdn) {
		update_item_available_stock(frm, cdt, cdn);
	},
});

function update_available_stock(frm) {
	const warehouse = frm.doc.set_from_warehouse;

	(frm.doc.items || []).forEach((row) => {
		update_item_available_stock(frm, row.doctype, row.name, warehouse);
	});
}

function update_item_available_stock(frm, cdt, cdn, warehouse = frm.doc.set_from_warehouse) {
	const row = frappe.get_doc(cdt, cdn);

	if (!warehouse || !row.item_code) {
		frappe.model.set_value(cdt, cdn, "stock_available_at_source", 0);
		return;
	}

	frappe.call({
		method:
			"warehouse_management.events.stock_availability.get_available_qty",
		args: {
			item_code: row.item_code,
			warehouse: warehouse,
		},
		callback(r) {
			frappe.model.set_value(cdt, cdn, "stock_available_at_source", r.message || 0);
		},
	});
}