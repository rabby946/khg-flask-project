from flask import Blueprint, render_template, redirect, url_for, request, flash
from datetime import datetime
from extensions import db
from models import MembershipApplication, Member
from utils import upload_to_imgbb
public_app = Blueprint("public", __name__)

# Inject current year into templates
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
        dob = request.form.get('dob')  # Expecting format 'YYYY-MM-DD'
        nid = request.form.get('nid')
        fle = request.files.get('oath_paper_url')
        oath_paper_url = upload_to_imgbb(fle)
        password = request.form.get('password')
        file = request.files.get('photo_url')
        photo_url = upload_to_imgbb(file)
        # Basic validation
        if not full_name or not email or not phone or not password:
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("public.apply_membership"))
        # Convert date string to datetime.date
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
        # Create membership application
        application = MembershipApplication(
            name=full_name,
            father_name=father_name,
            email=email,
            phone=phone,
            address=address,
            occupation=occupation,
            date_of_birth=date_of_birth,
            nid=nid,
            oath_paper_url=oath_paper_url,
            photo_url=photo_url,
            password_hash=password  # Later, hash it before saving
        )

        db.session.add(application)
        db.session.commit()

        flash("Your application has been submitted successfully!", "success")
        return redirect(url_for("public.home"))

    return render_template('public/apply.html')


@public_app.route('/about')
def about():
    return render_template('public/about.html')


@public_app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get("name")
        email  = request.form.get("email")
        subject = request.form.get("subject")
        message = request.form.get("message")
        print(name, email, subject, message)
    return render_template("public/contact.html")
@public_app.route("/login")
def login():
    return render_template("public/login.html")