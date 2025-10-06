import os
from dotenv import load_dotenv
from flask import Flask
from flask_migrate import Migrate
from extensions import db
from config import Config
from routes.public import public_app
from routes.admin import admin_app
from routes.member import member_app
from routes.superAdmin import superadmin_app
from routes.loanmanagement import loanmanagement_app
from routes.donationmanagement import donationmanagement_app
from routes.membermanagement import membermanagement_app
from routes.loanapplication import loan_app

load_dotenv()
migrate = Migrate() 
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.secret_key = app.config['FLASK_SECRET_KEY']
    db.init_app(app) 
    migrate.init_app(app, db)
    register_blueprints(app)
    return app
def register_blueprints(app):
    app.register_blueprint(public_app)
    app.register_blueprint(member_app, url_prefix="/member")
    app.register_blueprint(admin_app, url_prefix="/admin")
    app.register_blueprint(superadmin_app, url_prefix="/superadmin")
    app.register_blueprint(loan_app, url_prefix="/loanapplication")
    app.register_blueprint(loanmanagement_app, url_prefix="/loanmanagement")
    app.register_blueprint(donationmanagement_app, url_prefix="/donationmanagement")
    app.register_blueprint(membermanagement_app, url_prefix="/membermanagement")
    
app = create_app()
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
