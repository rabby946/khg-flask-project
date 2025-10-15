from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from datetime import datetime
from extensions import db
from models import MembershipApplication, Member, PasswordResetToken, Admin
from utils import upload_to_imgbb
public_app = Blueprint("public", __name__)
import secrets
from utils import sendMail, sendMailhtml1
from werkzeug.security import generate_password_hash


@public_app.context_processor
def inject_now():
    return {'year': datetime.now().year}

# ------------------ Public Routes ------------------ #
@public_app.route('/')
def home():
    return render_template('public/home.html')
@public_app.route('/instructions')
def instructions():
    return render_template('public/instructions.html')
@public_app.route('/about')
def about():
    return render_template('public/about.html')
@public_app.route("/login")
def login():
    return render_template("public/login.html")
@public_app.route("/privacy")
def privacy():
    return render_template("public/privacy.html")
@public_app.route("/terms")
def terms():
    return render_template("public/terms.html")

@public_app.route('/apply', methods=['GET', 'POST'])
def apply_membership():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        father_name = request.form.get('father_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        occupation = request.form.get('occupation')
        dob = request.form.get('dob')  
        nid = request.form.get('nid')
        
        password = request.form.get('password')
        file = request.files.get('photo_url')
        photo_url = upload_to_imgbb(file)
        if not full_name or not email or not phone or not password:
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("public.apply_membership"))
        date_of_birth = None
        if dob:
            try:
                date_of_birth = datetime.strptime(dob, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid date format. Use YYYY-MM-DD.", "danger")
                return redirect(url_for("public.apply_membership"))
        email_exists = MembershipApplication.query.filter(MembershipApplication.email==email).first()
        if email_exists:
            flash("Email already in use by another member.", "danger")
            return redirect(url_for("public.apply_membership"))

        phone_exists = Member.query.filter(Member.phone==phone).first()
        if phone_exists:
            flash("Phone number already in use by another member.", "danger")
            return redirect(url_for("public.apply_membership"))
        nid_exists = Member.query.filter(Member.nid==nid).first()
        if nid_exists:
            flash("NID already in use by another member.", "danger")
            return redirect(url_for("public.apply_membership"))
        nid_exists = MembershipApplication.query.filter(MembershipApplication.nid==nid).first()
        if nid_exists:
            flash("NID already in use by another member.", "danger")
            return redirect(url_for("public.apply_membership"))
        application = MembershipApplication(name=full_name,father_name=father_name,email=email,phone=phone,address=address,occupation=occupation,date_of_birth=date_of_birth,nid=nid,oath_paper_url="oath_paper_url",photo_url=photo_url,password_hash=password)
        db.session.add(application)
        db.session.commit()
        html_body = render_template("emails/apply_email.html",application=application,sender_name=current_app.config["BREVO_SENDER_NAME"])
        sendMailhtml1(email, "Your Membership Application Received", html_body)
        flash("Your application has been submitted successfully!", "success")
        return redirect(url_for("public.home"))

    return render_template('public/apply.html')

@public_app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get("name")
        email  = request.form.get("email")
        subject = request.form.get("subject")
        message = request.form.get("message")
        admin_emails = ["korjehasanahgroup@gmail.com"]
        if admin_emails:
            html_body = render_template("emails/contact_email.html",name=name,email=email,subject=subject,message=message, now=datetime.now())
            sendMailhtml1(admin_emails, f"New Contact: {subject}", html_body)
            flash("Your message has been sent successfully! ✅", "success")
        return redirect(url_for("public.contact"))
    return render_template("public/contact.html")

@public_app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        credentials = request.form.get("credential")
        user = None
        user_type = None
        user = Member.query.filter((Member.phone == credentials) | (Member.email == credentials)).first()
        if user:
            user_type = "member"
        if not user:
            user = Admin.query.filter((Admin.username == credentials) | (Admin.email == credentials)).first()
            if user:
                user_type = "admin"
        if not user:
            flash("No user found.", "danger")
            return redirect(url_for("public.forgot_password"))
        if not user.email:
            flash("This account does not have an email address. Contact support.", "warning")
            return redirect(url_for("public.forgot_password"))
        PasswordResetToken.query.filter_by(user_type=user_type, user_id=user.member_id if user_type == "member" else user.admin_id).delete()
        token = secrets.token_urlsafe(32)
        reset = PasswordResetToken(user_type=user_type,user_id=user.member_id if user_type == "member" else user.admin_id,token=token,)
        db.session.add(reset)
        db.session.commit()
        reset_link = url_for("public.reset_password", token=token, _external=True)
        html_body = render_template("emails/reset_password.html", name=user.name if user_type == "member" else user.username, reset_link=reset_link, now=datetime.utcnow(), user=user)
        sendMailhtml1(user.email, "Password Reset Request", html_body)
        name = user.full_name  if user_type != "member" else user.name
        flash(f"{name}, Password reset link sent to your email, {user.email}", "success")
        return redirect(url_for("public.login"))
    return render_template("public/forgot_password.html")

@public_app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    reset = PasswordResetToken.query.filter_by(token=token).first()
    if not reset or reset.expires_at < datetime.utcnow():
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for("public.forgot_password"))
    if request.method == "POST":
        new_password = request.form.get("password")
        hashed = generate_password_hash(new_password)
        if reset.user_type == "member":
            user = Member.query.get(reset.user_id)
            user.password_hash = hashed
        else:
            user = Admin.query.get(reset.user_id)
            user.password_hash = hashed
        db.session.delete(reset)  
        db.session.commit()
        print("coming")
        flash("Password updated successfully! Please log in.", "success")
        return redirect(url_for("public.login"))
    return render_template("public/reset_password.html", token=token)


