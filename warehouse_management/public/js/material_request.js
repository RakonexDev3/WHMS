frappe.ui.form.on("Material Request", {
	refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            update_available_stock(frm);
        }

        set_stock_at_source_tooltip(frm);

        setTimeout(() => {
            frm.page.wrapper
                .find('.btn:contains("Approve"), .dropdown-item:contains("Approve")')
                .off('click')
                .on('click', function(e) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    handle_approve_click(frm);
                });
        }, 300);
    },

	set_from_warehouse(frm) {
		if (frm.doc.docstatus === 0) {
			update_available_stock(frm);
		}
	},
});

frappe.ui.form.on("Material Request Item", {
	item_code(frm, cdt, cdn) {
		if (frm.doc.docstatus === 0) {
			update_item_available_stock(frm, cdt, cdn);
		}
	},
});

function set_stock_at_source_tooltip(frm) {
	const tooltip = frm.doc.docstatus === 0
		? __("Stock at Source (Currently Available)")
		: __("Stock at Source (At Time of Approval)");

	setTimeout(() => {
		frm.fields_dict.items.grid.wrapper
			.find('[data-fieldname="stock_available_at_source"]')
			.attr("title", tooltip);
	}, 100);
}

function update_available_stock(frm) {
	const warehouse = frm.doc.set_from_warehouse;

	(frm.doc.items || []).forEach((row) => {
		update_item_available_stock(frm, row.doctype, row.name, warehouse);
	});
}

function update_item_available_stock(frm, cdt, cdn, warehouse = frm.doc.set_from_warehouse) {
	const row = frappe.get_doc(cdt, cdn);

	if (!warehouse || !row.item_code) {
		row.stock_available_at_source = 0;
		frm.refresh_field("items");
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
			row.stock_available_at_source = r.message || 0;
            frm.refresh_field("items");
		},
	});
}

function handle_approve_click(frm) {
    frappe.call({
        method: "warehouse_management.events.material_request.get_conflicting_pending_mrs",
        args: { material_request: frm.doc.name },
        freeze: true,
        freeze_message: __("Checking for conflicts..."),
        callback: function(r) {
            let conflicts = r.message || [];

            if (!conflicts.length) {
                run_workflow_action(frm, 'Approve');
                return;
            }

            show_conflict_dialog(frm, conflicts);
        }
    });
}

function show_conflict_dialog(frm, conflicts) {
    let rows = conflicts.map(c => {
        let mr_link = frappe.utils.get_form_link
            ? frappe.utils.get_form_link("Material Request", c.mr_name)
            : `/app/material-request/${encodeURIComponent(c.mr_name)}`;

        return `
            <tr>
                <td><a href="${mr_link}" target="_blank">${frappe.utils.escape_html(c.mr_name)}</a></td>
                <td>${frappe.utils.escape_html(c.target_warehouse || '')}</td>
                <td>${frappe.utils.escape_html(c.item_code)}</td>
                <td>${frappe.utils.escape_html(c.item_name || '')}</td>
                <td style="text-align:right">${c.qty}</td>
            </tr>
        `;
    }).join('');

    let table_html = `
        <div style="max-height: 400px; overflow-y: auto;">
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>Material Request</th>
                        <th>Target Warehouse</th>
                        <th>Item Code</th>
                        <th>Item Name</th>
                        <th style="text-align:right">Qty</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;

    let d = new frappe.ui.Dialog({
        title: __('Conflicting Pending Material Requests'),
        size: 'large',
        fields: [
            { fieldtype: 'HTML', fieldname: 'conflict_table', options: table_html }
        ],
        primary_action_label: __('Approve Anyway'),
        primary_action: () => {
            d.hide();
            run_workflow_action(frm, 'Approve');
        },
        secondary_action_label: __('Cancel'),
        secondary_action: () => {
            d.hide();
        }
    });

    d.show();
}

function run_workflow_action(frm, action) {
    frappe.dom.freeze(__("Updating..."));
    frappe.xcall('frappe.model.workflow.apply_workflow', { doc: frm.doc, action: action })
        .then((doc) => {
            frappe.model.sync(doc);
            frm.refresh();
        })
        .finally(() => {
            frappe.dom.unfreeze();
        });
}