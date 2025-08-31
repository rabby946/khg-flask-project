


from flask import Flask, render_template, request, redirect, flash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
from datetime import datetime

@app.context_processor
def inject_now():
    return {'year': datetime.now().year}
# ------------------ Public Routes ------------------ #

@app.route('/')
def home():
    return render_template('public/home.html')

@app.route('/instructions')
def instructions():
    return render_template('public/instructions.html')

@app.route('/apply', methods=['GET', 'POST'])
def apply_membership():
    if request.method == 'POST':
        # Here you can handle the form data and save to DB
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        occupation = request.form.get('occupation')
        dob = request.form.get('dob')
        monthly_contribution = request.form.get('monthly_contribution')

        # Example: flash message
        flash('Your application has been submitted successfully!')
        return redirect('/apply')

    return render_template('public/apply.html')

@app.route('/about')
def about():
    return render_template('public/about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')

        # Here you can handle saving or emailing the contact message
        flash('Your message has been sent!')
        return redirect('/contact')

    return render_template('public/contact.html')

@app.route('/login')
def login():
    return render_template("public/login.html")


if __name__ == '__main__':
    app.run(debug=True)
