from flask import Flask, render_template, redirect, url_for, flash, request , Response , session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
#import requests
from datetime import datetime
import json
from zhipuai import ZhipuAI
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = 'lp308OCGxxxxxxxxVLGKSk2HQ'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
#创建config表格，并且储存如site.db

messages = [] #! 假设存储消息的列表

db = SQLAlchemy(app)#数据
bcrypt = Bcrypt(app)#加密
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
#建表1

class Message(db.Model):
    
    id = db.Column(db.Integer, primary_key=True)#序号
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)#标号(?,有重复)
    username = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.now)

    user = db.relationship('User', backref=db.backref('messages', lazy=True))
#见表2，记录用户信息和交互内容，relationship建立用户与内容的对应关系

class SurveyResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.String(10), nullable=False)  # "yes" or "no"
    timestamp = db.Column(db.DateTime, default=datetime.now)

    user = db.relationship('User', backref=db.backref('responses', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
# Warning

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))#登陆成功
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')#加密
        user = User(username=username, password=hashed_password)
        db.session.add(user)
        db.session.commit()#手动提交（没有用这一行代码会怎样？）
        flash('Your account has been created! You can now log in', 'success')
        #并没有看到，，但是也没啥关系。。
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()#warning
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user, remember=request.form.get('remember'))
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html')

@app.route("/")
def index():
    return redirect(url_for('login'))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/home")
@login_required
def home():
    return render_template('home.html')

@app.route("/upload_message", methods=['POST'])
@login_required
def upload_message():
    username = current_user.username
    user_message = request.form.get('message')
    message_time = datetime.now()

    user = User.query.filter_by(username=username).first()

    if not user_message.strip():
        return render_template('error.html', error_message="输入不能为空或只有空格")
    
    session['user_message'] = user_message
    session['username'] = username
    session['message_time'] = message_time.isoformat()  # 将时间序列化为字符串

    return "Message received", 200

# 处理流式输出并保存到数据库
@app.route("/stream_response")
@login_required
def stream_response():
    username = session.get('username')
    user_message = session.get('user_message')
    message_time_str = session.get('message_time')

    if not username or not user_message:
        return "No active message", 400

    user = User.query.filter_by(username=username).first()
    message_time = datetime.fromisoformat(message_time_str)  # 将时间反序列化为 datetime 对象

    # 初始化 API 客户端
    client = ZhipuAI(api_key="6e12ec3xxxxxxxxxxzgRCP0YK")  # 替换为你的 API Key，已打码
    response = client.chat.completions.create(
        model="glm-4",
        messages=[
            {
                "role": "user",
                "content": f'{user_message}'
            }
        ],
        stream=True  # 启用流式输出
    )

    def generate():
        response_text = ""
        for chunk in response:
            partial_response = chunk.choices[0].delta.content
            response_text += partial_response
            yield f"data: {partial_response}\n\n"

        # 在流结束后，将消息和响应写入数据库
        with app.app_context():
            if user:
                message = Message(user_id=user.id, username=username, message=user_message, response=response_text, timestamp=message_time)
                db.session.add(message)
                db.session.commit()

    return Response(generate(), content_type='text/event-stream')

@app.route("/submit_answer", methods=['POST'])
@login_required
def submit_answer():
    data = request.get_json()
    question = data.get('question')
    answer = data.get('answer')
    #user_id = current_user.id

    # 将回答存储在数据库中
    new_response = SurveyResponse(user_id=current_user.username, question=question, answer=answer)
    db.session.add(new_response)
    db.session.commit()

    return {"status": "success"}, 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # 创建数据库及其表
    app.run(debug=True, host='0.0.0.0')





