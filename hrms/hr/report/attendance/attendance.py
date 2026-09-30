# Copyright (c) 2025
# For license information, please see license.txt

from datetime import time, timedelta

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, getdate, to_timedelta, today

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	return get_columns(), get_data(filters)


def validate_filters(filters):
	if not filters.from_date or not filters.to_date:
		frappe.throw(_("Please select Start Date and End Date"))

	if not filters.company:
		frappe.throw(_("Please select a Company"))

	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("Start Date cannot be after End Date"))


def get_columns():
	return [
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 110},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 160},
		{"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 140},
		{"label": _("Shift"), "fieldname": "shift", "fieldtype": "Link", "options": "Shift Type", "width": 110},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Data", "width": 90},
		{"label": _("Day"), "fieldname": "day", "fieldtype": "Data", "width": 70},
		{"label": _("In"), "fieldname": "in_time", "fieldtype": "Data", "width": 80},
		{"label": _("Out"), "fieldname": "out_time", "fieldtype": "Data", "width": 80},
		{"label": _("Work Hrs"), "fieldname": "work_hrs", "fieldtype": "Data", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
		{"label": _("Early Exit"), "fieldname": "early_exit", "fieldtype": "Data", "width": 110},
		{"label": _("Leave Type"), "fieldname": "leave_type", "fieldtype": "Link", "options": "Leave Type", "width": 120},
	]


def get_data(filters):
	from_date = getdate(filters.from_date)
	to_date = getdate(filters.to_date)
	today_date = getdate(today())

	employees = get_employees(filters)
	if not employees:
		return []

	records = get_attendance_records(filters, list(employees), from_date, to_date)
	shift_info = get_shift_info(records, employees)

	# One employee can (rarely) have several attendance records on a day (multiple shifts)
	records_by_key = {}
	for rec in records:
		records_by_key.setdefault((rec.employee, getdate(rec.attendance_date)), []).append(rec)

	# Absent / Holiday rows have no leave type, late or early exit info,
	# so they make no sense when one of those filters is active
	include_synthetic = not (filters.leave_type or filters.late_entry or filters.early_exit)
	holiday_cache = {}

	data = []
	for emp in employees.values():
		holidays = get_holiday_dates(emp.name, from_date, to_date, holiday_cache) if include_synthetic else set()

		current = from_date
		while current <= to_date:
			recs = records_by_key.get((emp.name, current))

			if recs:
				for rec in recs:
					data.append(build_row_from_record(rec, emp, shift_info))

			elif include_synthetic and (not filters.shift or emp.default_shift == filters.shift):
				if current in holidays:
					data.append(build_row(current, emp, shift=emp.default_shift, status="Holiday"))
				elif is_absent_candidate(current, today_date, emp):
					# No Attendance record at all -> treat as Absent
					data.append(build_row(current, emp, shift=emp.default_shift, status="Absent"))

			current = getdate(add_days(current, 1))

	if filters.status:
		data = [row for row in data if matches_status(row["status"], filters.status)]

	if filters.late_entry:
		wanted = filters.late_entry == "Yes"
		data = [row for row in data if row["_late"] == wanted]

	if filters.early_exit:
		wanted = filters.early_exit == "Yes"
		data = [row for row in data if row["_early"] == wanted]

	for row in data:
		row.pop("_late", None)
		row.pop("_early", None)
		row["company"] = filters.company  # not a visible column, used by the print format header

	return data


def get_employees(filters):
	emp_filters = {"company": filters.company}
	if filters.employee:
		emp_filters["name"] = filters.employee
	if filters.department:
		emp_filters["department"] = filters.department

	employees = frappe.get_all(
		"Employee",
		filters=emp_filters,
		fields=["name", "employee_name", "department", "date_of_joining", "relieving_date", "default_shift"],
		order_by="employee_name asc",
	)
	if not employees and filters.employee:
		frappe.throw(
			_("Employee {0} not found in company {1}").format(filters.employee, filters.company)
		)

	return {emp.name: emp for emp in employees}


def matches_status(row_status, selected):
	# "Late" matches every "Late 7m", "Late 1hr 25m" ... row
	if selected == "Late":
		return row_status.startswith("Late")

	return row_status == selected


def get_attendance_records(filters, employee_ids, from_date, to_date):
	att_filters = {
		"employee": ["in", employee_ids],
		"company": filters.company,
		"attendance_date": ["between", [from_date, to_date]],
		"docstatus": ["<", 2],  # draft + submitted, ignore cancelled
	}
	if filters.shift:
		att_filters["shift"] = filters.shift
	if filters.leave_type:
		att_filters["leave_type"] = filters.leave_type

	return frappe.get_all(
		"Attendance",
		filters=att_filters,
		fields=[
			"name",
			"employee",
			"attendance_date",
			"company",
			"status",
			"shift",
			"in_time",
			"out_time",
			"working_hours",
			"late_entry",
			"early_exit",
			"leave_type",
		],
		order_by="attendance_date asc, in_time asc",
	)


def get_shift_info(records, employees):
	"""Return {shift_name: {start, end, grace, exit_grace}} (timedeltas / minutes)"""
	shift_names = {rec.shift for rec in records if rec.shift}
	shift_names |= {emp.default_shift for emp in employees.values() if emp.default_shift}

	if not shift_names:
		return {}

	# Grace period fields differ between HRMS versions, so only query what exists
	meta = frappe.get_meta("Shift Type")
	optional = [
		"enable_entry_grace_period",
		"late_entry_grace_period",
		"enable_exit_grace_period",
		"early_exit_grace_period",
	]
	fields = ["name", "start_time", "end_time"] + [f for f in optional if meta.has_field(f)]

	shifts = frappe.get_all("Shift Type", filters={"name": ["in", list(shift_names)]}, fields=fields)

	info = {}
	for shift in shifts:
		if shift.start_time is None:
			continue

		info[shift.name] = frappe._dict(
			start=as_timedelta(shift.start_time),
			end=as_timedelta(shift.end_time) if shift.end_time is not None else None,
			grace=get_grace(shift, "enable_entry_grace_period", "late_entry_grace_period"),
			exit_grace=get_grace(shift, "enable_exit_grace_period", "early_exit_grace_period"),
		)
	return info


def get_grace(shift, toggle_field, value_field):
	grace = cint(shift.get(value_field))
	if toggle_field in shift and not shift.get(toggle_field):
		return 0
	return grace


def get_holiday_dates(employee, from_date, to_date, cache):
	try:
		from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
	except ImportError:
		return set()

	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if not holiday_list:
		return set()

	if holiday_list not in cache:
		dates = frappe.get_all(
			"Holiday",
			filters={"parent": holiday_list, "holiday_date": ["between", [from_date, to_date]]},
			pluck="holiday_date",
		)
		cache[holiday_list] = {getdate(d) for d in dates}

	return cache[holiday_list]


def is_absent_candidate(date, today_date, employee):
	# Only past days can be marked as absent (today may not be checked in yet)
	if date >= today_date:
		return False

	if employee.date_of_joining and date < getdate(employee.date_of_joining):
		return False

	if employee.relieving_date and date > getdate(employee.relieving_date):
		return False

	return True


def build_row_from_record(rec, employee, shift_info):
	in_time = get_datetime(rec.in_time) if rec.in_time else None
	out_time = get_datetime(rec.out_time) if rec.out_time else None
	default_shift = employee.default_shift

	late_minutes = get_late_minutes(rec, in_time, default_shift, shift_info)
	early_minutes = get_early_exit_minutes(rec, out_time, default_shift, shift_info)

	working_hours = flt(rec.working_hours)
	if not working_hours and in_time and out_time and out_time > in_time:
		working_hours = (out_time - in_time).total_seconds() / 3600

	return build_row(
		getdate(rec.attendance_date),
		employee,
		shift=rec.shift or default_shift,
		in_time=in_time,
		out_time=out_time,
		working_hours=working_hours,
		status=get_status(rec, in_time, late_minutes),
		leave_type=rec.leave_type if rec.status in ("On Leave", "Half Day") else "",
		late=late_minutes is not None,
		early_minutes=early_minutes,
	)


def get_late_minutes(rec, in_time, default_shift, shift_info):
	"""Return None when on time, otherwise minutes late (0 if the shift is unknown)."""
	if not in_time:
		return None

	shift = shift_info.get(rec.shift or default_shift)
	if not shift:
		# No shift to compare with, rely on the flag saved on the record
		return 0 if rec.late_entry else None

	expected_in = get_datetime(rec.attendance_date) + shift.start
	diff_seconds = (in_time - expected_in).total_seconds()

	if diff_seconds > shift.grace * 60:
		return int(diff_seconds // 60)

	return None


def get_early_exit_minutes(rec, out_time, default_shift, shift_info):
	"""Return None when not an early exit, otherwise minutes left early (0 if the shift is unknown)."""
	if not out_time:
		return None

	shift = shift_info.get(rec.shift or default_shift)
	if not shift or shift.end is None:
		return 0 if rec.get("early_exit") else None

	expected_out = get_datetime(rec.attendance_date) + shift.end
	if shift.end <= shift.start:  # overnight shift ends the next day
		expected_out += timedelta(days=1)

	diff_seconds = (expected_out - out_time).total_seconds()
	if diff_seconds > shift.exit_grace * 60:
		return int(diff_seconds // 60)

	return None


def build_row(
	date,
	employee,
	shift=None,
	in_time=None,
	out_time=None,
	working_hours=0,
	status="",
	leave_type="",
	late=False,
	early_minutes=None,
):
	return {
		"employee": employee.name,
		"employee_name": employee.employee_name,
		"department": employee.department,
		"shift": shift or "",
		"date": f"{MONTHS[date.month - 1]} {date.day:02d}",  # Aug 01
		"day": DAYS[date.weekday()],  # Sat, Sun, Mon ...
		"in_time": in_time.strftime("%H:%M") if in_time else "",
		"out_time": out_time.strftime("%H:%M") if out_time else "",
		"work_hrs": format_hours(working_hours),
		"status": status,
		"early_exit": format_duration("Early", early_minutes) if early_minutes is not None else "",
		"leave_type": leave_type or "",
		"_late": late,
		"_early": early_minutes is not None,
	}


def get_status(rec, in_time, late_minutes):
	if rec.status in ("On Leave", "Half Day"):
		return rec.status

	# The record may say "Absent" (auto attendance marks it when working hours are
	# below the shift threshold), but if the employee punched in, judge by the punch.
	if rec.status == "Absent" and not in_time:
		return "Absent"

	if late_minutes is not None:
		return format_duration("Late", late_minutes)

	return "On Time"


def format_duration(prefix, minutes):
	hours, mins = divmod(int(minutes), 60)
	parts = []
	if hours:
		parts.append(f"{hours}hr")
	if mins:
		parts.append(f"{mins}m")

	return f"{prefix} " + " ".join(parts) if parts else prefix


def format_hours(hours):
	total_minutes = int(round(flt(hours) * 60))
	if total_minutes <= 0:
		return ""

	h, m = divmod(total_minutes, 60)
	parts = []
	if h:
		parts.append(f"{h}h")
	if m:
		parts.append(f"{m}m")

	return " ".join(parts)


def as_timedelta(value):
	if isinstance(value, timedelta):
		return value
	if isinstance(value, time):
		return timedelta(hours=value.hour, minutes=value.minute, seconds=value.second)
	return to_timedelta(value)