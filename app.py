import os
import random
import google.generativeai as genai
import pandas as pd

from authlib.integrations.flask_client import OAuth
from flask.cli import load_dotenv
from flask import Flask, url_for, session, redirect, jsonify, request
from flask_sqlalchemy import SQLAlchemy

load_dotenv()
app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    access_token_url="https://oauth2.googleapis.com/token",
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    api_base_url="https://www.googleapis.com/oauth2/v3/",
    jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
    client_kwargs={
        "scope": "openid email profile",
    },
)

def load_items(file_path: str) -> list:
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            items = list(line.strip() for line in file)
            return items
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return []

file_path = 'data/items.txt'
items = load_items(file_path)

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

generation_config = genai.GenerationConfig(
    temperature=1,
    top_p=0.95,
    top_k=40,
    max_output_tokens=8192,
    response_mime_type="text/plain",
)

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    system_instruction=f"너는 나와 스무고개 게임을 할거야. 정답 단어는 {random.choice(items)}야. 내가 포기하면 '포기하셨습니다.' 라는 문장과 함께 정답을 알려줘. 정답을 맞히면 '정답입니다!' 와 함게 정답을 말해줘.",
    generation_config=generation_config,
)

chat_session = model.start_chat(
  history=[
  ]
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)

class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    attempts = db.Column(db.Integer, nullable=False)
    result = db.Column(db.String(20), nullable=False)
    date = db.Column(db.Date, nullable=False, default=db.func.current_date())

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return "Hello, World!"

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = google.authorize_access_token()
    user_info = oauth.google.get('https://www.googleapis.com/oauth2/v3/userinfo').json()

    user = User.query.filter_by(email=user_info['email']).first()
    if not user:
        user = User(email=user_info['email'], name=user_info['name'])
        db.session.add(user)
        db.session.commit()

    session['user'] = {'email': user.email, 'name': user.name}

    return redirect(url_for('index'))

@app.route('/game', methods=['POST'])
def game():
    data =request.get_json()
    user_input = data['input'] if data else None

    if not user_input:
        return jsonify({'error': "Request Body must include 'input'"}), 400

    if len(user_input) > 100:
        return jsonify({'error': "Input must be less than 100 characters"}), 400

    response = chat_session.send_message(user_input).text

    if 'user' in session:
        user = User.query.filter_by(email=session['user']['email']).first()
        record = Record.query.filter_by(user_id=user.id, date=db.func.current_date()).first()

        if not record:
            record = Record(
                user_id = user.id,
                attempts = 1,
                result = 'in_progress'
            )
            db.session.add(record)
            db.session.commit()
        elif record.result == 'in_progress':
            record.attempts += 1
            db.session.commit()

        if '정답입니다!' in response:
            record.result = 'success'
            db.session.commit()
        elif '포기하셨습니다.' in response:
            record.result = 'failure'
            db.session.commit()

    return jsonify({'message': response})

@app.route('/record', methods=['GET'])
def records():
    if 'user' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user = User.query.filter_by(email =session['user']['email']).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    records = Record.query.filter(Record.result.in_(['success', 'failure'])).all()
    record_list = [
        {
            'user_id': record.user_id,
            'attempts': record.attempts,
            'result': record.result,
            'date': record.date
        }
        for record in records
    ]

    columns = ['user_id', 'attempts', 'result', 'date']
    df = pd.DataFrame(record_list, columns=columns)

    # 성공률 계산
    my_records = df[df['user_id'] == user.id]
    success_count = len(my_records[my_records['result'] == 'success'])
    total_games = len(my_records)
    success_rate = (success_count / total_games * 100) if total_games > 0 else 0

    # 내 평균 시도 횟수 계산
    my_avg_attempts = my_records['attempts'].mean() if total_games > 0 else 0

    # 평균 시도 횟수 백분위수 계산
    avg_attempts_by_user = df.groupby('user_id')['attempts'].mean()
    my_rank = avg_attempts_by_user.rank(ascending=False).get(user.id)
    my_percentile = (my_rank-1) / len(avg_attempts_by_user) * 100

    my_record_list = my_records.to_dict('records')

    return jsonify({
        'success_rate': f"{success_rate: .2f}%",
        'my_avg_attempts': f"{my_avg_attempts}",
        'my_percentile': f"{my_percentile: .2f}%",
        'record_list': my_record_list
    })

if __name__ == '__main__':
    app.run()