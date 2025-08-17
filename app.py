# app.py - Fixed version for Railway
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
import jwt
import hashlib
import random
import json

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY', 'dev-secret-key-change-in-production')

# Fix for Railway PostgreSQL URL
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///wordheist.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
CORS(app, origins=['http://localhost:3000', 'https://wordheist.vercel.app'])

# ============= MODELS =============


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    streak = db.Column(db.Integer, default=0)
    total_score = db.Column(db.Integer, default=0)


class Puzzle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    letters = db.Column(db.String(20), nullable=False)
    mystery_word = db.Column(db.String(20), nullable=False)
    valid_words = db.Column(db.Text, nullable=False)
    case_number = db.Column(db.Integer)
    case_title = db.Column(db.String(200))

# ============= ROUTES =============


@app.route('/')
def home():
    return jsonify({
        'message': 'Word Heist API',
        'status': 'running',
        'endpoints': ['/api/health', '/api/daily-puzzle']
    })


@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'message': 'Word Heist API is running'
    })


@app.route('/api/daily-puzzle')
def get_daily_puzzle():
    # Simplified puzzle for testing
    puzzle_data = {
        'puzzle': {
            'id': 1,
            'date': datetime.now().date().isoformat(),
            'letters': ['C', 'R', 'I', 'M', 'E', 'S'],
            'theme': 'Mystery',
            'case_number': 1,
            'case_title': 'The Maltese Mystery',
            'difficulty': 'medium',
            'mystery_length': 6
        }
    }
    return jsonify(puzzle_data)


@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()

        # For testing, just return success
        return jsonify({
            'message': 'Registration endpoint working',
            'received': data
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()

        # For testing, just return success
        return jsonify({
            'message': 'Login endpoint working',
            'received': data
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Create tables on first request


@app.before_first_request
def create_tables():
    try:
        db.create_all()
        print("Database tables created")
    except Exception as e:
        print(f"Error creating tables: {e}")

# Error handlers


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found', 'message': str(e)}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
