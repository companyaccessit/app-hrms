frappe.ui.form.on("Announcement", {
    refresh(frm) {
        frm.set_df_property("general_manager", "read_only", frm.doc.is_approved ? 1 : 0);
        frm.set_df_property("managing_director", "read_only", frm.doc.is_approved ? 1 : 0);

        if (frm.doc.docstatus === 1 && !frm.doc.is_approved) {
            frm.add_custom_button("Approved", () => {
                if (!frm.doc.general_manager || !frm.doc.managing_director) {
                    frappe.msgprint({
                        title: "Cannot Approve",
                        message: "Both <b>General Manager</b> and <b>Managing Director</b> signatures are required before approval.",
                        indicator: "red"
                    });
                    return;
                }

                frappe.confirm(
                    "Mark this Announcement as Approved? Signatures will be locked after this.",
                    () => {
                        frappe.call({
                            method: "frappe.client.set_value",
                            args: {
                                doctype: "Announcement",
                                name: frm.doc.name,
                                fieldname: {
                                    is_approved: 1,
                                    approved_date: frappe.datetime.get_today()
                                }
                            },
                            callback: () => {
                                frappe.show_alert({ message: "Announcement Approved", indicator: "green" });
                                frm.reload_doc();
                            }
                        });
                    }
                );
            }).addClass("btn-primary");
        }
    }
});