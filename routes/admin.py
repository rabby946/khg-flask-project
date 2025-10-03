from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app
from functools import wraps
from models import Admin, Donation, Loan, MembershipApplication, Member, LoanApplication, Notification, VoteItem, LoanTransaction, Vote, AuditLog
from extensions import db, mail
from utils import upload_to_imgbb, _send_async_email, sendMailhtml1, admin_required
from sqlalchemy import desc , asc, func
import threading
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
admin_app = Blueprint("admin", __name__, url_prefix="/admin")
from werkzeug.security import check_password_hash, generate_password_hash
from flask import current_app

def sendMailhtml(recipient, subject, body):
    if not isinstance(recipient, list):
        recipient = [recipient]
    cur_admin = Admin.query.get(session["admin_id"])
    html_body = render_template("email_template.html",subject=subject,body=body,year=datetime.now().year,sender=cur_admin )
    app = current_app._get_current_object()
    threading.Thread(target=_send_async_email,args=(app, recipient, subject, html_body, True),daemon=True,).start()

@admin_app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username= request.form.get("username")
        password = request.form.get("password")
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
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
    total_donations = db.session.query(db.func.coalesce(db.func.sum(Donation.amount), 0)).scalar()
    borrow_sum = db.session.query(db.func.coalesce(db.func.sum(LoanTransaction.amount), 0)).filter_by(transaction_type="borrow").scalar()
    repay_sum = db.session.query(db.func.coalesce(db.func.sum(LoanTransaction.amount), 0)).filter_by(transaction_type="repay").scalar()
    total_funds = total_donations - borrow_sum + repay_sum
    pending_memberships = MembershipApplication.query.filter_by(status="pending").count()
    pending_loans = LoanApplication.query.filter_by(status="pending").count()
    recent_memberships = (MembershipApplication.query.filter_by(status="pending").order_by(MembershipApplication.id.desc()).limit(5).all())
    recent_loans = (LoanApplication.query.filter_by(status="pending").order_by(LoanApplication.application_id.desc()).limit(5).all())
    admin = Admin.query.get_or_404(session["admin_id"])
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    monthly_donations_last_30_days = db.session.query(func.coalesce(func.sum(Donation.amount), 0)).filter(func.lower(Donation.donation_type) == "monthly",Donation.donated_at >= thirty_days_ago).scalar()
    return render_template("admin/dashboard.html",total_funds=total_funds,total_donations=total_donations,pending_memberships=pending_memberships,pending_loans=pending_loans,recent_memberships=recent_memberships,recent_loans=recent_loans,admin=admin,monthly_donations_last_30_days=monthly_donations_last_30_days)


@admin_app.route("/memberships")
@admin_required
def memberships():
    applications = MembershipApplication.query.order_by(MembershipApplication.applied_at.desc()).all()
    return render_template("admin/memberships.html", applications=applications)

@admin_app.route("/membership-applications/<int:app_id>")
@admin_required
def application_details(app_id):
    application = MembershipApplication.query.get_or_404(app_id)
    return render_template("admin/application_details.html", application=application)


@admin_app.route("/memberships/approve/<int:app_id>")
@admin_required
def approve_membership(app_id):
    app = MembershipApplication.query.get_or_404(app_id)
    if app.status != "pending":
        flash("This application has already been reviewed.", "warning")
        return redirect(url_for("admin.memberships"))
    new_member = Member(name=app.name, father_name=app.father_name,email=app.email,phone=app.phone,address=app.address,gender=app.gender,date_of_birth=app.date_of_birth,oath_paper_url=app.oath_paper_url,nid=app.nid,password_hash=app.password_hash,occupation=app.occupation,photo_url=app.photo_url,join_date=datetime.utcnow())
    html_body = render_template("emails/membership_approved.html",member=new_member,year=datetime.utcnow().year,admin_role=cur_admin.role)
    new_member.password_hash = generate_password_hash(app.password_hash)
    db.session.add(new_member)
    app.status = "approved"
    db.session.commit()
    log = AuditLog(admin_id=session.get("admin_id"),member_id=new_member.member_id,action=f"Approved membership application ID {app.id}",target_table="membership_applications",target_id=app.id,amount=0)
    cur_admin = Admin.query.get_or_404(session.get("admin_id"))
    sendMailhtml1(app.email, "Membership Application Approved", html_body)
    db.session.add(log)
    db.session.commit()
    flash(f"Membership approved for {app.name}", "success")
    return redirect(url_for("admin.memberships"))

@admin_app.route("/memberships/reject/<int:app_id>")
@admin_required
def reject_membership(app_id):
    app = MembershipApplication.query.get_or_404(app_id)
    if app.status != "pending":
        flash("This application has already been reviewed.", "warning")
        return redirect(url_for("admin.memberships"))
    app.status = "rejected"
    log = AuditLog(admin_id=session.get("admin_id"),action=f"Rejected membership application of {app.name}, nid={app.nid}",target_table="membership_applications",target_id=app.id,amount=0)
    db.session.add(log)
    cur_admin = Admin.query.get_or_404(session.get("admin_id"))
    body = f"""
        <p>Dear {app.name},</p>
        <p>Thank you for your interest in joining <strong>KHG</strong>. 
        We have carefully reviewed your membership application, but unfortunately 
        it has been <strong>rejected</strong> at this time.</p>
        
        <p>If you believe this was a mistake or wish to reapply, 
        please feel free to contact our office for further clarification.</p>

        <p>We truly appreciate your effort and encourage you to stay connected 
        with our community for future opportunities.</p>
        
        <p>Best regards,<br>
        {cur_admin.full_name}<br>
        {cur_admin.role}, KHG</p>
    """
    sendMailhtml(app.email,"Membership Application Rejected",body)
    db.session.commit()
    flash(f"Membership rejected for {app.name}", "danger")
    return redirect(url_for("admin.memberships"))

@admin_app.route("/delete_membership/<int:app_id>", methods=["POST"])
@admin_required
def delete_membership(app_id):
    app = MembershipApplication.query.get_or_404(app_id)
    if app.status != "rejected":
        flash("Only rejected applications can be deleted.", "danger")
        return redirect(url_for("admin.dashboard"))
    db.session.delete(app)
    db.session.commit()
    flash("Membership application deleted permanently.", "success")
    return redirect(url_for("admin.dashboard"))

# Loan applications list
@admin_app.route("/loan-applications")
@admin_required
def loans():
    applications = LoanApplication.query.order_by(LoanApplication.submitted_at.desc()).all()
    return render_template("admin/loans.html", applications=applications)

# Loan application details
@admin_app.route("/loan-applications/<int:application_id>")
@admin_required
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
    cur_admin = Admin.query.get_or_404(session.get("admin_id"))
    member = Member.query.get_or_404(application.member_id)  
    body = f"""
        <p>Dear {member.name},</p>
        <p>We would like to inform you that your <strong>Loan Application</strong> has been 
        moved to the <strong>voting stage</strong>. This means our community members 
        will now review and vote on your request.</p>

        <p><strong>Application Details:</strong></p>
        <ul>
            <li><b>Requested Amount:</b> {application.amount_requested}</li>
            <li><b>Cause:</b> {application.cause or 'Not specified'}</li>
            <li><b>Status:</b> Voting</li>
        </ul>

        <p>You will be notified as soon as the voting process is complete 
        and a decision has been made.</p>

        <p>Thank you for being part of <strong>KHG</strong>.</p>
    """

    # Send HTML mail
    sendMailhtml(
        member.email,
        "Your Loan Application is Now in Voting",
        body
    )
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
@admin_required
def accept_loan(application_id):
    application = LoanApplication.query.get_or_404(application_id)

    # Create loan
    loan = Loan(member_id=application.member_id,approved_amount=application.amount_requested,remaining_amount=application.amount_requested,status="ongoing",issued_at=datetime.utcnow())
    db.session.add(loan)
    db.session.flush()  
    # Transaction
    tx = LoanTransaction(loan_id=loan.loan_id,transaction_type="borrow",amount=application.amount_requested,created_at=datetime.utcnow())
    db.session.add(tx)
    # Update application metadata
    application.status = "approved"
    application.reviewed_by = session.get("admin_id")
    application.reviewed_at = datetime.utcnow()
    # Delete vote_item tied to this application (if exists)
    vote_item = VoteItem.query.filter_by(application_id=application.application_id).first()
    # Audit log
    log = AuditLog(admin_id=session.get("admin_id"),member_id=application.member_id,action=f"Accepted loan application ID {application.application_id}",target_table="loans",target_id=application.application_id,amount=tx.amount,created_at=datetime.utcnow())
    db.session.add(log)
    cur_admin = Admin.query.get_or_404(session.get("admin_id"))
    member = Member.query.get_or_404(application.member_id)  
    body = f"""
        <p>Dear {member.name},</p>
        <p>We are pleased to inform you that your <strong>Loan Application</strong> has been <strong>approved</strong> by our committee.</p>
        <p><strong>Loan Details:</strong></p>
        <ul>
            <li><b>Requested Amount:</b> {application.amount_requested}</li>
            <li><b>Cause:</b> {application.cause or 'Not specified'}</li>
            <li><b>Status:</b> Approved & Issued</li>
        </ul>
        <p>The approved amount has been issued and is now available for your use. 
        Please make sure to review the repayment schedule and terms.</p>
        <p>If you have any questions or require further assistance, please contact us.</p>
        <p>Thank you for trusting <strong>KHG</strong>.</p>
        <p>From,<br>
        {cur_admin.full_name}<br>
        {cur_admin.role}, KHG</p>
    """
    sendMailhtml(member.email,"Your Loan Application has been Approved",body)
    try:
        db.session.commit()
        flash("Loan accepted and issued to member.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error approving loan: {str(e)}", "danger")

    return redirect(url_for("admin.loan_application_details", application_id=application.application_id))

# Reject / Delete application
@admin_app.route("/loan-applications/delete/<int:application_id>", methods=["POST"])
@admin_required
def delete_loan_application(application_id):
    application = LoanApplication.query.get_or_404(application_id)
    member_id = application.member_id
    cur_admin = Admin.query.get_or_404(session.get("admin_id"))
    member = Member.query.get_or_404(member_id)  
    body = f"""
        <p>Dear {member.name},</p>
        <p>We regret to inform you that your <strong>Loan Application</strong> has been <strong>rejected</strong> after careful consideration.</p>
        <p><strong>Loan Application Details:</strong></p>
        <ul>
            <li><b>Requested Amount:</b> {application.amount_requested}</li>
            <li><b>Cause:</b> {application.cause or 'Not specified'}</li>
        </ul>
        <p>If you believe this decision was made in error or would like to submit another application, please feel free to contact us for clarification.</p>
        <p>We truly appreciate your interest in <strong>KHG</strong> and encourage you to stay connected with our community for future opportunities.</p>
        <p>From,<br>
        {cur_admin.full_name}<br>
        {cur_admin.role}, KHG</p>
    """
    sendMailhtml(member.email,"Loan Application Rejected",body)
    Vote.query.filter_by(application_id=application.application_id).delete(synchronize_session=False)
    vote_item = VoteItem.query.filter_by(application_id=application.application_id).first()
    if vote_item:
        db.session.delete(vote_item)
    log = AuditLog(admin_id=session.get("admin_id"),member_id=member_id,action=f"Rejected (deleted) loan application ID {application.application_id}",target_table="loan_applications",target_id=application.application_id,amount=0,created_at=datetime.utcnow())
    db.session.add(log)
    db.session.delete(application)
    try:
        db.session.commit()
        flash("Loan application rejected successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error rejecting application: {str(e)}", "danger")

    return redirect(url_for("admin.loans"))


@admin_app.route("/fund_history", methods=["GET", "POST"])
@admin_required
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


@admin_app.route("/loan_history")
@admin_required
def loan_history():
    loans = Loan.query.order_by(Loan.created_at.desc()).all()
    return render_template("admin/loan_history.html", loans=loans)

@admin_app.route("/members")
@admin_required
def manage_members():
    members = Member.query.order_by(Member.join_date.desc()).all()
    return render_template("admin/manage_members.html", members=members)

@admin_app.route("/members/<int:member_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_member(member_id):
    member = Member.query.get_or_404(member_id)
    if request.method == "POST":
        nid = request.form.get("nid")
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
        new_password = generate_password_hash(new_password)
        if new_password:
            member.password_hash = new_password
        db.session.commit()
        cur_admin = Admin.query.get_or_404(session.get("admin_id"))
        body = f"""
            <p>Dear {member.name},</p>
            <p>Your membership information has been successfully updated in our records. Below are your updated details:</p>
            <ul>
                <li><strong>Name:</strong> {member.name}</li>
                <li><strong>Father's Name:</strong> {member.father_name}</li>
                <li><strong>NID:</strong> {member.nid}</li>
                <li><strong>Email:</strong> {member.email}</li>
                <li><strong>Phone:</strong> {member.phone}</li>
                <li><strong>Occupation:</strong> {member.occupation}</li>
                <li><strong>Address:</strong> {member.address}</li>
            </ul>
            <p>If you did not request this change or notice any incorrect information, please contact us immediately.</p>
            <p>From,<br>
            {cur_admin.full_name}<br>
            {cur_admin.role}, KHG</p>
        """
        sendMailhtml(member.email, "Membership Information Updated", body)
        flash("Member details updated successfully.", "success")
        return redirect(url_for("admin.manage_members"))
        
    return render_template("admin/edit_member.html", member=member)

# Delete a member (cascade delete loans/donations)
@admin_app.route("/members/<int:member_id>/delete", methods=["POST"])
@admin_required
def delete_member(member_id):
    member = Member.query.get_or_404(member_id)
    cur_admin = Admin.query.get_or_404(session.get("admin_id"))
    # Delete related loans & donations
    for loan in member.loans:
        db.session.delete(loan)
    for donation in member.donations:
        db.session.delete(donation)

    db.session.delete(member)
    db.session.commit()
    flash(f"Member {member.name} deleted permanently.", "success")
    body = f"""
        <p>Dear {member.name},</p>
        <p>We regret to inform you that your membership with <strong>KHG</strong> has been cancelled and all associated records have been removed from our system.</p>
        <p>If you believe this action was made in error or wish to discuss this matter, please reach out to us through our contact page:</p>
        <p><a href="https://khg-bd.onrender.com/contact">Contact Korje Hasanah Group</a></p>
        <p>Thank you for being part of our community.</p>
        <p>From,<br>
        {cur_admin.full_name}<br>
        {cur_admin.role}, KHG</p>
    """
    sendMailhtml(member.email, "Membership Cancellation Notice", body)
    return redirect(url_for("admin.manage_members"))

@admin_app.route("/notifications", methods=["GET", "POST"])
@admin_required
def notifications():
    members = Member.query.order_by(Member.name).all()
    if request.method == "POST":
        message = request.form.get("message")
        selected_ids = request.form.getlist("member_ids")
        if not selected_ids:
            flash("Please select at least one member.", "warning")
            return redirect(url_for("admin.notifications"))
        for member_id in selected_ids:
            notif = Notification(member_id=int(member_id),admin_id=session.get("admin_id"),message=message,notification_type="general",created_at=datetime.utcnow())
            member = Member.query.get_or_404(member_id)
            email_body = f"""
                <p>Dear {member.name},</p>
                <p>You have a new notification from <strong>Korje Hasanah Group (KHG)</strong>:</p>
                <blockquote>{message}</blockquote>
                <p>We encourage you to stay connected with us for updates and opportunities.</p>
            """
            sendMailhtml(member.email,"New Notification from KHG",email_body)
            db.session.add(notif)
        db.session.commit()
        flash(f"Notification sent to {len(selected_ids)} member(s).", "success")
        return redirect(url_for("admin.notifications"))
    notifications_list = Notification.query.order_by(Notification.created_at.desc()).all()
    return render_template("admin/notifications.html", members=members, notifications=notifications_list)


@admin_app.route("/notifications/<int:notification_id>/delete", methods=["POST"])
@admin_required
def delete_notification(notification_id):
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

@admin_app.route("/loan-management", methods=["GET", "POST"])
@admin_required
def loan_management():
    members = Member.query.order_by(Member.name).all()
    loans = Loan.query.order_by(Loan.loan_id).all()
    if request.method == "POST":
        member_id = request.form.get("member_id")
        loan_id = request.form.get("loan_id") 
        action_type = request.form.get("action_type")  
        amount_raw = request.form.get("amount", "0")
        cur_admin = Admin.query.get_or_404(session.get("admin_id"))
        member = Member.query.get(member_id)
        if not member:
            flash("Selected member not found.", "danger")
            return redirect(url_for("admin.loan_management"))
        try:
            amount = Decimal(amount_raw)
            if amount <= 0:
                raise InvalidOperation
        except (InvalidOperation, TypeError):
            flash("Please enter a valid positive amount.", "danger")
            return redirect(url_for("admin.loan_management"))
        try:
            if action_type == "repay":
                if not loan_id:
                    flash("Please select a loan to apply repayment.", "warning")
                    return redirect(url_for("admin.loan_management"))
                loan = Loan.query.get_or_404(loan_id)
                if loan.member_id != member.member_id:
                    flash("Selected loan does not belong to the selected member. Choose the correct loan.", "danger")
                    return redirect(url_for("admin.loan_management"))
                loan.remaining_amount = (loan.remaining_amount or Decimal("0.00")) - amount
                if loan.remaining_amount <= 0:
                    if loan.remaining_amount < 0:
                        extra = abs(loan.remaining_amount)
                        donation = Donation(member_id=loan.member_id,amount=extra,donation_type="Extra repayment")
                        db.session.add(donation)
                        flash(f"Extra {extra} converted to donation.", "info")
                    loan.remaining_amount = Decimal("0.00")
                    loan.status = "paid"
                transaction = LoanTransaction(loan_id=loan.loan_id,transaction_type="repay",amount=amount,)
                db.session.add(transaction)
                audit = AuditLog(member_id=loan.member_id,admin_id=session.get("admin_id"),action=f"repaid",target_table="loans",target_id=loan.loan_id,amount=amount_raw)
                db.session.add(audit)
                notification = Notification( member_id=loan.member_id,admin_id=session.get("admin_id"),message=(
                        f"Your repayment of {amount} has been recorded. "
                        f"Original loan: {loan.approved_amount}, Remaining: {loan.remaining_amount}. "
                        f"Issued at: {loan.issued_at}"
                    )
                )
                db.session.add(notification)
                body = render_template("emails/loan_notification.html",subject="Loan Repayment Recorded",member=member,message=(
                        f"Your repayment of {amount} has been recorded. "
                        f"Original loan amount: {loan.approved_amount}, Remaining: {loan.remaining_amount}. "
                        f"Issued at: {loan.issued_at}."
                    ),sender=cur_admin,year=datetime.utcnow().year)
                sendMailhtml(member.email, "Loan Repayment Recorded", body)
            elif action_type == "borrow":
                loan = Loan(member_id=member.member_id,approved_amount=amount,remaining_amount=amount,status="ongoing",)
                db.session.add(loan)
                db.session.flush()  
                transaction = LoanTransaction(loan_id=loan.loan_id,transaction_type="borrow",amount=amount)
                db.session.add(transaction)
                audit = AuditLog(member_id=member.member_id,admin_id=session.get("admin_id"),action=f"borrow",target_table="loans",target_id=loan.loan_id,amount=amount)
                db.session.add(audit)
                notification = Notification(member_id=member.member_id,admin_id=session.get("admin_id"),message=f"A new loan of {amount} has been issued to you.")
                db.session.add(notification)
                body = render_template("emails/loan_notification.html",subject="New Loan Issued",member=member,message=f"A new loan of {amount} has been issued to you.",sender=cur_admin,year=datetime.utcnow().year)
                sendMailhtml(member.email, "New Loan Issued", body)
            db.session.commit()
            flash("Loan action completed successfully.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")
        return redirect(url_for("admin.loan_management"))
    return render_template("admin/loan_management.html", members=members, loans=loans)

@admin_app.route("/add-donation", methods=["GET", "POST"])
@admin_required
def add_donation():
    members = Member.query.order_by(Member.name).all()
    donations = Donation.query.order_by(Donation.donated_at.desc()).limit(50).all()

    if request.method == "POST":
        member_id = request.form.get("member_id")
        amount = request.form.get("amount")
        donation_type = request.form.get("donation_type") or "General"

        member = Member.query.get_or_404(member_id)

        donation = Donation(member_id=member.member_id,amount=amount,donation_type=donation_type)
        db.session.add(donation)
        db.session.commit()      
        audit = AuditLog(admin_id=session.get("admin_id"),member_id=member.member_id,action=f"{donation_type}",target_table="donations",target_id=donation.donation_id,amount=amount)
        db.session.add(audit)
        db.session.commit()
        cur_admin = Admin.query.get_or_404(session.get("admin_id"))
        body = f"""
            <p>Dear {member.name},</p>
            <p>Your donation has been successfully updated in our records. Below are your updated details:</p>
            <ul>
                <li><strong>Donation Type:</strong> {donation_type}</li>
                <li><strong>Amount:</strong> {amount}</li>
            </ul>
            <p>If you did not request this change or notice any incorrect information, please contact us immediately.</p>
            <p>From,<br>
            {cur_admin.full_name}<br>
            {cur_admin.role}, KHG</p>
        """
        sendMailhtml(member.email, "Donation has been recieved", body)
        flash("Donation added successfully.", "success")
        return redirect(url_for("admin.add_donation"))
    return render_template("admin/add_donation.html", members=members, donations=donations)