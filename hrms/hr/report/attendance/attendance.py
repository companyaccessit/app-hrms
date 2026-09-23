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

	if not filters.employee:
		frappe.throw(_("Please select an Employee"))

	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("Start Date cannot be after End Date"))


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Data", "width": 90},
		{"label": _("Day"), "fieldname": "day", "fieldtype": "Data", "width": 70},
		{"label": _("In"), "fieldname": "in_time", "fieldtype": "Data", "width": 80},
		{"label": _("Out"), "fieldname": "out_time", "fieldtype": "Data", "width": 80},
		{"label": _("Work Hrs"), "fieldname": "work_hrs", "fieldtype": "Data", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
	]


def get_data(filters):
	from_date = getdate(filters.from_date)
	to_date = getdate(filters.to_date)
	today_date = getdate(today())

	employee = frappe.db.get_value(
		"Employee",
		filters.employee,
		["employee_name", "date_of_joining", "relieving_date", "default_shift"],
		as_dict=True,
	)
	if not employee:
		frappe.throw(_("Employee {0} not found").format(filters.employee))

	records = get_attendance_records(filters.employee, from_date, to_date)
	shift_info = get_shift_info(records, employee.default_shift)
	holidays = get_holiday_dates(filters.employee, from_date, to_date)

	# One employee can (rarely) have several attendance records on a day (multiple shifts)
	records_by_date = {}
	for rec in records:
		records_by_date.setdefault(getdate(rec.attendance_date), []).append(rec)

	data = []
	current = from_date
	while current <= to_date:
		if current in records_by_date:
			for rec in records_by_date[current]:
				data.append(build_row_from_record(rec, employee.default_shift, shift_info))

		elif current in holidays:
			data.append(build_row(current, status="Holiday"))

		elif is_absent_candidate(current, today_date, employee):
			# No Attendance record at all -> treat as Absent
			data.append(build_row(current, status="Absent"))

		current = getdate(add_days(current, 1))

	if filters.status:
		data = [row for row in data if matches_status(row["status"], filters.status)]

	# Not a visible column, only used by the print format header
	for row in data:
		row["employee_name"] = employee.employee_name

	return data


def matches_status(row_status, selected):
	# "Late" matches every "Late 7m", "Late 1hr 25m" ... row
	if selected == "Late":
		return row_status.startswith("Late")

	return row_status == selected


def get_attendance_records(employee, from_date, to_date):
	return frappe.get_all(
		"Attendance",
		filters={
			"employee": employee,
			"attendance_date": ["between", [from_date, to_date]],
			"docstatus": ["<", 2],  # draft + submitted, ignore cancelled
		},
		fields=[
			"name",
			"attendance_date",
			"status",
			"shift",
			"in_time",
			"out_time",
			"working_hours",
			"late_entry",
		],
		order_by="attendance_date asc, in_time asc",
	)


def get_shift_info(records, default_shift):
	"""Return {shift_name: {start: timedelta, grace: minutes}}"""
	shift_names = {rec.shift for rec in records if rec.shift}
	if default_shift:
		shift_names.add(default_shift)

	if not shift_names:
		return {}

	# Grace period fields differ between HRMS versions, so only query what exists
	meta = frappe.get_meta("Shift Type")
	has_toggle = meta.has_field("enable_entry_grace_period")
	has_grace = meta.has_field("late_entry_grace_period")

	fields = ["name", "start_time"]
	if has_toggle:
		fields.append("enable_entry_grace_period")
	if has_grace:
		fields.append("late_entry_grace_period")

	shifts = frappe.get_all(
		"Shift Type",
		filters={"name": ["in", list(shift_names)]},
		fields=fields,
	)

	info = {}
	for shift in shifts:
		if shift.start_time is None:
			continue

		grace = cint(shift.get("late_entry_grace_period")) if has_grace else 0
		if has_toggle and not shift.get("enable_entry_grace_period"):
			grace = 0

		info[shift.name] = frappe._dict(start=as_timedelta(shift.start_time), grace=grace)
	return info


def get_holiday_dates(employee, from_date, to_date):
	try:
		from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
	except ImportError:
		return set()

	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if not holiday_list:
		return set()

	dates = frappe.get_all(
		"Holiday",
		filters={"parent": holiday_list, "holiday_date": ["between", [from_date, to_date]]},
		pluck="holiday_date",
	)
	return {getdate(d) for d in dates}


def is_absent_candidate(date, today_date, employee):
	# Only past days can be marked as absent (today may not be checked in yet)
	if date >= today_date:
		return False

	if employee.date_of_joining and date < getdate(employee.date_of_joining):
		return False

	if employee.relieving_date and date > getdate(employee.relieving_date):
		return False

	return True


def build_row_from_record(rec, default_shift, shift_info):
	in_time = get_datetime(rec.in_time) if rec.in_time else None
	out_time = get_datetime(rec.out_time) if rec.out_time else None

	late_minutes = get_late_minutes(rec, in_time, default_shift, shift_info)

	working_hours = flt(rec.working_hours)
	if not working_hours and in_time and out_time and out_time > in_time:
		working_hours = (out_time - in_time).total_seconds() / 3600

	return build_row(
		getdate(rec.attendance_date),
		in_time=in_time,
		out_time=out_time,
		working_hours=working_hours,
		status=get_status(rec, in_time, late_minutes),
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


def build_row(date, in_time=None, out_time=None, working_hours=0, status=""):
	return {
		"date": f"{MONTHS[date.month - 1]} {date.day:02d}",  # Aug 01
		"day": DAYS[date.weekday()],  # Sat, Sun, Mon ...
		"in_time": in_time.strftime("%H:%M") if in_time else "",
		"out_time": out_time.strftime("%H:%M") if out_time else "",
		"work_hrs": format_hours(working_hours),
		"status": status,
	}


def get_status(rec, in_time, late_minutes):
	if rec.status in ("On Leave", "Half Day"):
		return rec.status

	# The record may say "Absent" (auto attendance marks it when working hours are
	# below the shift threshold), but if the employee punched in, judge by the punch.
	if rec.status == "Absent" and not in_time:
		return "Absent"

	if late_minutes is not None:
		return format_late(late_minutes)

	return "On Time"


def format_late(minutes):
	hours, mins = divmod(int(minutes), 60)
	parts = []
	if hours:
		parts.append(f"{hours}hr")
	if mins:
		parts.append(f"{mins}m")

	return "Late " + " ".join(parts) if parts else "Late"


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