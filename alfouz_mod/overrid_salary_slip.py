# from erpnext.hr.doctype.employee_checkin.employee_checkin import EmployeeCheckin
import frappe
from erpnext.payroll.doctype.salary_slip.salary_slip import SalarySlip
from erpnext.hr.doctype.shift_assignment.shift_assignment import get_actual_start_end_datetime_of_shift
from frappe.model.document import Document
import datetime, math
from frappe.utils import now, cint, get_datetime ,getdate
from frappe.utils import add_days, cint, cstr, flt, getdate, rounded, date_diff, money_in_words, formatdate, get_first_day
from frappe import _


class overrid_salary_slip(SalarySlip):
	def get_working_days_details(self, joining_date=None, relieving_date=None, lwp=None, for_preview=0):
		payroll_based_on = frappe.db.get_value("Payroll Settings", None, "payroll_based_on")
		include_holidays_in_total_working_days = frappe.db.get_single_value("Payroll Settings", "include_holidays_in_total_working_days")

		working_days = date_diff(self.end_date, self.start_date) + 1
		if for_preview:
			self.total_working_days = working_days
			self.payment_days = working_days
			return

		holidays = self.get_holidays_for_employee(self.start_date, self.end_date)

		if not cint(include_holidays_in_total_working_days):
			working_days -= len(holidays)
			if working_days < 0:
				frappe.throw(_("There are more holidays than working days this month."))

		if not payroll_based_on:
			frappe.throw(_("Please set Payroll based on in Payroll settings"))

		if payroll_based_on == "Attendance":
			actual_lwp, absent = self.calculate_lwp_ppl_and_absent_days_based_on_attendance(holidays)
			self.absent_days = absent
			self.late_in = calculate_late_houres(self)
			self.early_out = calculate_early_exit(self)
			self.exit_permit = calculate_exit_permit(self)
			self.forget_fingerprint=calculate_forget_fingerprints(self)
		else:
			actual_lwp = self.calculate_lwp_or_ppl_based_on_leave_application(holidays, working_days)

		if not lwp:
			lwp = actual_lwp
		elif lwp != actual_lwp:
			frappe.msgprint(_("Leave Without Pay does not match with approved {} records")
				.format(payroll_based_on))

		self.leave_without_pay = lwp
		self.total_working_days = working_days

		payment_days = self.get_payment_days(joining_date,
			relieving_date, include_holidays_in_total_working_days)

		if flt(payment_days) > flt(lwp):
			self.payment_days = flt(payment_days) - flt(lwp)

			if payroll_based_on == "Attendance":
				self.payment_days -= flt(absent)

			# unmarked_days = self.get_unmarked_days(include_holidays_in_total_working_days)
			unmarked_days = self.get_unmarked_days()
			consider_unmarked_attendance_as = frappe.db.get_value("Payroll Settings", None, "consider_unmarked_attendance_as") or "Present"

			if payroll_based_on == "Attendance" and consider_unmarked_attendance_as =="Absent":
				self.absent_days += unmarked_days #will be treated as absent
				self.payment_days -= unmarked_days
				if include_holidays_in_total_working_days:
					for holiday in holidays:
						if not frappe.db.exists("Attendance", {"employee": self.employee, "attendance_date": holiday, "docstatus": 1 }):
							self.payment_days += 1
		else:
			self.payment_days = 0
# def get_leave_details(employee, date):
# 	allocation_records = get_leave_allocation_records(employee, date)
# 	leave_allocation = {}
# 	for d in allocation_records:
# 		allocation = allocation_records.get(d, frappe._dict())

# 		total_allocated_leaves = frappe.db.get_value('Leave Allocation', {
# 			'from_date': ('<=', date),
# 			'to_date': ('>=', date),
# 			'leave_type': allocation.leave_type,
# 			'employee': employee,
# 			'docstatus': 1
# 		}, 'SUM(total_leaves_allocated)') or 0

# 		remaining_leaves = get_leave_balance_on(employee, d, date, to_date = allocation.to_date,
# 			consider_all_leaves_in_the_allocation_period=True)

# 		end_date = allocation.to_date
# 		leaves_taken = get_leaves_for_period(employee, d, allocation.from_date, end_date) * -1
# 		leaves_pending = get_pending_leaves_for_period(employee, d, allocation.from_date, end_date)

# 		leave_allocation[d] = {
# 			"total_leaves": total_allocated_leaves,
# 			"expired_leaves": max(total_allocated_leaves - (remaining_leaves + leaves_taken), 0),
# 			"leaves_taken": leaves_taken,
# 			"pending_leaves": leaves_pending,
# 			"remaining_leaves": remaining_leaves}

# 	#is used in set query
# 	lwps = frappe.get_list("Leave Type", filters = {"is_lwp": 1})
# 	lwps = [lwp.name for lwp in lwps]

# 	ret = {
# 		'leave_allocation': leave_allocation,
# 		'leave_approver': get_leave_approver(employee),
# 		'lwps': lwps
# 	}

# 	return ret

def get_emp_and_leave_details(self):
	'''First time, load all the components from salary structure'''
	if self.employee:
		self.set("earnings", [])
		self.set("deductions", [])

		if not self.salary_slip_based_on_timesheet:
			self.get_date_details()
		self.validate_dates()
		joining_date, relieving_date = frappe.get_cached_value("Employee", self.employee,
			["date_of_joining", "relieving_date"])

		self.get_leave_details(joining_date, relieving_date)
		struct = self.check_sal_struct(joining_date, relieving_date)

		if struct:
			self._salary_structure_doc = frappe.get_doc('Salary Structure', struct)
			self.salary_slip_based_on_timesheet = self._salary_structure_doc.salary_slip_based_on_timesheet or 0
			self.set_time_sheet()
			self.pull_sal_struct()
def get_emp_and_leave_details(self):
	'''First time, load all the components from salary structure'''
	if self.employee:
		self.set("earnings", [])
		self.set("deductions", [])

		if not self.salary_slip_based_on_timesheet:
			self.get_date_details()
		self.validate_dates()
		joining_date, relieving_date = frappe.get_cached_value("Employee", self.employee,
			["date_of_joining", "relieving_date"])

		self.get_leave_details(joining_date, relieving_date)
		struct = self.check_sal_struct(joining_date, relieving_date)

		if struct:
			self._salary_structure_doc = frappe.get_doc('Salary Structure', struct)
			self.salary_slip_based_on_timesheet = self._salary_structure_doc.salary_slip_based_on_timesheet or 0
			self.set_time_sheet()
			self.pull_sal_struct()

def set_time_sheet(self):
	if self.salary_slip_based_on_timesheet:
		self.set("timesheets", [])
		timesheets = frappe.db.sql(""" select * from `tabTimesheet` where employee = %(employee)s and start_date BETWEEN %(start_date)s AND %(end_date)s and (status = 'Submitted' or
			status = 'Billed')""", {'employee': self.employee, 'start_date': self.start_date, 'end_date': self.end_date}, as_dict=1)

		for data in timesheets:
			self.append('timesheets', {
				'time_sheet': data.name,
				'working_hours': data.total_hours
			})

def pull_sal_struct(self):
	from erpnext.hr.doctype.salary_structure.salary_structure import make_salary_slip

	if self.salary_slip_based_on_timesheet:
		self.salary_structure = self._salary_structure_doc.name
		self.hour_rate = self._salary_structure_doc.hour_rate
		self.total_working_hours = sum([d.working_hours or 0.0 for d in self.timesheets]) or 0.0
		wages_amount = self.hour_rate * self.total_working_hours

		self.add_earning_for_hourly_wages(self, self._salary_structure_doc.salary_component, wages_amount)

	make_salary_slip(self._salary_structure_doc.name, self)

def calculate_late_houres(doc):
    attendances = frappe.db.sql('''
    SELECT attendance_date, status, leave_type ,  in_time
    FROM `tabAttendance`
    WHERE
    status = "Present" AND 
	late_entry = 1
    AND employee = %s
    AND docstatus = 1
    AND attendance_date between %s and %s
    ''', values=(doc.employee, doc.start_date, doc.end_date), as_dict=1)
    total_minutes_delay = 0
    for t in attendances:
        shift_actual_timings = get_actual_start_end_datetime_of_shift(doc.employee, get_datetime(t.in_time), True)
        start = shift_actual_timings[2].start_datetime
        end =get_datetime(t.in_time)
        diff_time = end - start
        total_minutes_delay += round (diff_time.total_seconds() / 60)
    return (total_minutes_delay )
    
def calculate_early_exit(doc):
	shift_type=fetch_shift(doc)
	if not (shift_type):
		frappe.msgprint(_("This employee dose not have shift assignment active to determine the delay time"))
	attendances = frappe.db.sql('''
    SELECT attendance_date, status, leave_type ,  out_time
    FROM `tabAttendance`
    WHERE
    status = "Present"  
	AND early_exit = 1
    AND employee = %s
    AND docstatus = 1
    AND attendance_date between %s and %s
    ''', values=(doc.employee, doc.start_date, doc.end_date), as_dict=1)
	total_early_out = 0
	for t in attendances:
		shift_actual_timings = get_actual_start_end_datetime_of_shift(doc.employee, get_datetime(t.out_time), True)
		start = get_datetime(t.out_time)
		end = shift_actual_timings[2].end_datetime
		diff_time = end - start
		total_early_out += round (diff_time.total_seconds() / 60)
		print(total_early_out)
	return (total_early_out )

def fetch_shift(self):
        shift_actual_timings = get_actual_start_end_datetime_of_shift(self.employee, get_datetime(self.start_date), True)
        if shift_actual_timings[2]:
            return (shift_actual_timings[2].shift_type.name)
        else:
            return ( None)
def calculate_forget_fingerprints(doc):
	total_number_of_forget_fingerprints= 0
	attendances = frappe.db.sql('''
    SELECT attendance_date, status, leave_type ,  in_time
    FROM `tabAttendance`
    WHERE
    (status = "Absent") AND (out_time is NULL) AND (in_time is not NULL)
    AND employee = %s
    AND docstatus = 1
    AND attendance_date between %s and %s
    ''', values=(doc.employee, doc.start_date, doc.end_date), as_dict=1)
	total_number_of_forget_fingerprints = len(attendances)
	return total_number_of_forget_fingerprints 

def calculate_exit_permit(doc):
	total_duration= 0
	exit_permit = frappe.db.sql('''
         SELECT from_time , to_time , duration , to_date
         FROM `tabexit permit`
         WHERE
         docstatus = 1 
	 	 AND employee = %s
         AND to_date between %s and %s
         ''', values=(doc.employee, doc.start_date, doc.end_date), as_dict=1)
	if exit_permit:
		total_duration = exit_permit[0].duration
		total_duration = sum(item['duration'] for item in exit_permit)
	return total_duration
	