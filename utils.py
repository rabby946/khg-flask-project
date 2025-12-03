from config import Config
import  threading
import traceback
from flask import g
from functools import wraps
from flask import current_app, session, flash, redirect, url_for, request
from models import Member


import cloudinary
import  sib_api_v3_sdk
import cloudinary
import cloudinary.uploader
cloudinary.config(
    cloud_name=Config.CLOUD_NAME,
    api_key=Config.CLOUD_API_KEY,
    api_secret=Config.CLOUD_API_SECRET
)

def upload_to_imgbb(file):
    result = cloudinary.uploader.upload(file)
    return result['secure_url']

def _send_async_email(app, recipient, subject, body, html=False):
    with app.app_context():
        try:
            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key["api-key"] = app.config["BREVO_API_KEY"]
            api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
            sender = {
                "name": app.config["BREVO_SENDER_NAME"],
                "email": app.config["BREVO_SENDER_EMAIL"],
            }
            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(to=[{"email": r} for r in recipient],
                                                           subject=subject,sender=sender,html_content=body if html else f"<p>{body}</p>",
                                                           text_content=None if html else body,)
            api_instance.send_transac_email(send_smtp_email)
            app.logger.info(f"Brevo email sent to {recipient}")
        except Exception as e:
            app.logger.error(f"Brevo email failed: {e}\n{traceback.format_exc()}")

def sendMail(recipient, subject, body):
    if not isinstance(recipient, list):
        recipient = [recipient]
    app = current_app._get_current_object()
    threading.Thread(target=_send_async_email,
                     args=(app, recipient, subject, body, False),daemon=True,).start()

def sendMailhtml1(recipient, subject, html_body):
    """Send HTML email asynchronously via Brevo API."""
    if not isinstance(recipient, list):
        recipient = [recipient]
    app = current_app._get_current_object()
    threading.Thread(target=_send_async_email,
                     args=(app, recipient, subject, html_body, True),daemon=True,).start()

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("Login required", "error")
            return redirect(url_for('public.login', next=request.url))
        return view(*args, **kwargs)
    return wrapped

def member_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("member_logged_in"):
            flash("Login required", "error")
            return redirect(url_for('member.login', next=request.url))

        g.member = Member.query.get(session.get("member_id"))
        if not g.member:
            session.pop("member_logged_in", None)
            session.pop("member_id", None)
            flash("Member not found", "error")
            return redirect(url_for('member.login'))

        return view(*args, **kwargs)
    return wrapped
