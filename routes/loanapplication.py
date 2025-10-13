from flask import  redirect, url_for, render_template, flash, request, session, Blueprint, current_app
from utils import admin_required, _send_async_email
from models import  db, Admin, Member,  AuditLog, Notification, Vote, VoteItem, LoanApplication, Loan, LoanTransaction
from decimal import Decimal, InvalidOperation
from datetime import  datetime
import threading

loan_app = Blueprint("loanapplication", __name__, url_prefix="/loanapplication")

def sendMailhtml(recipient, subject, body):
    if not isinstance(recipient, list):
        recipient = [recipient]
    cur_admin = Admin.query.get(session["admin_id"])
    html_body = render_template("email_template.html",subject=subject,body=body,year=datetime.now().year,sender=cur_admin )
    app = current_app._get_current_object()
    threading.Thread(target=_send_async_email,args=(app, recipient, subject, html_body, True),daemon=True,).start()

# Loan applications list
@loan_app.route("/")
@admin_required
def loans():
    applications = LoanApplication.query.order_by(LoanApplication.submitted_at.desc()).all()
    return render_template("admin/loans.html", applications=applications)

# Loan application details
@loan_app.route("/<int:application_id>")
@admin_required
def loan_application_details(application_id):
    application = LoanApplication.query.get_or_404(application_id)
    # If voting started, fetch votes for this application
    votes = []
    votes = Vote.query.filter_by(application_id=application.application_id).all()
    return render_template("admin/loan_application_details.html", application=application, votes=votes)

# Set application for voting
@loan_app.route("/<int:application_id>/set-voting")
@admin_required
def set_for_voting(application_id):
    application = LoanApplication.query.get_or_404(application_id)

    if application.status in ["approved", "rejected", "voting"]:
        flash(f"Cannot set application for voting. Current status: {application.status}", "warning")
        return redirect(url_for("loanapplication.loan_application_details", application_id=application.application_id))

    # Update status
    application.status = "voting"

    # Create a VoteItem for this loan
    vote_item = VoteItem(title=f"Loan Approval for {application.member.name}",description=f"Loan requested: {application.amount_requested}\nCause: {application.cause or 'Not specified'}",created_at=datetime.utcnow(),application_id=application.application_id)
    member = Member.query.get_or_404(application.member_id)  
    body = f"""
        <p>Dear {member.name},</p>
        <p>We would like to inform you that your <strong>Loan Application</strong> has been 
        moved to the <strong>voting stage</strong>. This means our community members 
        will now review and vote on your request. Check <a href = "https://khg-bd.onrender.com/member/voting"> here </a></p>

        <p><strong>Application Details:</strong></p>
        <ul>
            <li><b>Requested Amount:</b> {application.amount_requested}</li>
            <li><b>Cause:</b> {application.cause or 'Not specified'}</li>
            <li><b>Status:</b> Voting</li>
        </ul>

        <p>You will be notified as soon as the voting process is complete and a decision has been made.</p>

        <p>Thank you for being part of <strong>KHG</strong>.</p>
    """
    notification = Notification( member_id=member.member_id,admin_id=session.get("admin_id"),message=(
                        f"We would like to inform you that your Loan Application has been moved to the voting stage. This means our community members will now review and vote on your request."
                        f"Amount requested: {application.amount_requested}, Cause: {application.cause}. "
                    )
                )
    allmember = Member.query.all()
    for man in allmember:
        newbody = f"""
            <p>Dear {man.name},</p>
            <p>We would like to inform you that A new loan application is set for voting. Please help admin to take descision by showing your interest on this item. Please vote here:  <a href = "https://khg-bd.onrender.com/member/voting"> here </a></p>
            
            <p><strong>Application Details:</strong></p>
            <ul>
                <li><b>Requested Amount:</b> {application.amount_requested}</li>
                <li><b>Cause:</b> {application.cause or 'Not specified'}</li>
                <li><b>Status:</b> Voting</li>
            </ul>
            <p>Thank you for being part of <strong>KHG</strong>.</p>
        """
        sendMailhtml(man.email,"Your Loan Application is Now in Voting",newbody)

    db.session.add(notification)
    sendMailhtml(member.email,"Your Loan Application is Now in Voting",body)
    try:
        db.session.add(vote_item)
        db.session.commit()
        flash("Application is now set for voting and added to voting items.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error setting application for voting: {str(e)}", "danger")

    return redirect(url_for("loanapplication.loan_application_details", application_id=application.application_id))


# Accept loan
@loan_app.route("/<int:application_id>/accept", methods=["POST"])
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
    application.status = "approved"
    application.reviewed_by = session.get("admin_id")
    application.reviewed_at = datetime.utcnow()
    vote_item = VoteItem.query.filter_by(application_id=application.application_id).first()
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
    notification = Notification( member_id=member.member_id,admin_id=session.get("admin_id"),message=(
                        f"We are pleased to inform you that your Loan Application has been approved by our committee"
                        f"Amount requested: {application.amount_requested}, Cause: {application.cause}."
                    )
                )
    db.session.add(notification)
    try:
        db.session.commit()
        flash("Loan accepted and issued to member.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error approving loan: {str(e)}", "danger")
    return redirect(url_for("loanapplication.loan_application_details", application_id=application.application_id))

@loan_app.route("/delete/<int:application_id>", methods=["POST"])
@admin_required
def delete_loan_application(application_id):
    application = LoanApplication.query.get_or_404(application_id)
    member_id = application.member_id
    cur_admin = Admin.query.get_or_404(session.get("admin_id"))
    member = Member.query.get_or_404(member_id)  
    notification = Notification( member_id=member.member_id,admin_id=session.get("admin_id"),message=(
                        f"We regret to inform you that your Loan Application has been Rejected by our committee"
                        f"Amount requested: {application.amount_requested}, Cause: {application.cause}."
                    )
                )
    db.session.add(notification)
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

    return redirect(url_for("loanapplication.loans"))
