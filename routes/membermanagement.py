from flask import redirect, url_for, render_template, flash, request, session, Blueprint, current_app
from utils import admin_required, _send_async_email, upload_to_imgbb, sendMailhtml1
from models import  db, Admin,  Member, MembershipApplication, AuditLog
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import  datetime
import threading

membermanagement_app = Blueprint("membermanagement", __name__, url_prefix="/membermanagement")

def sendMailhtml(recipient, subject, body):
    if not isinstance(recipient, list):
        recipient = [recipient]
    cur_admin = Admin.query.get(session["admin_id"])
    html_body = render_template("email_template.html",subject=subject,body=body,year=datetime.now().year,sender=cur_admin )
    app = current_app._get_current_object()
    threading.Thread(target=_send_async_email,args=(app, recipient, subject, html_body, True),daemon=True,).start()


@membermanagement_app.route("/")
@admin_required
def manage_members():
    members = Member.query.order_by(Member.join_date.desc()).all()
    return render_template("admin/manage_members.html", members=members)

@membermanagement_app.route("/<int:member_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_member(member_id):
    member = Member.query.get_or_404(member_id)
    if request.method == "POST":
        nid = request.form.get("nid")
        nid_exists = Member.query.filter(Member.nid == nid, Member.member_id != member.member_id).first()
        if nid_exists:
            flash("NID already in use by another member.", "danger")
            return redirect(url_for("membermanagement.edit_member", member_id=member.member_id))
        member.nid = nid
        member.name = request.form.get("name")
        member.father_name = request.form.get("father_name")
        member.email = request.form.get("email")
        member.phone = request.form.get("phone")
        member.occupation = request.form.get("occupation")
        member.address = request.form.get("address")
        member.gender = request.form.get("gender")
        member.date_of_birth = request.form.get("date_of_birth")
        photo_file = request.files.get("photo_file")
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
        return redirect(url_for("membermanagement.manage_members"))
        
    return render_template("admin/edit_member.html", member=member)

# Delete a member (cascade delete loans/donations)
@membermanagement_app.route("/<int:member_id>/delete", methods=["POST"])
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
    return redirect(url_for("membermanagement.manage_members"))

@membermanagement_app.route("/memberships")
@admin_required
def memberships():
    applications = MembershipApplication.query.order_by(MembershipApplication.applied_at.desc()).all()
    return render_template("admin/memberships.html", applications=applications)

@membermanagement_app.route("/membership-applications/<int:app_id>")
@admin_required
def application_details(app_id):
    application = MembershipApplication.query.get_or_404(app_id)
    return render_template("admin/application_details.html", application=application)


@membermanagement_app.route("/memberships/approve/<int:app_id>")
@admin_required
def approve_membership(app_id):
    app = MembershipApplication.query.get_or_404(app_id)
    if app.status != "pending":
        flash("This application has already been reviewed.", "warning")
        return redirect(url_for("membermanagement.memberships"))
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
    return redirect(url_for("membermanagement.memberships"))

@membermanagement_app.route("/memberships/reject/<int:app_id>")
@admin_required
def reject_membership(app_id):
    app = MembershipApplication.query.get_or_404(app_id)
    if app.status != "pending":
        flash("This application has already been reviewed.", "warning")
        return redirect(url_for("membermanagement.memberships"))
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
    return redirect(url_for("membermanagement.memberships"))

@membermanagement_app.route("/delete_membership/<int:app_id>", methods=["POST"])
@admin_required
def delete_membership(app_id):
    app = MembershipApplication.query.get_or_404(app_id)
    if app.status != "rejected":
        flash("Only rejected applications can be deleted.", "danger")
        return redirect(url_for("membermanagement.dashboard"))
    db.session.delete(app)
    db.session.commit()
    flash("Membership application deleted permanently.", "success")
    return redirect(url_for("membermanagement.dashboard"))