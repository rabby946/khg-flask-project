from flask import Blueprint, render_template, current_app, request, redirect, url_for, flash, session

superadmin_app = Blueprint("superadmin", __name__, url_prefix="/superadmin")


# Secret login route (GET + POST)
@superadmin_app.route("/<secret_link>", methods=["GET", "POST"])
def login(secret_link):
    # Check if URL secret matches
    if secret_link != current_app.config.get("SUPERADMIN_LINK"):
        return "Forbidden", 403

    if request.method == "POST":
        password = request.form.get("sadmin-password")
        if password == current_app.config.get("SUPERADMIN_LINK"):
            session["superadmin_logged_in"] = True
            flash("Login successful!", "success")
            return redirect(url_for("superadmin.dashboard"))  
        else:
            flash("Invalid password!", "danger")
    return render_template("public/superlogin.html")

@superadmin_app.route("/")
@superadmin_app.route("/dashboard")
def dashboard():
    if not session.get("superadmin_logged_in"):
        flash("You are not logged in brother")
        return redirect(url_for("public.home"))
    return render_template("superadmin/dashboard.html", total_funds = 0, total_members = 0, pending_applications = 0, total_admins=0)
@superadmin_app.route("/logout")
def logout():
    if not session.get("superadmin_logged_in"):
        flash("You are not logged in brother")
        return redirect(url_for("public.home"))
    session.pop("superadmin_logged_in", None)
    flash("logged out successfully")
    return redirect(url_for("public.home"))

@superadmin_app.route("/add_admin")
def add_admin():
    if not session.get("superadmin_logged_in"):
        flash("You are not logged in brother")
        return redirect(url_for("public.home"))
    return "working add admin"

@superadmin_app.route("/delete_admin")
def delete_admin():
    if not session.get("superadmin_logged_in"):
        flash("You are not logged in brother")
        return redirect(url_for("public.home"))
    return "working delete admin"

@superadmin_app.route("/manage_admins")
def manage_admins():
    if not session.get("superadmin_logged_in"):
        flash("You are not logged in brother")
        return redirect(url_for("public.home"))
    admins = []
    return render_template("superadmin/manage_admins.html", admins=admins)

@superadmin_app.route("/view_audit_logs")
def view_audit_logs():
    if not session.get("superadmin_logged_in"):
        flash("You are not logged in brother")
        return redirect(url_for("public.home"))
    view_audit_logs = []
    return render_template("superadmin/view_audit_logs.html", audit_logs=view_audit_logs)

@superadmin_app.route("/super_admin_reports")
def super_admin_reports():
    if not session.get("superadmin_logged_in"):
        flash("You are not logged in brother")
        return redirect(url_for("public.home"))
    donation_labels = []
    donation_values = []
    return render_template("superadmin/super_admin_reports.html",
                       total_donations=0, total_members=0, total_loans=0,
                       pending_loans=0, donation_labels=donation_labels,
                       donation_values=donation_values, repaid_loans=0,
                       pending_loans_count=0)

