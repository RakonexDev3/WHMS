// Copyright (c) 2026, Rakonex and contributors
// For license information, please see license.txt

frappe.query_reports["Stock Replenishment Report"] = {
    filters: [
        {
            fieldname: "warehouse",
            label: __("Warehouse"),
            fieldtype: "Link",
            options: "Warehouse",
            get_query() {
                return {
                    query: "warehouse_management.warehouse_management.report.stock_replenishment_report.stock_replenishment_report.get_warehouse_query",
                };
            },
        },
        {
            fieldname: "critical_only",
            label: __("Critically Low Items Only"),
            fieldtype: "Check",
            default: 1
        }
    ],

    get_datatable_options(options) {
        return Object.assign(options, {
            checkboxColumn: true,
        });
    },

    onload(report) {
        warehouse_management.setup_report_hover(report);

        report.page.add_inner_button(
            __("Material Request"),
            () => {
                const indexes = report.datatable.rowmanager.getCheckedRows();

                if (!indexes.length) {
                    frappe.throw(__("Please select at least one item."));
                }

                const selected_rows = indexes.map(i => report.data[i]);

                frappe.call({
                    method: "warehouse_management.warehouse_management.report.stock_replenishment_report.stock_replenishment_report.get_material_request",
                    args: {
                        items: selected_rows,
                    },
                    freeze: true,
                    callback(r) {
                        if (r.exc || !r.message) return;

                        frappe.model.sync(r.message);

                        frappe.set_route(
                            "Form",
                            r.message.doctype,
                            r.message.name
                        );
                    }
                });
            },
            __("Create")
        );
    }
};

warehouse_management.setup_report_hover = function (report) {
	warehouse_management.observe_link_preview();

	const bind_events = () => {
		if (!report.datatable || !report.datatable.wrapper) {
			return;
		}

		const $wrapper = $(report.datatable.wrapper);

		$wrapper.off(".stock_preview");

		$wrapper.on(
			"mouseenter.stock_preview",
			'a[data-doctype="Item"]',
			function () {
				const item_code = $(this).attr("data-name");

				if (!item_code) {
					return;
				}

				warehouse_management.current_item = item_code;

				warehouse_management.current_frm = {
					doc: {
						company: frappe.defaults.get_default("company"),
					},
				};

				warehouse_management.schedule_append_stock();
			}
		);
	};

	bind_events();

	if (report._stock_preview_observer) {
		return;
	}

	const target = report.page.wrapper[0];

	report._stock_preview_observer = new MutationObserver(() => {
		bind_events();
	});

	report._stock_preview_observer.observe(target, {
		childList: true,
		subtree: true,
	});
};