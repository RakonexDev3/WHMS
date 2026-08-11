let active_warehouse = null;
let material_request_listview = null;

frappe.listview_settings["Material Request"] = {
	add_fields: [
		"set_warehouse",
		"set_from_warehouse",
	],

	button: {
		show: function (doc) {
			return (
				active_warehouse &&
				doc.set_warehouse &&
				doc.set_warehouse !== active_warehouse
			);
		},

		get_label: function (doc) {
			return `
				<i
					class="fa fa-exchange"
					style="font-size:14px; color:#888;"
				></i>
			`;
		},

		get_description: function (doc) {
			return __(
				"Material Request from External Warehouse",
				[active_warehouse]
			);
		},

		action: function (doc) {
			if (!active_warehouse || !material_request_listview) {
				return;
			}

			const filters = material_request_listview.filter_area.get();

			const already_filtered = filters.some(
				(filter) =>
					filter[1] === "set_from_warehouse" &&
					filter[2] === "=" &&
					filter[3] === active_warehouse
			);

			if (already_filtered) {
				return;
			}

			material_request_listview.filter_area.add(
				"Material Request",
				"set_from_warehouse",
				"=",
				active_warehouse
			);
		},
	},

	onload: function (listview) {
		material_request_listview = listview;

		frappe.call({
			method: "warehouse_management.events.material_request.get_active_warehouse",

			callback: function (r) {
				active_warehouse = r.message || null;

				if (active_warehouse) {
					listview.refresh();
				}
			},
		});
	},
};