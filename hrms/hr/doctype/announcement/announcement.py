# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Announcement(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		announcement_by: DF.Link | None
		approved_date: DF.Date | None
		company: DF.Link | None
		content: DF.TextEditor | None
		department: DF.Link | None
		employee_name: DF.Data | None
		end_date: DF.Date | None
		is_approved: DF.Check
		memo: DF.Data | None
		posting_date: DF.Date
		reference: DF.Data | None
		start_date: DF.Date | None
		title: DF.Data
	# end: auto-generated types

 
	def validate(self):
		if self.is_approved and self.has_value_changed("general_manager"):
			frappe.throw("General Manager signature cannot be changed after approval.")
   
		if self.is_approved and self.has_value_changed("managing_director"):frappe.throw("Managing Director signature cannot be changed after approval.")
            