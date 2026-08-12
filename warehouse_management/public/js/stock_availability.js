frappe.provide("warehouse_management");

warehouse_management.stock_cache = {};
warehouse_management.current_item = null;
warehouse_management.current_frm = null;
warehouse_management.preview_observer = null;


warehouse_management.get_stock = function (
	item_code,
	company,
	warehouse
) {
	const key = [
		item_code,
		company || "",
		warehouse || "",
	].join("::");

	if (warehouse_management.stock_cache[key]) {
		return Promise.resolve(
			warehouse_management.stock_cache[key]
		);
	}

	return frappe.call({
		method:
			"warehouse_management.events.stock_availability.get_stock_availability",
		args: {
			item_code: item_code,
			company: company,
			warehouse: warehouse,
		},
	}).then(function (r) {
		const rows = r.message || [];

		warehouse_management.stock_cache[key] = rows;

		return rows;
	});
};


warehouse_management.render_stock_table = function (rows) {
	let html = `
		<div class="warehouse-stock-preview">
			<div
				style="
					margin: 0 26px;
					border-top: 1px solid var(--border-color);
					padding-top: 12px;
					padding-bottom: 12px;
				"
			>
				<div
					class="text-muted"
					style="margin-bottom: 10px;"
				>
					${__("Stock Availability")}
				</div>
	`;

	rows.forEach(function (row) {
		const warehouse = frappe.utils.escape_html(
			row.warehouse_name || row.warehouse || ""
		);

		const qty = format_number(
			row.stock_qty || 0,
			null,
			{ precision: 2 }
		);

		html += `
			<div
				style="
					display: flex;
					justify-content: space-between;
					align-items: center;
					gap: 15px;
					margin-bottom: 8px;
				"
			>
				<span class="text-muted">
					${warehouse}
				</span>

				<span>
					${qty}
				</span>
			</div>
		`;
	});

	html += `
			</div>
		</div>
	`;

	return html;
};

warehouse_management.find_preview = function () {
	const selectors = [
		".link-preview:visible",
		".link-preview-popover:visible",
		".popover:visible",
		".tooltip-content:visible",
	];

	for (const selector of selectors) {
		const $preview = $(selector);

		if ($preview.length) {
			return $preview.last();
		}
	}

	return null;
};


warehouse_management.append_stock = function () {
	const frm = warehouse_management.current_frm;
	const item_code = warehouse_management.current_item;

	if (!frm || !item_code) {
		return;
	}

	const $preview =
		warehouse_management.find_preview();

	if (!$preview || !$preview.length) {
		return;
	}

	const existing_item =
		$preview
			.find(".warehouse-stock-preview")
			.attr("data-item-code");

	if (existing_item === item_code) {
		return;
	}

	$preview
		.find(".warehouse-stock-preview")
		.remove();

	const company =
		frm.doc.company ||
		frappe.defaults.get_default("company");

	const warehouse =
		frm.doc.set_from_warehouse || null;

	const safe_item_code =
		frappe.utils.escape_html(item_code);

	const $loading = $(`
		<div
			class="warehouse-stock-preview"
			data-item-code="${safe_item_code}"
		>
			<div
				style="
					margin: 0 26px;
					border-top: 1px solid var(--border-color);
					padding-top: 12px;
					padding-bottom: 12px;
				"
			>
				<div class="text-muted">
					${__("Loading stock...")}
				</div>
			</div>
		</div>
	`);

	$preview.append($loading);

	warehouse_management
		.get_stock(
			item_code,
			company,
			warehouse
		)
		.then(function (rows) {
			if (
				!$.contains(document, $loading[0]) ||
				warehouse_management.current_item !== item_code
			) {
				return;
			}

			if (!rows.length) {
				$loading.css("display", "none");
				return;
			}

			const $stock = $(
				warehouse_management.render_stock_table(rows)
			);

			$stock.attr(
				"data-item-code",
				item_code
			);

			$loading.replaceWith($stock);
		})
		.catch(function () {
			if (!$.contains(document, $loading[0])) {
				return;
			}

			$loading.html(`
				<hr style="margin: 10px 0;">

				<div class="text-danger">
					${__(
						"Unable to load stock availability."
					)}
				</div>
			`);
		});
};


warehouse_management.schedule_append_stock = function () {
	[50, 150, 300, 500, 800].forEach(
		function (delay) {
			setTimeout(function () {
				warehouse_management.append_stock();
			}, delay);
		}
	);
};


warehouse_management.observe_link_preview = function () {
	if (warehouse_management.preview_observer) {
		return;
	}

	warehouse_management.preview_observer =
		new MutationObserver(function () {
			if (!warehouse_management.current_item) {
				return;
			}

			warehouse_management.schedule_append_stock();
		});

	warehouse_management.preview_observer.observe(
		document.body,
		{
			childList: true,
			subtree: true,
		}
	);
};


warehouse_management.setup_item_hover = function (frm) {
	const grid = frm.fields_dict.items?.grid;

	if (!grid) {
		return;
	}

	const selector =
		'.grid-row [data-fieldname="item_code"]';

	grid.wrapper.off(".stock_preview");

	grid.wrapper.on(
		"mouseenter.stock_preview",
		selector,
		function () {
			const $row =
				$(this).closest(".grid-row");

			const grid_row =
				$row.data("grid_row");

			if (!grid_row?.doc?.item_code) {
				return;
			}

			warehouse_management.current_frm = frm;
			warehouse_management.current_item =
				grid_row.doc.item_code;

			warehouse_management.schedule_append_stock();
		}
	);
};


warehouse_management.setup_stock_preview = function (frm) {
	warehouse_management.observe_link_preview();

	let attempts = 0;

	const setup = function () {
		attempts++;

		if (frm.fields_dict.items?.grid) {
			warehouse_management.setup_item_hover(frm);
			return;
		}

		if (attempts < 20) {
			setTimeout(setup, 100);
		}
	};

	setup();
};


warehouse_management.reset_stock_preview = function () {
	warehouse_management.current_item = null;
	warehouse_management.current_frm = null;

	warehouse_management.stock_cache = {};
};


frappe.ui.form.on("Material Request", {
	refresh(frm) {
		warehouse_management.reset_stock_preview();

		warehouse_management.setup_stock_preview(frm);
	},
});