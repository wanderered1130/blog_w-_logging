import datetime
import os
import pathlib
from distutils.log import Log
from flask import Flask, render_template, request, redirect, url_for, flash, session # jsonify, make_response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
#from werkzeug.utils import secure_filename
#import datetime
#import random

from flask_mail import Mail, Message
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dengyi'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.example.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'your_username'
app.config['MAIL_PASSWORD'] = 'your_password'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

logging.basicConfig(filename='app.log', level=logging.DEBUG)

SRC_PATH = pathlib.Path(__file__).parent.absolute()
UPLOAD_FOLDER = os.path.join(SRC_PATH,  'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

UPLOAD_FOLDER = 'upload'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
basedir = os.path.abspath(os.path.dirname(__file__))
ALLOWED_EXTENSIONS = (['png', 'jpg', 'JPG', 'PNG', 'gif', 'GIF'])

db = SQLAlchemy()
login_manager = LoginManager(app)
mail = Mail(app)
db.init_app(app)

with app.app_context():
    db.create_all()

class Database(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))
    user = db.Column(db.String(50), unique=True)
    created = db.Column(db.DateTime(timezone=True), default=func.now())
    posts = db.relationship('Post', backref='database', passive_deletes=True)
    comment = db.relationship('Comment', backref='database', passive_deletes=True)

    def __init__(self, email, password, user):
        self.email = email
        self.password = password
        self.user = user

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text(1000), nullable=False)
    created = db.Column(db.DateTime(timezone=True), default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('database.id', ondelete="CASCADE"), nullable=False)
    comment = db.relationship('Comment', backref='post', passive_deletes=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text(1000), nullable=False)
    created = db.Column(db.DateTime(timezone=True), default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('database.id', ondelete="CASCADE"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete="CASCADE"), nullable=False)

@app.route('/')
@login_required
def index():
    posts = Post.query.order_by(Post.created.desc()).all()
    return render_template('index.html', posts=posts)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get("email")
        user = request.form.get("user")
        password = request.form.get("password")

        exist = Database.query.filter_by(email=email).first()
        user_exist = Database.query.filter_by(user=user).first()
        if exist:
            flash('電子信箱已被註冊',category='error')
        elif user_exist:
            flash('使用者名稱已被註冊',category='error')
        else:
            new_user = Database(email=email, user=user, password=generate_password_hash(password))
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=True)
            flash('註冊成功', category='success')
            return redirect(url_for('login'))
            # 新增資料庫記錄
            log = Log(user_id=new_user.id, action='Signup', timestamp=datetime.now())
            logging.info('User {} registered.'.format(new_user.user))
            db.session.add(log)
            db.session.commit()
            # 發送註冊通知郵件
            msg = Message('Registration Successful', recipients=[email])
            msg.body = 'Thank you for registering!'
            mail.send(msg)


    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get("email")
        user = request.form.get("user")
        password = request.form.get("password")

        exist = Database.query.filter_by(email=email).first()
        if exist:
            if check_password_hash(exist.password, password):
                flash('登入成功', category='success')
                login_user(exist, remember=True)
                # 新增登入記錄
                log = Log(user_id=exist.id, action='Login', timestamp=datetime.now())
                logging.info('User {} logged in.'.format(exist.user))
                db.session.add(log)
                db.session.commit()
                # 發送登入通知郵件
                msg = Message('Login Notification', recipients=[email])
                msg.body = 'You have logged in successfully.'
                mail.send(msg)
                return redirect(url_for('index'))
            else:
                flash('密碼錯誤', category='error')
                logging.warning('Login failed for user {}.'.format(email))
        else:
            flash('電子信箱錯誤', category='error')
            logging.warning('Login failed for user {}.'.format(email))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    # 新增登出記錄
    log = Log(user_id=current_user.id, action='Logout', timestamp=datetime.now())
    logging.info('User {} logged out.'.format(current_user.user))
    db.session.add(log)
    db.session.commit()
    logout_user()
    return render_template("index.html")

@app.route('/posts', methods=['GET', 'POST'])
@login_required
def post():
    if request.method == 'POST':
        text = request.form.get("text")
        if not text:
            # file = request.files['filename']
            # file.save(os.path.join(UPLOAD_FOLDER, file.filename))
            # print(file.filename)
            flash('請輸入內容', category='error')
            logging.error('Failed to add, delete, or modify a post.')
        elif 'password' in text:  # 檢查是否輸入了類似密碼的文字
            # 要求再三確認
            return render_template('confirm.html', text=text, action='post')
        else:
            posts = Post(text=text, user_id=current_user.id)
            db.session.add(posts)
            db.session.commit()
            flash('新增成功', category='success')
            # 新增貼文記錄
            log = Log(user_id=current_user.id, action='Post', timestamp=datetime.now())
            logging.debug('User {} added a new post.'.format(current_user.user))
            db.session.add(log)
            db.session.commit()
            return redirect(url_for('index'))
    return render_template('posts.html',user=current_user.user)

@app.route('/delete-post/<id>')
@login_required
def delete(id):
    post = Post.query.filter_by(id=id).first()
    if post:
        if current_user.id != post.user_id:
            flash('你沒有權限刪除', category='error')
            logging.error('Failed to add, delete, or modify a post.')
        elif current_user.id == post.user_id:
            db.session.delete(post)
            db.session.commit()
            logging.debug('User {} deleted a post.'.format(current_user.user))
            flash('刪除成功', category='success')
        else:
            flash('刪除失敗', category='error')
            logging.error('Failed to add, delete, or modify a post.')
    return redirect(url_for('index'))

@app.route('/edit-post/<id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.filter_by(id=id).first()
    if request.method == 'POST':
        text = request.form.get("text")
        if current_user.id != post.user_id:
            logging.error('Failed to add, delete, or modify a post.')
            flash('你沒有權限編輯', category='error')
        elif current_user.id == post.user_id:
            if not text:
                logging.error('Failed to add, delete, or modify a post.')
                flash('請輸入內容', category='error')
            else:
                post.text = text
                db.session.commit()
                logging.debug('User {} edited a post.'.format(current_user.user))
                flash('編輯成功', category='success')
                return redirect(url_for('index'))
    return render_template('edit-post.html', post=post)

@app.route('/create-comment/<post_id>', methods=['GET', 'POST'])
@login_required
def comment(post_id):
    text = request.form.get("text")
    if request.method == 'POST':
        if not text:
            logging.error('Failed to add or delete a comment.')
            flash('請輸入內容', category='error')
        elif 'password' in text:  # 檢查是否輸入了類似密碼的文字
            # 要求再三確認
            logging.error('Failed to add or delete a comment.')
            return render_template('confirm.html', text=text, action='comment')
        else:
            post = Post.query.filter_by(id=post_id).first()
            if post:
                comment = Comment(text=text, user_id=current_user.id, post_id=post_id)
                db.session.add(comment)
                db.session.commit()
                flash('新增成功', category='success')
                # 新增留言記錄
                log = Log(user_id=current_user.id, action='Comment', timestamp=datetime.now())
                logging.debug('User {} added a new comment.'.format(current_user.user))
                db.session.add(log)
                db.session.commit()
                return redirect(url_for('index'))
            else:
                logging.error('Failed to add or delete a comment.')
                flash('新增失敗', category='error')
    return render_template('index.html')

@app.route('/delete-comment/<id>')
@login_required
def delete_comment(id):
    comment = Comment.query.filter_by(id=id).first()
    if comment:
        if current_user.id != comment.user_id:
            logging.error('Failed to add or delete a comment.')
            flash('你沒有權限刪除', category='error')
        elif current_user.id == comment.user_id:
            db.session.delete(comment)
            db.session.commit()
            logging.debug('User {} deleted a comment.'.format(current_user.user))
            flash('刪除成功', category='success')
        else:
            logging.error('Failed to add or delete a comment.')
            flash('刪除失敗', category='error')
    return redirect(url_for('index'))

@app.route('/', methods=['POST'])
def upload_file():
    file = request.files['filename']
    if file.filename != '':
        file.save(os.path.join(UPLOAD_FOLDER, file.filename))
    return redirect(url_for('index'))

@app.route('/img/<filename>')
def display_image(filename):
    return redirect(url_for('static', filename='uploads/' + filename))

#createdatabase(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(id):
    return Database.query.get(int(id))

@app.route('/confirm/<confirmed>', methods=['GET', 'POST'])
def confirmed(confirmed):
    if confirmed == 'yes':
        text = session.get('text')
        action = session.get('action')
        if action == 'post':
            # 新增貼文記錄
            log = Log(user_id=current_user.id, action='Post', timestamp=datetime.now())
            db.session.add(log)
            db.session.commit()
            flash('貼文成功', category='success')
        elif action == 'comment':
            # 新增留言記錄
            log = Log(user_id=current_user.id, action='Comment', timestamp=datetime.now())
            db.session.add(log)
            db.session.commit()
            flash('留言成功', category='success')
    elif confirmed == 'no':
        flash('取消操作', category='info')
    return redirect(url_for('index'))

# @app.before_first_request
# def create_tables():
#     app.before_request_funcs[None].remove(create_tables)
#     db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
