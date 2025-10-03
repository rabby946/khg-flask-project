from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify
from sqlalchemy import func
from extensions import db
from models import Member, Loan, LoanApplication, Donation, Vote, VoteItem, Notification, MembershipApplication
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from utils import upload_to_imgbb, member_required, g
from sqlalchemy.exc import IntegrityError
member_app = Blueprint("member", __name__, url_prefix="/member")

# ---------------- Context processor ----------------
@member_app.context_processor
def inject_now():
    return {'year': datetime.now().year}

def get_current_member():
    return getattr(g, 'member', None)

# ---------------- LOGIN / LOGOUT ----------------
@member_app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nid = request.form.get("nid")
        password = request.form.get("password")
        if not nid or not password:
            flash("Please fill in both NID/phone and password.", "danger")
            return redirect(url_for("member.login"))
        member = Member.query.filter((Member.phone == nid) | (Member.nid == nid)).first()
        if member and check_password_hash(member.password_hash, password):
            session["member_logged_in"] = True
            session["member_id"] = member.member_id
            flash("Login successful!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("member.profile"))
        flash("Invalid credentials!", "danger")
        return redirect(url_for("member.login"))
    return render_template("public/login.html")

@member_app.route("/logout")
@member_required
def logout():
    session.pop("member_logged_in")
    session.pop("member_id")
    flash("Logged out successfully!", "success")

@member_app.route("/")
@member_app.route("/profile")
@member_required
def profile():
    member = g.member
    total_due = db.session.query(func.coalesce(func.sum(Loan.remaining_amount), 0)).filter(Loan.member_id == member.member_id,Loan.status == "ongoing").scalar()
    return render_template("member/profile.html", member=member, due_amount=total_due)

@member_app.route("/edit_profile", methods=["GET", "POST"])
@member_required
def edit_profile():
    if not session.get("member_logged_in"):
        flash("Please log in first.", "warning")
        return redirect(url_for("public.home"))
    member = get_current_member()
    if request.method == "POST":
        file = request.files.get('photo_url')
        if file and file.filename:
            new_photo_url = upload_to_imgbb(file)
            if new_photo_url:
                member.photo_url = new_photo_url
            else:
                flash("There was an error uploading the new photo. Please try again.", "danger")
                return redirect(url_for("member.edit_profile"))
        name = request.form.get("name")
        father_name = request.form.get("father_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        address = request.form.get("address")
        gender = request.form.get("gender")
        date_of_birth_str = request.form.get("date_of_birth")
        occupation = request.form.get("occupation")
        if email and Member.query.filter(Member.email == email, Member.member_id != member.member_id).first():
            flash("Email already in use by another member.", "danger")
            return redirect(url_for("member.edit_profile"))
        if phone and Member.query.filter(Member.phone == phone, Member.member_id != member.member_id).first():
            flash("Phone number already in use by another member.", "danger")
            return redirect(url_for("member.edit_profile"))
        member.name = name
        member.father_name = father_name
        member.email = email
        member.phone = phone
        member.address = address
        member.gender = gender
        member.occupation = occupation
        if date_of_birth_str:
            try:
                from datetime import datetime
                member.date_of_birth = datetime.strptime(date_of_birth_str, '%Y-%m-%d').date()
            except ValueError:
                flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
                return redirect(url_for("member.edit_profile"))
        else:
            member.date_of_birth = None
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("member.profile"))
    return render_template("member/edit_profile.html", member=member)

@member_app.route("/change_password", methods=["GET", "POST"])
@member_required
def change_password():
    member = get_current_member()
    if request.method == "POST":
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        if member.password_hash != old_password:
            flash("Old password is incorrect!", "danger")
        elif new_password != confirm_password:
            flash("New passwords do not match!", "danger")
        else:
            member.password_hash = new_password
            db.session.commit()
            flash("Password changed successfully!", "success")
            return redirect(url_for("member.profile"))
    return render_template("member/change_password.html", member=member)

@member_app.route("/notifications")
@member_required
def notifications():
    member = get_current_member()
    notifications = Notification.query.filter_by(member_id=member.member_id).order_by(Notification.created_at.desc()).all()
    return render_template("member/notifications.html",member=member, notifications=notifications)

@member_app.route("/notifications/<int:notification_id>/read", methods=["POST"])
@member_required
def mark_notification_read(notification_id):
    member = get_current_member()
    notification = Notification.query.filter_by(notification_id=notification_id, member_id=member.member_id).first()
    if not notification:
        return jsonify({"success": False, "message": "Notification not found"}), 404
    notification.is_read = True
    db.session.commit()
    return jsonify({"success": True, "message": "Marked as read"})

@member_app.route("/notifications/mark-all-read", methods=["POST"])
def mark_all_notifications_read():
    member = get_current_member()
    if not member:
        return jsonify({"success": False, "message": "Member not found"}), 404
    Notification.query.filter_by(member_id=member.member_id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"success": True, "message": "All notifications marked as read"})

@member_app.route("/notifications/<int:notification_id>/unread", methods=["POST"])
@member_required
def mark_notification_unread(notification_id):
    member = get_current_member()
    notification = Notification.query.filter_by(notification_id=notification_id, member_id=member.member_id).first()
    if not notification:
        return jsonify({"success": False, "message": "Notification not found"}), 404
    notification.is_read = False
    db.session.commit()
    return jsonify({"success": True, "message": "Marked as unread"})

@member_app.route("/notifications/<int:notification_id>/delete", methods=["POST"])
@member_required
def delete_notification(notification_id):
    member = get_current_member()
    notification = Notification.query.filter_by(notification_id=notification_id, member_id=member.member_id).first()
    if not notification:
        return jsonify({"success": False, "message": "Notification not found"}), 404
    db.session.delete(notification)
    db.session.commit()
    return jsonify({"success": True, "message": "Deleted"})

@member_app.route("/history")
@member_required
def history():
    member = get_current_member()
    donations = Donation.query.filter_by(member_id=member.member_id).order_by(Donation.donated_at.desc()).all()
    loans = Loan.query.filter_by(member_id=member.member_id).order_by(Loan.issued_at.desc()).all()
    return render_template("member/history.html",member=member, donations=donations, loans=loans)

@member_app.route("/voting", methods=["GET", "POST"])
@member_required
def voting():
    member = get_current_member()
    vote_items = VoteItem.query.order_by(VoteItem.created_at.desc()).all()
    if request.method == "POST":
        try:
            item_id = int(request.form.get("item_id"))
            choice = int(request.form.get("choice"))
            vote_itm = VoteItem.query.get_or_404(item_id)
            if not (0 <= choice <= 9):
                flash("Invalid choice. Please select a valid option.", "danger")
                return redirect(url_for("member.voting"))
        except (ValueError, TypeError):
            flash("Invalid submission. Please select an option from the dropdown.", "danger")
            return redirect(url_for("member.voting"))
        print(vote_itm.application_id)
        existing_vote = Vote.query.filter_by(member_id=member.member_id, item_id=item_id).first()
        if existing_vote:
            flash("You have already voted on this item!", "warning")
        else:
            vote = Vote(member_id=member.member_id, item_id=item_id, choice=choice,  application_id=vote_itm.application_id)
            try:
                db.session.add(vote)
                db.session.commit()
                flash("Your vote has been successfully recorded!", "success")
            except IntegrityError:
                db.session.rollback()
                flash("You have already voted on this item!", "warning")
            
        return redirect(url_for("member.voting"))
    member_votes_query = Vote.query.filter_by(member_id=member.member_id).all()
    member_votes = {vote.item_id: vote.choice for vote in member_votes_query}
    return render_template("member/voting.html", member=member, vote_items=vote_items, member_votes=member_votes)

@member_app.route("/apply_loan", methods=["GET", "POST"])
@member_required
def apply_loan():
    member = get_current_member()
    if request.method == "POST":
        amount = request.form.get("amount")
        cause = request.form.get("cause")
        loan_app = LoanApplication(member_id=member.member_id, amount_requested=amount, status="pending", cause=cause)
        db.session.add(loan_app)
        db.session.commit()
        flash(f"Loan application for {amount} BDT submitted successfully!", "success")
        return redirect(url_for("member.profile"))
    return render_template("member/apply_loan.html", member=member)
