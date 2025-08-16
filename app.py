# app.py - Main Flask Application
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta, timezone
import jwt
import hashlib
import random
import string
import os
from functools import wraps
import json

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///wordheist.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
CORS(app, origins=['http://localhost:3000', 'https://wordheist.vercel.app'])

# ============= MODELS =============

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    premium = db.Column(db.Boolean, default=False)
    premium_until = db.Column(db.DateTime, nullable=True)
    hints_remaining = db.Column(db.Integer, default=3)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_played = db.Column(db.Date, nullable=True)
    streak = db.Column(db.Integer, default=0)
    total_score = db.Column(db.Integer, default=0)
    
    # Relationships
    scores = db.relationship('Score', backref='user', lazy=True)
    progress = db.relationship('UserProgress', backref='user', lazy=True)

class Puzzle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    letters = db.Column(db.String(20), nullable=False)  # JSON array of letters
    mystery_word = db.Column(db.String(20), nullable=False)
    valid_words = db.Column(db.Text, nullable=False)  # JSON object with word lists
    difficulty = db.Column(db.String(20), default='medium')
    theme = db.Column(db.String(100))
    case_number = db.Column(db.Integer)
    case_title = db.Column(db.String(200))
    
    # Relationships
    scores = db.relationship('Score', backref='puzzle', lazy=True)
    progress = db.relationship('UserProgress', backref='puzzle', lazy=True)

class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    puzzle_id = db.Column(db.Integer, db.ForeignKey('puzzle.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    time_taken = db.Column(db.Integer)  # in seconds
    words_found = db.Column(db.Text)  # JSON array of found words
    completed = db.Column(db.Boolean, default=False)
    hints_used = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    puzzle_id = db.Column(db.Integer, db.ForeignKey('puzzle.id'), nullable=False)
    found_words = db.Column(db.Text, default='[]')  # JSON array
    current_score = db.Column(db.Integer, default=0)
    hints_used = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed = db.Column(db.Boolean, default=False)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'puzzle_id'),)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50))  # 'subscription', 'hints', 'remove_ads'
    amount = db.Column(db.Float)
    currency = db.Column(db.String(3), default='USD')
    status = db.Column(db.String(20))  # 'pending', 'completed', 'failed'
    stripe_payment_id = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============= PUZZLE GENERATOR =============

# Word lists for puzzle generation
PUZZLE_TEMPLATES = [
    {
        'letters': ['C', 'R', 'I', 'M', 'E', 'S'],
        'mystery': 'CRIMES',
        'theme': 'Mystery',
        'valid_words': {
            '3': ['ICE', 'SIR', 'RIM', 'IRE', 'SEC'],
            '4': ['RICE', 'MICE', 'CRIS', 'RIME', 'SEMI', 'ICES', 'SIRE'],
            '5': ['CRIME', 'CRIES', 'RICES', 'MISER', 'CIRES'],
            '6': ['CRIMES']
        }
    },
    {
        'letters': ['T', 'H', 'I', 'E', 'F', 'S'],
        'mystery': 'THIEFS',
        'theme': 'Heist',
        'valid_words': {
            '3': ['THE', 'HIT', 'FIT', 'SIT', 'TIE', 'HIS', 'ITS'],
            '4': ['THIS', 'HITS', 'FIST', 'TIES', 'SITE', 'HEFT'],
            '5': ['THIEF', 'SHIFT', 'HEFTS', 'HEIST'],
            '6': ['THIEFS']
        }
    },
    {
        'letters': ['S', 'T', 'O', 'L', 'E', 'N'],
        'mystery': 'STOLEN',
        'theme': 'Theft',
        'valid_words': {
            '3': ['SET', 'LET', 'NET', 'TEN', 'ONE', 'NOT', 'SON', 'TON', 'LOT'],
            '4': ['NEST', 'SENT', 'LETS', 'NETS', 'TENS', 'TONE', 'LOST', 'LOTS', 'SLOT'],
            '5': ['STONE', 'NOTES', 'STOLE', 'TONES'],
            '6': ['STOLEN']
        }
    }
]

def generate_daily_puzzle(date):
    """Generate or retrieve puzzle for a specific date"""
    # Use date as seed for consistent daily puzzles
    random.seed(date.toordinal())
    template = random.choice(PUZZLE_TEMPLATES)
    
    return {
        'letters': template['letters'],
        'mystery_word': template['mystery'],
        'valid_words': template['valid_words'],
        'theme': template['theme'],
        'case_number': (date.toordinal() % 1000) + 1,
        'case_title': f"The {template['theme']} Mystery"
    }

# ============= AUTHENTICATION =============

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.now(timezone.utc) + timedelta(days=30)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'No token provided'}), 401
        
        if token.startswith('Bearer '):
            token = token[7:]
        
        user_id = verify_token(token)
        if not user_id:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        request.user_id = user_id
        return f(*args, **kwargs)
    return decorated_function

# ============= API ROUTES =============

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'message': 'Word Heist API is running'})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not all([username, email, password]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if user exists
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken'}), 400
    
    # Create new user
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password)
    )
    db.session.add(user)
    db.session.commit()
    
    token = generate_token(user.id)
    
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'premium': user.premium
        }
    }), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if not all([email, password]):
        return jsonify({'error': 'Missing email or password'}), 400
    
    user = User.query.filter_by(email=email).first()
    
    if not user or user.password_hash != hash_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    token = generate_token(user.id)
    
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'premium': user.premium,
            'streak': user.streak,
            'total_score': user.total_score
        }
    })

@app.route('/api/daily-puzzle', methods=['GET'])
def get_daily_puzzle():
    # Get today's date or specific date from query params
    date_str = request.args.get('date')
    if date_str:
        puzzle_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        puzzle_date = datetime.now().date()
    
    # Check if puzzle exists in database
    puzzle = Puzzle.query.filter_by(date=puzzle_date).first()
    
    if not puzzle:
        # Generate new puzzle
        puzzle_data = generate_daily_puzzle(puzzle_date)
        puzzle = Puzzle(
            date=puzzle_date,
            letters=json.dumps(puzzle_data['letters']),
            mystery_word=puzzle_data['mystery_word'],
            valid_words=json.dumps(puzzle_data['valid_words']),
            theme=puzzle_data['theme'],
            case_number=puzzle_data['case_number'],
            case_title=puzzle_data['case_title']
        )
        db.session.add(puzzle)
        db.session.commit()
    
    # Get user progress if authenticated
    user_progress = None
    auth_header = request.headers.get('Authorization')
    if auth_header:
        token = auth_header.replace('Bearer ', '')
        user_id = verify_token(token)
        if user_id:
            progress = UserProgress.query.filter_by(
                user_id=user_id,
                puzzle_id=puzzle.id
            ).first()
            if progress:
                user_progress = {
                    'found_words': json.loads(progress.found_words),
                    'current_score': progress.current_score,
                    'hints_used': progress.hints_used,
                    'completed': progress.completed
                }
    
    return jsonify({
        'puzzle': {
            'id': puzzle.id,
            'date': puzzle.date.isoformat(),
            'letters': json.loads(puzzle.letters),
            'theme': puzzle.theme,
            'case_number': puzzle.case_number,
            'case_title': puzzle.case_title,
            'difficulty': puzzle.difficulty,
            'mystery_length': len(puzzle.mystery_word)
        },
        'user_progress': user_progress
    })

@app.route('/api/validate-word', methods=['POST'])
@require_auth
def validate_word():
    data = request.json
    word = data.get('word', '').upper()
    puzzle_id = data.get('puzzle_id')
    
    if not all([word, puzzle_id]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Get puzzle
    puzzle = Puzzle.query.get(puzzle_id)
    if not puzzle:
        return jsonify({'error': 'Invalid puzzle'}), 404
    
    # Check if word is valid
    valid_words = json.loads(puzzle.valid_words)
    word_length = str(len(word))
    is_valid = word in valid_words.get(word_length, [])
    is_mystery = word == puzzle.mystery_word
    
    if not is_valid:
        return jsonify({'valid': False, 'message': 'Not a valid word'}), 200
    
    # Update user progress
    user_id = request.user_id
    progress = UserProgress.query.filter_by(
        user_id=user_id,
        puzzle_id=puzzle_id
    ).first()
    
    if not progress:
        progress = UserProgress(
            user_id=user_id,
            puzzle_id=puzzle_id
        )
        db.session.add(progress)
    
    found_words = json.loads(progress.found_words)
    
    if word in found_words:
        return jsonify({'valid': True, 'duplicate': True, 'message': 'Already found'}), 200
    
    # Add word and update score
    found_words.append(word)
    progress.found_words = json.dumps(found_words)
    progress.current_score += len(word) * 10
    
    if is_mystery:
        progress.current_score += 100
        progress.completed = True
    
    # Update user's total score
    user = User.query.get(user_id)
    user.total_score += len(word) * 10
    if is_mystery:
        user.total_score += 100
    
    db.session.commit()
    
    return jsonify({
        'valid': True,
        'duplicate': False,
        'points': len(word) * 10,
        'is_mystery': is_mystery,
        'current_score': progress.current_score,
        'found_words': found_words,
        'completed': progress.completed
    })

@app.route('/api/use-hint', methods=['POST'])
@require_auth
def use_hint():
    data = request.json
    puzzle_id = data.get('puzzle_id')
    
    user = User.query.get(request.user_id)
    
    if user.hints_remaining <= 0 and not user.premium:
        return jsonify({'error': 'No hints remaining'}), 400
    
    # Get puzzle and progress
    puzzle = Puzzle.query.get(puzzle_id)
    progress = UserProgress.query.filter_by(
        user_id=request.user_id,
        puzzle_id=puzzle_id
    ).first()
    
    if not progress:
        progress = UserProgress(
            user_id=request.user_id,
            puzzle_id=puzzle_id
        )
        db.session.add(progress)
    
    # Find a word not yet found
    valid_words = json.loads(puzzle.valid_words)
    found_words = json.loads(progress.found_words)
    
    hint_word = None
    for length in ['3', '4', '5', '6']:
        for word in valid_words.get(length, []):
            if word not in found_words:
                hint_word = word
                break
        if hint_word:
            break
    
    if not hint_word:
        return jsonify({'error': 'No more words to find'}), 400
    
    # Deduct hint if not premium
    if not user.premium:
        user.hints_remaining -= 1
    
    progress.hints_used += 1
    db.session.commit()
    
    return jsonify({
        'hint': hint_word,
        'hints_remaining': user.hints_remaining if not user.premium else 'unlimited'
    })

@app.route('/api/submit-score', methods=['POST'])
@require_auth
def submit_score():
    data = request.json
    puzzle_id = data.get('puzzle_id')
    score = data.get('score')
    time_taken = data.get('time_taken')
    words_found = data.get('words_found')
    
    # Check if score already exists
    existing = Score.query.filter_by(
        user_id=request.user_id,
        puzzle_id=puzzle_id
    ).first()
    
    if existing:
        # Update if new score is higher
        if score > existing.score:
            existing.score = score
            existing.time_taken = time_taken
            existing.words_found = json.dumps(words_found)
            db.session.commit()
    else:
        # Create new score
        new_score = Score(
            user_id=request.user_id,
            puzzle_id=puzzle_id,
            score=score,
            time_taken=time_taken,
            words_found=json.dumps(words_found),
            completed=True
        )
        db.session.add(new_score)
        
        # Update user streak
        user = User.query.get(request.user_id)
        today = datetime.now().date()
        
        if user.last_played:
            days_diff = (today - user.last_played).days
            if days_diff == 1:
                user.streak += 1
            elif days_diff > 1:
                user.streak = 1
        else:
            user.streak = 1
        
        user.last_played = today
        db.session.commit()
    
    return jsonify({'success': True, 'message': 'Score submitted'})

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    period = request.args.get('period', 'daily')  # daily, weekly, all-time
    puzzle_id = request.args.get('puzzle_id')
    
    query = db.session.query(
        User.username,
        Score.score,
        Score.time_taken
    ).join(Score)
    
    if period == 'daily' and puzzle_id:
        query = query.filter(Score.puzzle_id == puzzle_id)
    elif period == 'weekly':
        week_ago = datetime.now() - timedelta(days=7)
        query = query.filter(Score.created_at >= week_ago)
    
    leaderboard = query.order_by(Score.score.desc()).limit(100).all()
    
    return jsonify({
        'leaderboard': [
            {
                'rank': idx + 1,
                'username': username,
                'score': score,
                'time': time_taken
            }
            for idx, (username, score, time_taken) in enumerate(leaderboard)
        ]
    })

@app.route('/api/user-stats', methods=['GET'])
@require_auth
def get_user_stats():
    user = User.query.get(request.user_id)
    
    # Get total puzzles solved
    puzzles_solved = Score.query.filter_by(
        user_id=request.user_id,
        completed=True
    ).count()
    
    # Get average score
    avg_score = db.session.query(db.func.avg(Score.score)).filter_by(
        user_id=request.user_id
    ).scalar() or 0
    
    return jsonify({
        'username': user.username,
        'streak': user.streak,
        'total_score': user.total_score,
        'puzzles_solved': puzzles_solved,
        'average_score': round(avg_score),
        'premium': user.premium,
        'hints_remaining': user.hints_remaining if not user.premium else 'unlimited'
    })

@app.route('/api/subscribe', methods=['POST'])
@require_auth
def subscribe():
    # This would integrate with Stripe/PayPal
    # For now, just a placeholder
    user = User.query.get(request.user_id)
    user.premium = True
    user.premium_until = datetime.now() + timedelta(days=30)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Subscription activated',
        'premium_until': user.premium_until.isoformat()
    })

# ============= DATABASE INITIALIZATION =============

@app.before_request
def create_tables():
    db.create_all()

@app.cli.command('init-db')
def init_db():
    """Initialize the database with tables and sample data."""
    db.create_all()
    print("Database initialized!")

@app.cli.command('seed-puzzles')
def seed_puzzles():
    """Generate puzzles for the next 30 days."""
    today = datetime.now().date()
    for i in range(30):
        puzzle_date = today + timedelta(days=i)
        if not Puzzle.query.filter_by(date=puzzle_date).first():
            puzzle_data = generate_daily_puzzle(puzzle_date)
            puzzle = Puzzle(
                date=puzzle_date,
                letters=json.dumps(puzzle_data['letters']),
                mystery_word=puzzle_data['mystery_word'],
                valid_words=json.dumps(puzzle_data['valid_words']),
                theme=puzzle_data['theme'],
                case_number=puzzle_data['case_number'],
                case_title=puzzle_data['case_title']
            )
            db.session.add(puzzle)
    db.session.commit()
    print("Puzzles seeded for next 30 days!")

if __name__ == '__main__':
    app.run(debug=True, port=5000)