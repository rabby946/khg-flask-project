from flask import  redirect, url_for, render_template, flash, request, session, Blueprint, current_app
from utils import admin_required, _send_async_email
from models import  db, Admin, Donation, Member,  AuditLog, Donation, Notification, DonationRequest
from decimal import Decimal, InvalidOperation
from datetime import  datetime
import threading

donationmanagement_app = Blueprint("donationmanagement", __name__, url_prefix="/donationmanagement")

def sendMailhtml(recipient, subject, body):
    if not isinstance(recipient, list):
        recipient = [recipient]
    cur_admin = Admin.query.get(session["admin_id"])
    html_body = render_template("email_template.html",subject=subject,body=body,year=datetime.now().year,sender=cur_admin )
    app = current_app._get_current_object()
    threading.Thread(target=_send_async_email,args=(app, recipient, subject, html_body, True),daemon=True,).start()


@donationmanagement_app.route("/", methods=["GET", "POST"])
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

@donationmanagement_app.route("/donation_requests", methods=["GET", "POST"])
@admin_required
def donation_requests():
    if request.method == "POST":
        req_id = request.form.get("request_id")
        action = request.form.get("action")  #accept / reject
        admin_note = request.form.get("admin_note", "").strip() or "N/A"

        donation_request = DonationRequest.query.get(req_id)
        if not donation_request:
            flash("Donation request not found.", "danger")
            return redirect(url_for("admin.donation_requests"))

        if action == "accept":
            donation_request.status = "Accepted"
            donation = Donation(member_id=donation_request.member_id,amount=donation_request.amount,donation_type=donation_request.donation_type)
            db.session.add(donation)
            db.session.commit()
            audit = AuditLog(admin_id=session.get("admin_id"),member_id=donation_request.member_id,action=f"{donation_request.donation_type}",target_table="donations",target_id=donation.donation_id,amount=donation_request.amount)
            db.session.add(audit)
        elif action == "reject":
            donation_request.status = "Rejected"
        else:
            flash("Invalid action.", "danger")
            return redirect(url_for("admin.donation_requests"))
        try:
            member = donation_request.member 
            subject = f"Your Donation Request #{donation_request.id} Has Been {donation_request.status}"
            message_body = f"""
                <p>Dear {member.name},</p>
                <p>Your donation request (ID: <strong>{donation_request.id}</strong>) of 
                <strong>${donation_request.amount:.2f}</strong> submitted on 
                <strong>{donation_request.created_at.strftime('%d %B %Y')}</strong> has been 
                <strong>{donation_request.status}</strong>.</p>
                <p><b>Donation Type:</b> {donation_request.donation_type}<br>
                <b>Payment Method:</b> {donation_request.payment_method}<br>
                <b>Transaction ID:</b> {donation_request.transaction_id}</p>
                <p><b>Admin Note:</b> {donation_request.admin_note}</p>
                <p>We thank you for your continued support to <strong>Korje Hasanah Group (KHG)</strong>.</p>
                <p>Kind regards,<br><b>KHG Admin Team</b></p>
            """
            sendMailhtml(member.email, subject, message_body)
        except Exception as e:
            print(f"[Email Error] Failed to send notification: {e}")
        cur_admin = Admin.query.get_or_404(session.get("admin_id"))
        donation_request.updated_by = cur_admin.full_name
        donation_request.admin_note = admin_note
        donation_request.updated_at = datetime.utcnow()

        db.session.commit()
        flash(f"Donation request #{req_id} has been {donation_request.status.lower()}.", "success")
        return redirect(url_for("admin.donation_requests"))

    requests = DonationRequest.query.order_by(DonationRequest.created_at.desc()).all()
    return render_template("admin/donation_requests.html", requests=requests)

