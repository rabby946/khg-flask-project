from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from functools import wraps
from models import Admin, Donation, Loan, MembershipApplication, Member, LoanApplication, Notification, VoteItem, LoanTransaction, Vote, AuditLog
from extensions import db
from utils import upload_to_imgbb
from sqlalchemy import desc , asc, func
admin_app = Blueprint("admin", __name__, url_prefix="/admin")
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
@admin_app.context_processor
def inject_now():
    return {'year': datetime.now().year}

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("Login required", "error")
            return redirect(url_for('public.login'))
        return view(*args, **kwargs)
    return wrapped

@admin_app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username= request.form.get("username")
        password = request.form.get("password")
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.password_hash == password:
            session["admin_logged_in"] = True
            session["admin_id"] = admin.admin_id
            flash("Login successful!", "success")
            return redirect(url_for("admin.dashboard"))
        flash("Invalid email or password!", "danger")
    return render_template("public/login.html")

@admin_app.route("/")
@admin_app.route("/dashboard")
@admin_required
def dashboard():
    # Total donations ever
    total_donations = db.session.query(
        db.func.coalesce(db.func.sum(Donation.amount), 0)
    ).scalar()

    # Total funds = donations - borrowed + repaid
    borrow_sum = db.session.query(
        db.func.coalesce(db.func.sum(LoanTransaction.amount), 0)
    ).filter_by(transaction_type="borrow").scalar()

    repay_sum = db.session.query(
        db.func.coalesce(db.func.sum(LoanTransaction.amount), 0)
    ).filter_by(transaction_type="repay").scalar()

    total_funds = total_donations - borrow_sum + repay_sum

    # Pending counts
    pending_memberships = MembershipApplication.query.filter_by(status="pending").count()
    pending_loans = LoanApplication.query.filter_by(status="pending").count()

    # Recent 5 pending items
    recent_memberships = (MembershipApplication.query
                          .filter_by(status="pending")
                          .order_by(MembershipApplication.id.desc())
                          .limit(5)
                          .all())
    recent_loans = (LoanApplication.query
                    .filter_by(status="pending")
                    .order_by(LoanApplication.application_id.desc())
                    .limit(5)
                    .all())

    # Admin info
    admin = Admin.query.get_or_404(session["admin_id"])

    # Sum of monthly donations in last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    monthly_donations_last_30_days = db.session.query(
        func.coalesce(func.sum(Donation.amount), 0)
    ).filter(
        func.lower(Donation.donation_type) == "monthly",
        Donation.donated_at >= thirty_days_ago
    ).scalar()

    return render_template(
        "admin/dashboard.html",
        total_funds=total_funds,
        total_donations=total_donations,
        pending_memberships=pending_memberships,
        pending_loans=pending_loans,
        recent_memberships=recent_memberships,
        recent_loans=recent_loans,
        admin=admin,
        monthly_donations_last_30_days=monthly_donations_last_30_days
    )

#membership
@admin_app.route("/memberships")
def memberships():
    # ✅ Protect route: only logged-in admins allowed
    if not session.get("admin_logged_in"):
        flash("Please log in as admin first.", "warning")
        return redirect(url_for("public.home"))

    applications = MembershipApplication.query.order_by(MembershipApplication.applied_at.desc()).all()
    return render_template("admin/memberships.html", applications=applications)

@admin_app.route("/membership-applications/<int:app_id>")
def application_details(app_id):
    application = MembershipApplication.query.get_or_404(app_id)
    return render_template("admin/application_details.html", application=application)


@admin_app.route("/memberships/approve/<int:app_id>")
def approve_membership(app_id):
    app = MembershipApplication.query.get_or_404(app_id)

    if app.status != "pending":
        flash("This application has already been reviewed.", "warning")
        return redirect(url_for("admin.memberships"))
    # Move application into Members table
    new_member = Member(name=app.name, father_name=app.father_name,email=app.email,phone=app.phone,address=app.address,gender=app.gender,date_of_birth=app.date_of_birth,oath_paper_url=app.oath_paper_url,nid=app.nid,password_hash=app.password_hash,occupation=app.occupation,photo_url=app.photo_url,join_date=datetime.utcnow())
    db.session.add(new_member)
    # Update application status
    app.status = "approved"
    db.session.commit()
    flash(f"Membership approved for {app.name}", "success")
    return redirect(url_for("admin.memberships"))

@admin_app.route("/memberships/reject/<int:app_id>")
def reject_membership(app_id):
    app = MembershipApplication.query.get_or_404(app_id)
    if app.status != "pending":
        flash("This application has already been reviewed.", "warning")
        return redirect(url_for("admin.memberships"))
    app.status = "rejected"
    db.session.commit()
    flash(f"Membership rejected for {app.name}", "danger")
    return redirect(url_for("admin.memberships"))

@admin_app.route("/delete_membership/<int:app_id>", methods=["POST"])
def delete_membership(app_id):
    if not session.get("admin_logged_in"):
        flash("Please log in first.", "warning")
        return redirect(url_for("public.home"))
    app = MembershipApplication.query.get_or_404(app_id)
    if app.status != "rejected":
        flash("Only rejected applications can be deleted.", "danger")
        return redirect(url_for("admin.dashboard"))
    db.session.delete(app)
    db.session.commit()
    flash("Membership application deleted permanently.", "success")
    return redirect(url_for("admin.dashboard"))

# Loan applications list
# Loan applications list
@admin_app.route("/loan-applications")
def loans():
    applications = LoanApplication.query.order_by(LoanApplication.submitted_at.desc()).all()
    return render_template("admin/loans.html", applications=applications)

# Loan application details
@admin_app.route("/loan-applications/<int:application_id>")
def loan_application_details(application_id):
    application = LoanApplication.query.get_or_404(application_id)
    # If voting started, fetch votes for this application
    votes = []
    votes = Vote.query.filter_by(application_id=application.application_id).all()
    return render_template("admin/loan_application_details.html", application=application, votes=votes)

# Set application for voting
@admin_app.route("/loan-applications/<int:application_id>/set-voting")
@admin_required
def set_for_voting(application_id):
    application = LoanApplication.query.get_or_404(application_id)

    if application.status in ["approved", "rejected", "voting"]:
        flash(f"Cannot set application for voting. Current status: {application.status}", "warning")
        return redirect(url_for("admin.loan_application_details", application_id=application.application_id))

    # Update status
    application.status = "voting"

    # Create a VoteItem for this loan
    vote_item = VoteItem(title=f"Loan Approval for {application.member.name}",description=f"Loan requested: {application.amount_requested}\nCause: {application.cause or 'Not specified'}",created_at=datetime.utcnow(),application_id=application.application_id)

    try:
        db.session.add(vote_item)
        db.session.commit()
        flash("Application is now set for voting and added to voting items.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error setting application for voting: {str(e)}", "danger")

    return redirect(url_for("admin.loan_application_details", application_id=application.application_id))


# Accept loan
@admin_app.route("/loan-applications/<int:application_id>/accept", methods=["POST"])
def accept_loan(application_id):
    application = LoanApplication.query.get_or_404(application_id)

    # Create loan
    loan = Loan(
        member_id=application.member_id,
        approved_amount=application.amount_requested,
        remaining_amount=application.amount_requested,
        status="ongoing",
        issued_at=datetime.utcnow()
    )
    db.session.add(loan)
    db.session.flush()  # ensure loan.loan_id available

    # Transaction
    tx = LoanTransaction(
        loan_id=loan.loan_id,
        transaction_type="borrow",
        amount=application.amount_requested,
        created_at=datetime.utcnow()
    )
    db.session.add(tx)

    # Update application metadata
    application.status = "approved"
    application.reviewed_by = session.get("admin_id")
    application.reviewed_at = datetime.utcnow()

    # Delete votes tied to this application (if any)
    # use .delete for efficiency; synchronize_session=False is OK when not relying on in-memory objects
    # Vote.query.filter_by(application_id=application.application_id).delete(synchronize_session=False)

    # Delete vote_item tied to this application (if exists)
    vote_item = VoteItem.query.filter_by(application_id=application.application_id).first()
    # if vote_item:
    #     db.session.delete(vote_item)

    # Audit log
    log = AuditLog(
        admin_id=session.get("admin_id"),
        member_id=application.member_id,
        action=f"Accepted loan application ID {application.application_id}",
        target_table="loan_applications",
        target_id=application.application_id,
        created_at=datetime.utcnow()
    )
    db.session.add(log)

    try:
        db.session.commit()
        flash("Loan accepted and issued to member.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error approving loan: {str(e)}", "danger")

    return redirect(url_for("admin.loan_application_details", application_id=application.application_id))


# Reject / Delete application
@admin_app.route("/loan-applications/delete/<int:application_id>", methods=["POST"])
def delete_loan_application(application_id):
    application = LoanApplication.query.get_or_404(application_id)
    member_id = application.member_id

    # Delete votes tied to this application
    Vote.query.filter_by(application_id=application.application_id).delete(synchronize_session=False)

    # Delete vote_item tied to this application
    vote_item = VoteItem.query.filter_by(application_id=application.application_id).first()
    if vote_item:
        db.session.delete(vote_item)

    # Audit log (record before deleting application)
    log = AuditLog(
        admin_id=session.get("admin_id"),
        member_id=member_id,
        action=f"Rejected (deleted) loan application ID {application.application_id}",
        target_table="loan_applications",
        target_id=application.application_id,
        created_at=datetime.utcnow()
    )
    db.session.add(log)

    # Delete application object
    db.session.delete(application)

    try:
        db.session.commit()
        flash("Loan application rejected successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error rejecting application: {str(e)}", "danger")

    return redirect(url_for("admin.loans"))


@admin_app.route("/fund_history", methods=["GET", "POST"])
def fund_history():
    sort_order = request.args.get("sort", "desc")  # asc or desc
    fund_type = request.args.get("type", "all")    # donation, loan_given, loan_repay
    member_id = request.args.get("member_id", "all")
    # --- Donations Query ---
    donations = (db.session.query(Donation.donation_id.label("id"),Donation.amount.label("amount"),Donation.donated_at.label("date"),Member.name.label("member_name"),db.literal("donation").label("category"),Donation.donation_type.label("subtype")).select_from(Donation).join(Member, Donation.member_id == Member.member_id))
    # --- Loan Transactions Query ---
    loan_txns = (db.session.query(LoanTransaction.transaction_id.label("id"),LoanTransaction.amount.label("amount"),LoanTransaction.created_at.label("date"),Member.name.label("member_name"),LoanTransaction.transaction_type.label("category"),db.literal("").label("subtype")).select_from(LoanTransaction).join(Loan, LoanTransaction.loan_id == Loan.loan_id).join(Member, Loan.member_id == Member.member_id))
    # Apply member filter
    if member_id != "all":
        donations = donations.filter(Donation.member_id == int(member_id))
        loan_txns = loan_txns.filter(Loan.member_id == int(member_id))

    # Apply type filter
    if fund_type == "donation":
        combined = donations
    elif fund_type == "loan_given":
        combined = loan_txns.filter(LoanTransaction.transaction_type == "borrow")
    elif fund_type == "loan_repay":
        combined = loan_txns.filter(LoanTransaction.transaction_type == "repay")
    else:
        combined = donations.union_all(loan_txns)

    # Sorting
    if sort_order == "asc":
        combined = combined.order_by(asc("date"))
    else:
        combined = combined.order_by(desc("date"))
    records = combined.all()
    members = Member.query.all()
    return render_template("admin/fund_history.html",records=records,members=members,sort_order=sort_order,fund_type=fund_type,member_id=member_id)

# --- Loan History Page ---
@admin_app.route("/loan_history")
def loan_history():
    if not session.get("admin_logged_in"):
        flash("Please log in as admin first.", "warning")
        return redirect(url_for("public.home"))

    # Get all loans (approved, rejected, completed, ongoing)
    loans = Loan.query.order_by(Loan.created_at.desc()).all()

    return render_template("admin/loan_history.html", loans=loans)


# List all members
@admin_app.route("/members")
def manage_members():
    if not session.get("admin_logged_in"):
        flash("Please log in first.", "warning")
        return redirect(url_for("public.home"))

    members = Member.query.order_by(Member.join_date.desc()).all()
    return render_template("admin/manage_members.html", members=members)


# Edit a member
@admin_app.route("/members/<int:member_id>/edit", methods=["GET", "POST"])
def edit_member(member_id):
    if not session.get("admin_logged_in"):
        flash("Please log in first.", "warning")
        return redirect(url_for("public.home"))

    member = Member.query.get_or_404(member_id)

    if request.method == "POST":
        nid = request.form.get("nid")

# Check if another member already has this NID
        nid_exists = Member.query.filter(Member.nid == nid, Member.member_id != member.member_id).first()
        if nid_exists:
            flash("NID already in use by another member.", "danger")
            return redirect(url_for("admin.edit_member", member_id=member.member_id))
        member.nid = nid
        member.name = request.form.get("name")
        member.father_name = request.form.get("father_name")
        member.email = request.form.get("email")
        member.phone = request.form.get("phone")
        member.occupation = request.form.get("occupation")
        member.address = request.form.get("address")
        member.gender = request.form.get("gender")
        member.date_of_birth = request.form.get("date_of_birth")
        photo_file = request.files.get("photo_url")
        if photo_file and photo_file.filename != "":
            member.photo_url = upload_to_imgbb(photo_file)

        oath_file = request.files.get("oath_paper_url")
        if oath_file and oath_file.filename != "":
            member.oath_paper_url = upload_to_imgbb(oath_file)

        new_password = request.form.get("password")
        if new_password:
            member.password_hash = new_password
        db.session.commit()
        flash("Member details updated successfully.", "success")
        return redirect(url_for("admin.manage_members"))

    return render_template("admin/edit_member.html", member=member)


# Delete a member (cascade delete loans/donations)
@admin_app.route("/members/<int:member_id>/delete", methods=["POST"])
def delete_member(member_id):
    if not session.get("admin_logged_in"):
        flash("Please log in first.", "warning")
        return redirect(url_for("public.home"))

    member = Member.query.get_or_404(member_id)

    # Delete related loans & donations
    for loan in member.loans:
        db.session.delete(loan)
    for donation in member.donations:
        db.session.delete(donation)

    db.session.delete(member)
    db.session.commit()
    flash(f"Member {member.name} deleted permanently.", "success")
    return redirect(url_for("admin.manage_members"))


@admin_app.route("/notifications", methods=["GET", "POST"])
def notifications():
    if not session.get("admin_logged_in"):
        flash("Please log in first.", "warning")
        return redirect(url_for("public.home"))

    members = Member.query.order_by(Member.name).all()

    if request.method == "POST":
        message = request.form.get("message")
        selected_ids = request.form.getlist("member_ids")

        if not selected_ids:
            flash("Please select at least one member.", "warning")
            return redirect(url_for("admin.notifications"))

        for member_id in selected_ids:
            notif = Notification(
                member_id=int(member_id),
                admin_id=session.get("admin_id"),
                message=message,
                notification_type="general",
                created_at=datetime.utcnow()
            )
            db.session.add(notif)

        db.session.commit()
        flash(f"Notification sent to {len(selected_ids)} member(s).", "success")
        return redirect(url_for("admin.notifications"))

    # Fetch previously sent notifications (latest first)
    notifications_list = Notification.query.order_by(Notification.created_at.desc()).all()
    return render_template("admin/notifications.html", members=members, notifications=notifications_list)


# Delete notification
@admin_app.route("/notifications/<int:notification_id>/delete", methods=["POST"])
def delete_notification(notification_id):
    if not session.get("admin_logged_in"):
        flash("Please log in first.", "warning")
        return redirect(url_for("public.home"))

    notif = Notification.query.get_or_404(notification_id)
    db.session.delete(notif)
    db.session.commit()
    flash("Notification deleted successfully.", "success")
    return redirect(url_for("admin.notifications"))

@admin_app.route("/logout")
@admin_required
def logout():
    if session.get("admin_logged_in"):
        session.pop("admin_logged_in")
        session.pop("admin_id")
        flash("Logged out successfully!", "success")
    else:
        flash("You are not logged in.", "warning")
    return redirect(url_for("public.home"))

@admin_app.route("/members/<int:member_id>")
@admin_required
def view_member(member_id):
    member = Member.query.get_or_404(member_id)
    return render_template("admin/view_member.html", member=member)


# Admin loan management page

@admin_app.route("/loan-management", methods=["GET", "POST"])
def loan_management():
    members = Member.query.order_by(Member.name).all()
    loans = Loan.query.order_by(Loan.loan_id).all()

    if request.method == "POST":
        member_id = request.form.get("member_id")
        loan_id = request.form.get("loan_id")  # can be empty if creating new loan
        action_type = request.form.get("action_type")  # borrow or repay
        amount_raw = request.form.get("amount", "0")

        # Validate member
        member = Member.query.get(member_id)
        if not member:
            flash("Selected member not found.", "danger")
            return redirect(url_for("admin.loan_management"))

        # Parse amount safely
        try:
            amount = Decimal(amount_raw)
            if amount <= 0:
                raise InvalidOperation
        except (InvalidOperation, TypeError):
            flash("Please enter a valid positive amount.", "danger")
            return redirect(url_for("admin.loan_management"))

        try:
            if action_type == "repay":
                # must have a loan selected
                if not loan_id:
                    flash("Please select a loan to apply repayment.", "warning")
                    return redirect(url_for("admin.loan_management"))

                loan = Loan.query.get_or_404(loan_id)

                # IMPORTANT: server-side ownership check
                if loan.member_id != member.member_id:
                    flash("Selected loan does not belong to the selected member. Choose the correct loan.", "danger")
                    return redirect(url_for("admin.loan_management"))

                # Deduct repayment from remaining_amount (Decimal arithmetic)
                loan.remaining_amount = (loan.remaining_amount or Decimal("0.00")) - amount

                # Handle overpayment -> convert extra to donation
                if loan.remaining_amount <= 0:
                    if loan.remaining_amount < 0:
                        extra = abs(loan.remaining_amount)
                        donation = Donation(
                            member_id=loan.member_id,
                            amount=extra,
                            donation_type="Extra repayment"
                        )
                        db.session.add(donation)
                        flash(f"Extra {extra} converted to donation.", "info")

                    loan.remaining_amount = Decimal("0.00")
                    loan.status = "paid"

                # Create repayment transaction
                transaction = LoanTransaction(
                    loan_id=loan.loan_id,
                    transaction_type="repay",
                    amount=amount,
                )
                db.session.add(transaction)

                # Audit log
                audit = AuditLog(
                    member_id=loan.member_id,
                    admin_id=session.get("admin_id"),
                    action=f"{member.name} repaid {amount} for Loan ID {loan.loan_id}"
                )
                db.session.add(audit)

                # Notification -> send to the loan owner (safe)
                notification = Notification(
                    member_id=loan.member_id,
                    admin_id=session.get("admin_id"),
                    message=(
                        f"Your repayment of {amount} has been recorded. "
                        f"Original loan: {loan.approved_amount}, Remaining: {loan.remaining_amount}. "
                        f"Issued at: {loan.issued_at}"
                    )
                )
                db.session.add(notification)

            elif action_type == "borrow":
                # Create new loan (no application)
                loan = Loan(
                    member_id=member.member_id,
                    approved_amount=amount,
                    remaining_amount=amount,
                    status="ongoing",
                )
                db.session.add(loan)
                db.session.flush()  # get loan.loan_id

                # Create borrow transaction
                transaction = LoanTransaction(
                    loan_id=loan.loan_id,
                    transaction_type="borrow",
                    amount=amount,
                )
                db.session.add(transaction)

                # Audit log
                audit = AuditLog(
                    member_id=member.member_id,
                    admin_id=session.get("admin_id"),
                    action=f"{member.name} borrowed {amount} (Loan ID {loan.loan_id})"
                )
                db.session.add(audit)

                # Notification
                notification = Notification(
                    member_id=member.member_id,
                    admin_id=session.get("admin_id"),
                    message=f"A new loan of {amount} has been issued to you."
                )
                db.session.add(notification)

            db.session.commit()
            flash("Loan action completed successfully.", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

        return redirect(url_for("admin.loan_management"))

    return render_template("admin/loan_management.html", members=members, loans=loans)

@admin_app.route("/add-donation", methods=["GET", "POST"])
def add_donation():
    members = Member.query.order_by(Member.name).all()
    donations = Donation.query.order_by(Donation.donated_at.desc()).limit(50).all()

    if request.method == "POST":
        member_id = request.form.get("member_id")
        amount = request.form.get("amount")
        donation_type = request.form.get("donation_type") or "General"

        member = Member.query.get_or_404(member_id)

        donation = Donation(
            member_id=member.member_id,
            amount=amount,
            donation_type=donation_type
        )
        db.session.add(donation)

        # Optional: Audit log
        audit = AuditLog(
            member_id=member.member_id,
            admin_id=session.get("admin_id"),
            action=f"Admin added donation of {amount} to {member.name}"
        )
        db.session.add(audit)

        db.session.commit()
        flash("Donation added successfully.", "success")
        return redirect(url_for("admin.add_donation"))

    return render_template("admin/add_donation.html", members=members, donations=donations)
