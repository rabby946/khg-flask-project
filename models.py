from extensions import db
from datetime import datetime, timedelta

# ------------------ MEMBER ------------------
class Member(db.Model):
    __tablename__ = "members"
    member_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    father_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(15))
    password_hash = db.Column(db.Text, nullable=False)
    join_date = db.Column(db.DateTime, default=datetime.utcnow)
    oath_paper_url = db.Column(db.String(200))
    nid = db.Column(db.String(20), unique=True)
    occupation = db.Column(db.String(100))
    photo_url = db.Column(db.String(300))
    address = db.Column(db.String(250))
    gender = db.Column(db.String(20))
    date_of_birth = db.Column(db.Date)
    
    loans = db.relationship("Loan", back_populates="member", lazy=True, cascade="all, delete-orphan")
    donations = db.relationship("Donation", back_populates="member", lazy=True, cascade="all, delete-orphan")
    loan_applications = db.relationship("LoanApplication", back_populates="member", lazy=True, cascade="all, delete-orphan")
    votes = db.relationship("Vote", back_populates="member", lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="member", lazy=True, cascade="all, delete-orphan")
    audit_logs = db.relationship("AuditLog", back_populates="member", lazy=True, cascade="all, delete-orphan")

# ------------------ ADMIN ------------------
class Admin(db.Model):
    __tablename__ = "admins"
    admin_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(50), default="admin")
    photo_url = db.Column(db.String(300))
    phone = db.Column(db.String(15))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    audit_logs = db.relationship("AuditLog", back_populates="admin", lazy=True, cascade="all, delete-orphan")
    loan_applications = db.relationship("LoanApplication", back_populates="admin", lazy=True, cascade="all, delete-orphan")
    sent_notifications = db.relationship("Notification", back_populates="admin", lazy=True, cascade="all, delete-orphan")

# ------------------ LOANS ------------------
class Loan(db.Model):
    __tablename__ = "loans"
    loan_id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.member_id"), nullable=False)
    approved_amount = db.Column(db.Numeric(12, 2), nullable=False)
    remaining_amount = db.Column(db.Numeric(12, 2), nullable=True)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="ongoing")  

    member = db.relationship("Member", back_populates="loans")
    transactions = db.relationship("LoanTransaction",back_populates="loan",lazy=True,cascade="all, delete-orphan",passive_deletes=True)

class LoanTransaction(db.Model):
    __tablename__ = "loan_transactions"
    transaction_id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer,db.ForeignKey("loans.loan_id", ondelete="CASCADE"),nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)  
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    loan = db.relationship("Loan", back_populates="transactions")

class LoanApplication(db.Model):
    __tablename__ = "loan_applications"
    application_id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.member_id", ondelete="CASCADE"), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.admin_id", ondelete="CASCADE"), nullable=True)
    amount_requested = db.Column(db.Numeric(12, 2), nullable=False)
    cause = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="pending")  
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    member = db.relationship("Member", back_populates="loan_applications")
    admin = db.relationship("Admin", back_populates="loan_applications")
    vote_item = db.relationship("VoteItem", back_populates="application", uselist=False, cascade="all, delete-orphan")
    votes = db.relationship("Vote", back_populates="application", lazy=True, cascade="all, delete-orphan")

# ------------------ DONATIONS ------------------
class Donation(db.Model):
    __tablename__ = "donations"
    donation_id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.member_id"), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    donation_type = db.Column(db.String(50), default="general")  
    donated_at = db.Column(db.DateTime, default=datetime.utcnow)

    member = db.relationship("Member", back_populates="donations")

# ------------------ VOTING ------------------
class VoteItem(db.Model):
    __tablename__ = "vote_items"
    item_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.DateTime, nullable=True)  

    application_id = db.Column(db.Integer, db.ForeignKey("loan_applications.application_id"), nullable=True)
    application = db.relationship("LoanApplication", back_populates="vote_item", uselist=False)
    votes = db.relationship("Vote", back_populates="item", lazy=True)

class Vote(db.Model):
    __tablename__ = "votes"
    vote_id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.member_id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("vote_items.item_id"), nullable=False)
    choice = db.Column(db.Integer, nullable=False) 
    voted_at = db.Column(db.DateTime, default=datetime.utcnow)
    application_id = db.Column(db.Integer, db.ForeignKey("loan_applications.application_id"), nullable=True)

    application = db.relationship("LoanApplication", back_populates="votes")
    member = db.relationship("Member", back_populates="votes")
    item = db.relationship("VoteItem", back_populates="votes")

    __table_args__ = (
        db.CheckConstraint('choice >= 0 AND choice <= 9', name='check_choice_range'),
        db.UniqueConstraint("member_id", "item_id", name="unique_member_vote"),
    )

# ------------------ NOTIFICATIONS ------------------
class Notification(db.Model):
    __tablename__ = "notifications"
    notification_id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.member_id"), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.admin_id", ondelete="CASCADE"), nullable=True)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), default="general")
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    member = db.relationship("Member", back_populates="notifications")
    admin = db.relationship("Admin", back_populates="sent_notifications")

# ------------------ AUDIT LOG ------------------
class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    log_id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("admins.admin_id", ondelete="CASCADE"), nullable=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.member_id"), nullable=False)
    action = db.Column(db.Text, nullable=False)
    target_table = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    admin = db.relationship("Admin", back_populates="audit_logs")
    member = db.relationship("Member", back_populates="audit_logs")

# ------------------ MEMBERSHIP APPLICATION ------------------
class MembershipApplication(db.Model):
    __tablename__ = "membership_applications"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    father_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    phone = db.Column(db.String(50), nullable=False)
    address = db.Column(db.String(250))
    gender = db.Column(db.String(20))
    date_of_birth = db.Column(db.Date)
    oath_paper_url = db.Column(db.String(200))
    nid = db.Column(db.String(20), unique=True)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="pending") 
    password_hash = db.Column(db.Text, nullable=False)
    occupation = db.Column(db.String(100))
    photo_url = db.Column(db.String(300))

    def __repr__(self):
        return f"<MembershipApplication {self.name} - {self.status}>"

# ------------------ RESET PASSWORD ------------------
class PasswordResetToken(db.Model):
    __tablename__ = "password_resets"
    id = db.Column(db.Integer, primary_key=True)
    user_type = db.Column(db.String(20), nullable=False)  
    user_id = db.Column(db.Integer, nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=1))

class DonationRequest(db.Model):
    __tablename__ = "donation_requests"
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.member_id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    donation_type = db.Column(db.String(50), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    transaction_id = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, default="N/A")
    status = db.Column(db.String(20), default="Pending")  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    updated_by = db.Column(db.String(100))  
    admin_note = db.Column(db.Text, default="N/A")

    member = db.relationship("Member", backref=db.backref("donation_requests", lazy=True))

class LoanRepaymentRequest(db.Model):
    __tablename__ = "loan_repayment_requests"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.member_id"), nullable=False)
    loan_id = db.Column(db.Integer, db.ForeignKey("loans.loan_id"), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    transaction_id = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, default="N/A")
    status = db.Column(db.String(20), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    updated_by = db.Column(db.String(100))
    admin_note = db.Column(db.Text, default="N/A")

    # Relationships
    member = db.relationship("Member", backref=db.backref("loan_repayment_requests", lazy=True))
    loan = db.relationship("Loan", backref=db.backref("repayment_requests", lazy=True))
