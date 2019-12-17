import os
import subprocess
import json
import re
from subprocess import Popen, PIPE, check_output
from flask import Flask, render_template, request, url_for, session, redirect
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from passlib.hash import sha256_crypt
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import bleach 


cpath = os.getcwd()
app_db_file = "sqlite:///{}".format(os.path.join(cpath, "app_db.db"))

app = Flask(__name__)
app.secret_key = 'BdAui8H9npasU'

#def create_app(config = None):
app.config["SQLALCHEMY_DATABASE_URI"] = app_db_file
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.urandom(16)

db = SQLAlchemy(app)

# used for  csrf token
csrf = CSRFProtect(app)

# talisman use for security 
Talisman(app, force_https=False, strict_transport_security=False, session_cookie_secure=False)


# declaring models 
class User(db.Model):
    __tablename__ = 'users'
    username = db.Column(db.String(20), unique = True, nullable = False, primary_key = True)
    password = db.Column(db.String(86), nullable = False)
    twofa = db.Column(db.String(11), nullable = False)
    role = db.Column(db.String(6), nullable = True)

    def __repr__(self):
        return "<User %r %r %r %r>" % (self.username, self.password, self.twofa, self.role)

class LoginHistory(db.Model):
    __tablename__ = 'history'
    lid = db.Column(db.Integer, nullable = False, autoincrement = True, primary_key = True) 
    lintime = db.Column(db.DateTime, nullable = False)
    louttime = db.Column(db.DateTime, nullable = True)
    username = db.Column(db.String(20), nullable = False)

    def __repr__(self):
        return "<LoginHistory %r %r %r %r>" % (self.lid, self.lintime, self.louttime, self.username)

class QueryHistory(db.Model):
    __tablename__ = 'queries'
    qid = db.Column(db.Integer, nullable = False, autoincrement = True, primary_key = True) 
    qtext = db.Column(db.String(3000), nullable = False)
    qresult = db.Column(db.String(3000), nullable = False)
    username = db.Column(db.String(20), nullable = False)

    def __repr__(self):
        return "<QueryHistory %r %r %r %r>" % (self.qid, self.qtext, self.qresult, self.username)

#db creation
db.create_all()

if (User.query.filter_by(username = "admin").count() == 0):
    admin_account = User (username = "admin", password = sha256_crypt.using(rounds = 324333).hash("Administrator@1"), twofa = "12345678901", role ="admin")
    db.session.add(admin_account)
    db.session.commit()


@app.route('/')
def index():
  
    return render_template("index.html")


@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        success = ""
        username = request.form['uname'].lower()
        password = request.form['pword']
        twofa = request.form['2fa']

        user = User.query.filter_by(username = username).first()

        if (user is not None):
            success = "failure"
        else:
            password = sha256_crypt.using(rounds=324333).hash(password)
            user = User(username = username, password = password, twofa = twofa)

            db.session.add(user)
            db.session.commit()
            success = "success"

        return render_template ("register.html", success = success)
    
    if request.method == 'GET':
        session.clear()
        success = "Please register to access the site"
        return render_template("register.html", success = success)


@app.route('/login', methods=['GET', 'POST'])
def login():
    admin = False

    # bleach used for sanitizing 
    if request.method == 'POST':
        result = ""
        username = bleach.clean(request.form['uname'].lower())
        password = bleach.clean(request.form['pword'])
        twofa = bleach.clean(request.form['2fa'])
        user = User.query.filter_by(username = username).first()

        if (user is not None):
            if sha256_crypt.verify(password, user.password):
                if (user.twofa == twofa):
                    timestamp = datetime.utcnow()

                    session['logged_in'] = True
                    session['user'] = username
                    session['lintime'] = timestamp.isoformat()
                    session['role'] = user.role
                    log = LoginHistory(username = username, lintime = timestamp)
                    db.session.add(log)
                    db.session.commit()
                    result = "success"
                else:
                    result = "Two-factor failure"
            else:
                result = "Incorrect password"
        else:
            result = "Incorrect user"
    
        return render_template('login.html', result = result)


    if request.method == 'GET':
        result = "Please login to use the site"

        return render_template("login.html", result = result)


@app.route('/spell_check', methods=['GET', 'POST'])
def spell():
    if(session.get('logged_in') == True): 
        if (session['role']) == 'admin':
            admin = True
        else:
            admin = False

        cpath = os.getcwd()

        if request.method == 'POST':
            outputtext = request.form['inputtext']
            textfile = open("./static/text.txt", "w")
            textfile.writelines(outputtext)
            textfile.close()

            tmp = subprocess.check_output([cpath + '/static/a.out', cpath + '/static/text.txt', cpath + '/static/wordlist.txt']).decode('utf-8')
            misspelled = tmp.replace("\n",", ")[:-2]

            queryLog = QueryHistory(qtext = outputtext, qresult = misspelled, username = session['user'])
            db.session.add(queryLog)
            db.session.commit()

            return render_template("spell_check.html", misspelled = misspelled, outputtext = outputtext)

        if request.method == 'GET':
            return render_template("spell_check.html", admin = admin)

    else:
        return redirect(url_for('login'))
    


@app.route('/history', methods = ['POST', 'GET'])
def history():
    if session.get('logged_in') == True:
        if session['role'] == 'admin':
            admin = True

            if request.method == 'GET':
                queries = QueryHistory.query.order_by(QueryHistory.qid)
            if request.method == 'POST':
                search_user = request.form['userquery'].lower() 
                queries = QueryHistory.query.filter_by(username = search_user).order_by(QueryHistory.qid)
        else:
            queries = QueryHistory.query.filter_by(username = session['user']).order_by(QueryHistory.qid)
            admin = False
        
        qCount = queries.count()
        return render_template('queryhistory.html', queries = queries, queriesCount = qCount, admin = admin)

    else:
        return redirect(url_for('login'))


@app.route('/history/query<id>')
def query(id):
    if session.get('logged_in') == True:

        if session['role'] == 'admin':
            query = QueryHistory.query.filter_by(qid = id).first() 
            admin = True
        else:
            query = QueryHistory.query.filter_by(qid = id, username = session['user']).first()
            admin = False     

        return render_template('queryview.html', query = query, admin = admin)

    else:
        return redirect(url_for('login'))


@app.route('/login_history', methods =['POST','GET'])
def login_history():
    if session.get('logged_in') == True and session['role'] == 'admin':
        admin = True

        if request.method =='GET':
            queries = LoginHistory.query.order_by(LoginHistory.lid)
        if request.method =='POST':
            search_user = request.form['userid'].lower()
            
            queries = LoginHistory.query.filter_by(username = search_user).order_by(LoginHistory.lid)       
        return render_template('login_history.html', queries = queries, admin = admin)

    else:
        return redirect(url_for('spell_check'))


@app.route('/logout')
def logout():
    timestamp = datetime.utcnow()
    currentLoginTime = datetime.strptime(session['lintime'], '%Y-%m-%dT%H:%M:%S.%f')
    
    currentLog = LoginHistory.query.filter_by(lintime = currentLoginTime, username = session['user']).first()
    currentLog.logoutTime = timestamp
    db.session.commit()
    
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')