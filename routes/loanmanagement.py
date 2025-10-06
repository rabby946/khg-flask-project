from flask import redirect, url_for, render_template, flash, request, session, Blueprint, current_app
from utils import admin_required, _send_async_email
from models import  db, Admin, Loan, Member, LoanTransaction, AuditLog, Donation, Notification, LoanRepaymentRequest
from decimal import Decimal, InvalidOperation
from datetime import  datetime
import threading

loanmanagement_app = Blueprint("loanmanagement", __name__, url_prefix="/loanmanagement")

def sendMailhtml(recipient, subject, body):
    if not isinstance(recipient, list):
        recipient = [recipient]
    cur_admin = Admin.query.get(session["admin_id"])
    html_body = render_template("email_template.html",subject=subject,body=body,year=datetime.now().year,sender=cur_admin )
    app = current_app._get_current_object()
    threading.Thread(target=_send_async_email,args=(app, recipient, subject, html_body, True),daemon=True,).start()


@loanmanagement_app.route("/", methods=["GET", "POST"])
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
            return redirect(url_for("loanmanagement.loan_management"))
        try:
            amount = Decimal(amount_raw)
            if amount <= 0:
                raise InvalidOperation
        except (InvalidOperation, TypeError):
            flash("Please enter a valid positive amount.", "danger")
            return redirect(url_for("loanmanagement.loan_management"))
        try:
            if action_type == "repay":
                if not loan_id:
                    flash("Please select a loan to apply repayment.", "warning")
                    return redirect(url_for("loanmanagement.loan_management"))
                loan = Loan.query.get_or_404(loan_id)
                if loan.member_id != member.member_id:
                    flash("Selected loan does not belong to the selected member. Choose the correct loan.", "danger")
                    return redirect(url_for("loanmanagement.loan_management"))
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
                try:
                    member = member.member_id
                    subject = f"Your repayment of {amount} has been recorded."
                    message_body = f"""
                        <p>Dear {member.name},</p>
                        <p>f"Your repayment of {amount} has been recorded.</p>
                         f"Original loan: {loan.approved_amount}, Remaining: {loan.remaining_amount}. "
                        f"Issued at: {loan.issued_at}"
                        <p><b>Note:</b> If you think this is something inapropriate happend with you please contact : <a href="khg-bd.onrender.com">here </a></p> <br>
                        <p>We thank you for your continued support to <strong>Korje Hasanah Group (KHG)</strong>.</p>
                        <p>Kind regards,<br><b>KHG Admin Team</b></p>
                    """
                    sendMailhtml(member.email, subject, message_body)
                except Exception as e:
                    print(f"[Email Error] Failed to send notification: {e}")
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
                try:
                    member = member.member_id
                    subject = f"Your Loan amount {amount} Has Been issued"
                    message_body = f"""
                        <p>Dear {member.name},</p>
                        <p>Your new loan amount BDT <strong>{amount}</strong> has been issued.</p>
                        
                        <p><b>Note:</b> If you think this is something inapropriate happend with you please contact : <a href="khg-bd.onrender.com">here </a></p> <br>
                        <p>We thank you for your continued support to <strong>Korje Hasanah Group (KHG)</strong>.</p>
                        <p>Kind regards,<br><b>KHG Admin Team</b></p>
                    """
                    sendMailhtml(member.email, subject, message_body)
                except Exception as e:
                    print(f"[Email Error] Failed to send notification: {e}")
            db.session.commit()
            flash("Loan action completed successfully.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")
        return redirect(url_for("loanmanagement.loan_management"))
    return render_template("admin/loan_management.html", members=members, loans=loans)


@loanmanagement_app.route("/loan_repayment_requests", methods=["GET", "POST"])
@admin_required
def loan_repayment_requests():
    if request.method == "POST":
        req_id = request.form.get("request_id")
        action = request.form.get("action")  # accept / reject
        admin_note = request.form.get("admin_note", "").strip() or "N/A"

        repayment_request = LoanRepaymentRequest.query.get(req_id)
        if not repayment_request or repayment_request.status != "Pending":
            flash("Repayment request not found.", "danger")
            return redirect(url_for("loanmanagement.loan_repayment_requests"))

        loan = Loan.query.get(repayment_request.loan_id)
        member = repayment_request.member

        if not loan:
            flash("Associated loan not found.", "danger")
            return redirect(url_for("loanmanagement.loan_repayment_requests"))

        # --- Handle Accept / Reject Logic ---
        if action == "accept":
            repayment_request.status = "Accepted"
            repayment_request.updated_by = session.get("admin_name", "Unknown Admin")
            repayment_request.admin_note = admin_note
            repayment_request.updated_at = datetime.utcnow()
            audit = AuditLog(member_id=loan.member_id,admin_id=session.get("admin_id"),action=f"repaid",target_table="loans",target_id=loan.loan_id,amount=repayment_request.amount)
            db.session.add(audit)
            # Subtract amount from remaining loan
            loan.remaining_amount = float(loan.remaining_amount) - float(repayment_request.amount)
            if loan.remaining_amount <= 0:
                loan.remaining_amount = 0
                loan.status = "Completed"

            # Record loan transaction (optional, if you want to track)
            transaction = LoanTransaction(
                loan_id=loan.loan_id,
                amount=repayment_request.amount,
                transaction_type="Repayment",
                created_at=datetime.utcnow()
            )
            db.session.add(transaction)

            db.session.commit()

            # --- Send Email to Member ---
            try:
                subject = f"Your Loan Repayment Request #{repayment_request.id} Has Been Accepted"
                message_body = f"""
                    <p>Dear {member.name},</p>
                    <p>Your loan repayment request (ID: <strong>{repayment_request.id}</strong>) for 
                    Loan <strong>#{loan.loan_id}</strong> of 
                    <strong>${repayment_request.amount:.2f}</strong> has been <b>Accepted</b>.</p>
                    <p><b>Remaining Loan Balance:</b> ${loan.remaining_amount:.2f}</p>
                    <p><b>Payment Method:</b> {repayment_request.payment_method}<br>
                    <b>Transaction ID:</b> {repayment_request.transaction_id}</p>
                    <p><b>Admin Note:</b> {repayment_request.admin_note}</p>
                    <p>Thank you for your timely repayment. Keep supporting <b>Korje Hasanah Group (KHG)</b>.</p>
                """
                sendMailhtml(member.email, subject, message_body)
            except Exception as e:
                print(f"[Email Error] Failed to notify member: {e}")

        elif action == "reject":
            repayment_request.status = "Rejected"
            repayment_request.updated_by = session.get("admin_name", "Unknown Admin")
            repayment_request.admin_note = admin_note
            repayment_request.updated_at = datetime.utcnow()
            
            audit = AuditLog(member_id=loan.member_id,admin_id=session.get("admin_id"),action=f"rejected loan repayment request",target_table="loans",target_id=loan.loan_id,amount=0)
            db.session.add(audit)
            db.session.commit()
            # --- Notify Member via Email ---
            try:
                subject = f"Your Loan Repayment Request #{repayment_request.id} Has Been Rejected"
                message_body = f"""
                    <p>Dear {member.name},</p>
                    <p>Your repayment request (ID: <strong>{repayment_request.id}</strong>) for 
                    Loan <strong>#{repayment_request.loan_id}</strong> of 
                    <strong>${repayment_request.amount:.2f}</strong> has been <b>Rejected</b>.</p>
                    <p><b>Admin Note:</b> {repayment_request.admin_note}</p>
                    <p>If you believe this was a mistake, please contact the KHG team for clarification.</p>
                """
                sendMailhtml(member.email, subject, message_body)
            except Exception as e:
                print(f"[Email Error] Failed to notify member: {e}")

        else:
            flash("Invalid action.", "danger")
            return redirect(url_for("loanmanagement.loan_repayment_requests"))

        flash(f"Loan repayment request #{req_id} has been {repayment_request.status.lower()}.", "success")
        return redirect(url_for("loanmanagement.loan_repayment_requests"))

    # --- Display All Requests ---
    requests = LoanRepaymentRequest.query.order_by(LoanRepaymentRequest.created_at.desc()).all()
    return render_template("admin/loan_repayment_requests.html", requests=requests, Member=Member)
