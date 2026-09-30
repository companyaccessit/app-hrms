// Copyright (c) 2025
// For license information, please see license.txt

frappe.query_reports["Attendance"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
			on_change: function () {
				// Employee / Department lists depend on company
				frappe.query_report.set_filter_value("employee", "");
				frappe.query_report.set_filter_value("department", "");
			},
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
			get_query: function () {
				const company = frappe.query_report.get_filter_value("company");
				return { filters: company ? { company: company } : {} };
			},
			on_change: function () {
				frappe.query_report.set_filter_value("employee", "");
			},
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
			get_query: function () {
				const company = frappe.query_report.get_filter_value("company");
				const department = frappe.query_report.get_filter_value("department");
				const filters = {};
				if (company) filters.company = company;
				if (department) filters.department = department;
				return { filters: filters };
			},
		},
		{
			fieldname: "from_date",
			label: __("Start Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("End Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "shift",
			label: __("Shift Type"),
			fieldtype: "Link",
			options: "Shift Type",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "On Time", "Late", "Absent", "Holiday", "On Leave", "Half Day"].join("\n"),
		},
		{
			fieldname: "leave_type",
			label: __("Leave Type"),
			fieldtype: "Link",
			options: "Leave Type",
		},
		{
			fieldname: "late_entry",
			label: __("Late Entry"),
			fieldtype: "Select",
			options: ["", "Yes", "No"].join("\n"),
		},
		{
			fieldname: "early_exit",
			label: __("Early Exit"),
			fieldtype: "Select",
			options: ["", "Yes", "No"].join("\n"),
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "status" && data && data.status) {
			const status = data.status;
			let color = "";

			if (status === "On Time") {
				color = "var(--green-600, #2f9e44)";
			} else if (status.startsWith("Late")) {
				color = "var(--orange-600, #e67700)";
			} else if (status === "Absent") {
				color = "var(--red-600, #e03131)";
			} else {
				// Holiday / On Leave / Half Day
				color = "var(--text-muted, #6c757d)";
			}

			value = `<span style="color: ${color}; font-weight: 600;">${value}</span>`;
		}

		if (column.fieldname === "early_exit" && data && data.early_exit) {
			value = `<span style="color: var(--orange-600, #e67700); font-weight: 600;">${value}</span>`;
		}

		return value;
	},
};