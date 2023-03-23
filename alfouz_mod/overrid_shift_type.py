from __future__ import unicode_literals
import itertools
from datetime import timedelta

import frappe
from frappe.model.document import Document
from frappe.utils import cint, getdate, get_datetime
from erpnext.hr.doctype.shift_assignment.shift_assignment import get_actual_start_end_datetime_of_shift, get_employee_shift
from erpnext.hr.doctype.employee_checkin.employee_checkin import mark_attendance_and_link_log, calculate_working_hours
from erpnext.hr.doctype.attendance.attendance import mark_attendance
from erpnext.hr.doctype.employee.employee import get_holiday_list_for_employee
from erpnext.hr.doctype.shift_type.shift_type import ShiftType
from frappe import _


class overrid_shift_type(ShiftType):
	def get_attendance(self, logs):
		"""Return attendance_status, working_hours, late_entry, early_exit, in_time, out_time
		for a set of logs belonging to a single shift.
		Assumtion:
			1. These logs belongs to an single shift, single employee and is not in a holiday date.
			2. Logs are in chronological order
		"""
		late_entry = early_exit = False
		total_working_hours, in_time, out_time = calculate_working_hours(logs, self.determine_check_in_and_check_out, self.working_hours_calculation_based_on)
		if cint(self.enable_entry_grace_period) and in_time and in_time > logs[0].shift_start + timedelta(minutes=cint(self.late_entry_grace_period)):
			late_entry = True

		if cint(self.enable_exit_grace_period) and out_time and out_time < logs[0].shift_end - timedelta(minutes=cint(self.early_exit_grace_period)):
			early_exit = True
			
		if cint(self.minutes_delay_threshold_for_absent) and in_time and in_time > logs[0].shift_start + timedelta(minutes=cint(self.minutes_delay_threshold_for_absent)):
			frappe.msgprint(_("Please select"))
			return 'Absent', total_working_hours, late_entry, early_exit, in_time, out_time
		if self.working_hours_threshold_for_absent and total_working_hours < self.working_hours_threshold_for_absent:
			return 'Absent', total_working_hours, late_entry, early_exit, in_time, out_time
		if self.working_hours_threshold_for_half_day and total_working_hours < self.working_hours_threshold_for_half_day:
			return 'Half Day', total_working_hours, late_entry, early_exit, in_time, out_time
		return 'Present', total_working_hours, late_entry, early_exit, in_time, out_time
