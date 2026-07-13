frappe.listview_settings["Announcement"] = {
    formatters: {
        company: function (value) {
            return value ? value : "All Company";
        }
    },
    get_indicator(doc) {
        if (doc.docstatus === 0) {
            return ["Draft", "red", "docstatus,=,0"];
        }
        if (doc.docstatus === 1 && doc.is_approved) {
            return ["Approved", "green", "is_approved,=,1"];
        }
        if (doc.docstatus === 1 && !doc.is_approved) {
            return ["Review", "orange", "is_approved,=,0"];
        }
        if (doc.docstatus === 2) {
            return ["Cancelled", "grey", "docstatus,=,2"];
        }
    },

    onload(listview) {
        listview.$result.on("render-complete", () => paint_approved_rows(listview));
    },

    refresh(listview) {
        paint_approved_rows(listview);
    }
};

function paint_approved_rows(listview) {
    setTimeout(() => {
        const approved_names = listview.data
            .filter((doc) => doc.is_approved)
            .map((doc) => doc.name);

        let css = "";
        approved_names.forEach((name) => {
            css += `
                .list-row-container[data-name="${CSS.escape(name)}"] {
                    background-color: #d9f2e3 !important;
                }
                .list-row-container[data-name="${CSS.escape(name)}"] .list-row-col,
                .list-row-container[data-name="${CSS.escape(name)}"] .list-row,
                .list-row-container[data-name="${CSS.escape(name)}"] [class*="col"] {
                    background-color: transparent !important;
                }
            `;
        });

        $("#announcement-approved-style").remove();
        $("<style>").attr("id", "announcement-approved-style").html(css).appendTo("head");
    }, 150);
}