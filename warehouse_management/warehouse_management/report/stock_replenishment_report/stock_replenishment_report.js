// Copyright (c) 2026, Rakonex and contributors
// For license information, please see license.txt

frappe.query_reports["Stock Replenishment Report"] = {
    filters: [
        {
            fieldname: "warehouse",
            label: __("Warehouse"),
            fieldtype: "Link",
            options: "Warehouse"
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