from flask import Blueprint, render_template, current_app, request, redirect, url_for, flash, session
from extensions import db
from models import Admin, Member, MembershipApplication, AuditLog, Donation, Loan, LoanApplication
from utils import upload_to_imgbb
superadmin_app = Blueprint("superadmin", __name__, url_prefix="/superadmin")


# ------------------ LOGIN ------------------
@superadmin_app.route("/<secret_link>", methods=["GET", "POST"])
def login(secret_link):
    if secret_link != current_app.config.get("SUPERADMIN_LINK"):
        return "Forbidden", 403

    if request.method == "POST":
        password = request.form.get("sadmin-password")
        if password == current_app.config.get("SUPERADMIN_PASSWORD"):  # ✅ match your config variable
            session["superadmin_logged_in"] = True
            flash("Login successful!", "success")
            return redirect(url_for("superadmin.dashboard"))
        else:
            flash("Invalid password!", "danger")

    return render_template("public/superlogin.html")


# ------------------ DASHBOARD ------------------
@superadmin_app.route("/")
@superadmin_app.route("/dashboard")
def dashboard():
    if not session.get("superadmin_logged_in"):
        flash("You are not logged in brother")
        return redirect(url_for("public.home"))
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()
    total_funds = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
    total_members = Member.query.count()
    pending_applications = MembershipApplication.query.filter_by(status="pending").count()
    total_admins = Admin.query.count()

    return render_template(
        "superadmin/dashboard.html",
        total_funds=total_funds,
        total_members=total_members,
        pending_applications=pending_applications,
        total_admins=total_admins, 
        recent_logs=logs
    )


# ------------------ LOGOUT ------------------
@superadmin_app.route("/logout")
def logout():
    session.pop("superadmin_logged_in", None)
    flash("Logged out successfully")
    return redirect(url_for("public.home"))


# ------------------ MANAGE ADMINS ------------------
@superadmin_app.route("/manage_admins")
def manage_admins():
    if not session.get("superadmin_logged_in"):
        flash("You are not logged in brother")
        return redirect(url_for("public.home"))

    admins = Admin.query.all()
    return render_template("superadmin/manage_admins.html", admins=admins)


@superadmin_app.route("/add_admin", methods=["GET", "POST"])
def add_admin():
    if not session.get("superadmin_logged_in"):
        flash("You are not logged in brother")
        return redirect(url_for("public.home"))

    if request.method == "POST":
        username = request.form.get("username")
        check_admin = Admin.query.filter(Admin.username==username).first()
        if check_admin:
            flash("username already exists")
            print("worng")
            return redirect(url_for("superadmin.manage_admins"))
        full_name = request.form.get("name")
        role = request.form.get("role")
        phone = request.form.get("phone")
        photo_url = upload_to_imgbb(request.files.get("photo"))
        password_hash = request.form.get("password_hash") 
        
        new_admin = Admin(username=username, full_name=full_name, password_hash=password_hash, role=role, phone=phone, photo_url=photo_url)
        db.session.add(new_admin)
        db.session.commit()

        flash("Admin added successfully!", "success")
        return redirect(url_for("superadmin.manage_admins"))
    return render_template("superadmin/add_admin.html")


@superadmin_app.route("/delete_admin/<int:admin_id>", methods=["POST"])
def delete_admin(admin_id):
    if not session.get("superadmin_logged_in"):
        flash("You are not logged in brother")
        return redirect(url_for("public.home"))

    admin = Admin.query.get_or_404(admin_id)
    db.session.delete(admin)
    db.session.commit()

    flash("Admin deleted successfully!", "success")
    return redirect(url_for("superadmin.manage_admins"))


# ------------------ AUDIT LOGS ------------------
@superadmin_app.route("/audit-logs", methods=["GET", "POST"])
# @superadmin_required
def view_audit_logs():
    admin_id = request.args.get("admin_id", "all")
    member_id = request.args.get("member_id", "all")
    target_table = request.args.get("target_table", "all")

    logs = AuditLog.query

    if admin_id != "all":
        logs = logs.filter_by(admin_id=int(admin_id))
    if member_id != "all":
        logs = logs.filter_by(member_id=int(member_id))
    if target_table != "all":
        logs = logs.filter_by(target_table=target_table)

    logs = logs.order_by(AuditLog.created_at.desc()).all()

    admins = Admin.query.order_by(Admin.full_name).all()
    members = Member.query.order_by(Member.name).all()
    target_tables = db.session.query(AuditLog.target_table.distinct()).all()
    target_tables = [t[0] for t in target_tables if t[0]]

    return render_template(
        "superadmin/view_audit_logs.html",
        logs=logs,
        admins=admins,
        members=members,
        target_tables=target_tables,
        selected_admin=admin_id,
        selected_member=member_id,
        selected_target_table=target_table
    )


# ------------------ REPORTS ------------------
@superadmin_app.route("/super_admin_reports")
def super_admin_reports():
    if not session.get("superadmin_logged_in"):
        flash("You are not logged in brother")
        return redirect(url_for("public.home"))

    total_donations = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
    total_members = Member.query.count()
    total_loans = Loan.query.count()
    pending_loans = LoanApplication.query.filter_by(status="pending").count()
    repaid_loans = Loan.query.filter_by(status="paid").count()
    pending_loans_count = Loan.query.filter_by(status="ongoing").count()

    # For charts
    donation_data = db.session.query(Donation.donation_type, db.func.sum(Donation.amount)) \
                              .group_by(Donation.donation_type).all()
    donation_labels = [row[0] for row in donation_data]
    donation_values = [float(row[1]) for row in donation_data]

    return render_template(
        "superadmin/super_admin_reports.html",
        total_donations=total_donations,
        total_members=total_members,
        total_loans=total_loans,
        pending_loans=pending_loans,
        donation_labels=donation_labels,
        donation_values=donation_values,
        repaid_loans=repaid_loans,
        pending_loans_count=pending_loans_count
    )
