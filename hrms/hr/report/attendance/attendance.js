// Copyright (c) 2025
// For license information, please see license.txt

frappe.query_reports["Attendance"] = {
	filters: [
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
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
			reqd: 1,
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "On Time", "Late", "Absent", "Holiday", "On Leave", "Half Day"].join("\n"),
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

		return value;
	},
};