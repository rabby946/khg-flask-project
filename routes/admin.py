from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app
from functools import wraps
from models import Admin, Donation, Loan, MembershipApplication, Member, LoanApplication, Notification, VoteItem, LoanTransaction, Vote, AuditLog, DonationRequest, LoanRepaymentRequest
from extensions import db
from utils import  _send_async_email, sendMailhtml1, admin_required
from sqlalchemy import desc , asc, func, extract
import threading
from datetime import datetime, timedelta

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



@admin_app.route("/history")
@admin_required
def donation_history():
    monthly_data = (db.session.query(extract('year', Donation.donated_at).label('year'),extract('month', Donation.donated_at).label('month'),func.sum(Donation.amount).label('total_amount')).group_by('year', 'month').order_by('year', 'month').all())
    start_date = datetime(2022, 1, 1)
    now = datetime.now()
    all_months = []
    current = start_date
    while current <= now:
        all_months.append((current.year, current.month))
        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)
    monthly_dict = {
        (int(row.year), int(row.month)): float(row.total_amount or 0)
        for row in monthly_data
    }
    monthly_summaries = [
        {
            "year": y,
            "month": m,
            "month_name": datetime(y, m, 1).strftime("%B"),
            "amount": monthly_dict.get((y, m), 0)
        }
        for (y, m) in all_months
    ]
    total_donations = db.session.query(func.coalesce(func.sum(Donation.amount), 0)).scalar()
    total_remaining_loans = db.session.query(func.coalesce(func.sum(Loan.remaining_amount), 0)).scalar()
    available_funds = total_donations - total_remaining_loans
    return render_template("admin/donation_history.html",monthly_summaries=monthly_summaries,total_donations=total_donations,available_funds=available_funds,)
from flask import Response
from io import StringIO
import csv
CSV_COLUMNS = ["Record Type","Member ID","Member Name","Loan ID","Transaction ID","Donation ID","Amount","Donation Type","Transaction Type","Payment Method","Message","Status","Created At","Updated At","Updated By","Admin Note",]

@admin_app.route("/fund_history/export_full")
@admin_required
def export_full_fund_history():
    # Optional filters
    member_id = request.args.get("member_id", "all")
    sort_order = request.args.get("sort", "desc")

    donations = (
        db.session.query(Donation, Member)
        .join(Member, Donation.member_id == Member.member_id)
    )
    donation_requests = (
        db.session.query(DonationRequest, Member)
        .join(Member, DonationRequest.member_id == Member.member_id)
    )
    loan_txns = (
        db.session.query(LoanTransaction, Loan, Member)
        .join(Loan, LoanTransaction.loan_id == Loan.loan_id)
        .join(Member, Loan.member_id == Member.member_id)
    )
    repay_requests = (
        db.session.query(LoanRepaymentRequest, Loan, Member)
        .join(Loan, LoanRepaymentRequest.loan_id == Loan.loan_id)
        .join(Member, LoanRepaymentRequest.member_id == Member.member_id)
    )

    if member_id != "all":
        donations = donations.filter(Donation.member_id == int(member_id))
        donation_requests = donation_requests.filter(DonationRequest.member_id == int(member_id))
        loan_txns = loan_txns.filter(Loan.member_id == int(member_id))
        repay_requests = repay_requests.filter(LoanRepaymentRequest.member_id == int(member_id))

    if sort_order == "asc":
        donations = donations.order_by(Donation.donated_at.asc())
        donation_requests = donation_requests.order_by(DonationRequest.created_at.asc())
        loan_txns = loan_txns.order_by(LoanTransaction.created_at.asc())
        repay_requests = repay_requests.order_by(LoanRepaymentRequest.created_at.asc())
    else:
        donations = donations.order_by(Donation.donated_at.desc())
        donation_requests = donation_requests.order_by(DonationRequest.created_at.desc())
        loan_txns = loan_txns.order_by(LoanTransaction.created_at.desc())
        repay_requests = repay_requests.order_by(LoanRepaymentRequest.created_at.desc())

    si = StringIO()
    writer = csv.DictWriter(si, fieldnames=CSV_COLUMNS)
    writer.writeheader()

    for d, m in donations:
        writer.writerow({"Record Type": "Donation","Member ID": m.member_id,"Member Name": m.name,"Donation ID": d.donation_id,"Amount": float(d.amount),"Donation Type": d.donation_type,"Created At": d.donated_at.strftime("%Y-%m-%d %H:%M:%S"),})

    for r, m in donation_requests:
        writer.writerow({"Record Type": "Donation Request","Member ID": m.member_id,"Member Name": m.name,"Transaction ID": r.transaction_id,"Amount": float(r.amount),"Donation Type": r.donation_type,"Payment Method": r.payment_method,"Message": r.message,"Status": r.status,"Created At": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),"Updated At": r.updated_at.strftime("%Y-%m-%d %H:%M:%S") if r.updated_at else "","Updated By": r.updated_by or "","Admin Note": r.admin_note or "",})

    for t, l, m in loan_txns:
        writer.writerow({"Record Type": "Loan Transaction","Member ID": m.member_id,"Member Name": m.name,"Loan ID": l.loan_id,"Transaction ID": t.transaction_id,"Transaction Type": t.transaction_type,"Amount": float(t.amount),"Created At": t.created_at.strftime("%Y-%m-%d %H:%M:%S"),})

    for rr, l, m in repay_requests:
        writer.writerow({"Record Type": "Loan Repayment Request","Member ID": m.member_id,"Member Name": m.name,"Loan ID": l.loan_id,"Amount": float(rr.amount),"Payment Method": rr.payment_method,"Transaction ID": rr.transaction_id,"Message": rr.message,"Status": rr.status,"Created At": rr.created_at.strftime("%Y-%m-%d %H:%M:%S"),"Updated At": rr.updated_at.strftime("%Y-%m-%d %H:%M:%S") if rr.updated_at else "","Updated By": rr.updated_by or "","Admin Note": rr.admin_note or "",})

    output = Response(
        si.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=full_fund_history.csv"
        },
    )
    return output
