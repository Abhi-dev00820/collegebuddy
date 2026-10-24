
import os
import re
import random
from functools import wraps

from flask import (
    Flask, render_template, session, flash,
    request, redirect, url_for, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from rapidfuzz import fuzz, process

# Flask configs

app = Flask(__name__)


app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-me")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# model

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)


# --------------------------------------------------
# Chatbot response dataset
#
# Each intent contains example user messages and
# possible responses. Add more examples as needed.
# --------------------------------------------------

CHATBOT_DATA = {
    "greeting": {
        "patterns": [
            "hi", "hello", "hey", "hey there",
            "hi bro", "hello buddy", "good morning",
            "good evening", "howdy"
        ],
        "responses": [
            "Hey! What's going on?",
            "Hi! How's your day been?",
            "Hey there. What are you up to?",
            "Hello! Tell me what's on your mind."
        ]
    },

    "how_are_you": {
        "patterns": [
            "how are you", "how are you doing",
            "how have you been", "what's up",
            "how is it going", "you doing good"
        ],
        "responses": [
            "I'm doing good! What's happening with you?",
            "All good here. How's your day going?",
            "I'm here and ready to chat. How about you?"
        ]
    },

    "sadness": {
        "patterns": [
            "i feel sad", "i am feeling low",
            "i feel down", "i am upset",
            "i am not feeling good", "having a bad day",
            "nothing feels right"
        ],
        "responses": [
            "That sounds like a difficult day. Want to talk about what happened?",
            "Some days really do feel heavy. What's been bothering you?",
            "I'm listening. You can tell me what's going on."
        ]
    },

    "stress": {
        "patterns": [
            "i am stressed", "i feel stressed",
            "too much work", "i have too many assignments",
            "college is stressful", "i am exhausted",
            "i had a hectic day", "i feel overwhelmed"
        ],
        "responses": [
            "Sounds like you've had a lot on your plate. What took up most of your day?",
            "That's a lot to deal with at once. Want to talk through it?",
            "College can pile things up quickly. What's stressing you out the most?"
        ]
    },

    "happiness": {
        "patterns": [
            "i am happy", "i feel great",
            "today was amazing", "i am excited",
            "something good happened", "i had a great day"
        ],
        "responses": [
            "That's great! What happened?",
            "Nice! Tell me what made your day so good.",
            "Love that. What's the good news?"
        ]
    },

    "college": {
        "patterns": [
            "i hate college", "college is boring",
            "i am tired of college", "college life",
            "my college is stressful", "i have college tomorrow"
        ],
        "responses": [
            "What's bothering you about college lately?",
            "College can be a mixed bag. Is it the workload, people, or something else?",
            "Tell me more. What happened at college?"
        ]
    },

    "programming": {
        "patterns": [
            "i am learning python", "i am coding",
            "i am learning flask", "programming is hard",
            "i built a project", "i am learning backend",
            "i want to become a developer"
        ],
        "responses": [
            "Nice! What are you building right now?",
            "Building projects is a good way to learn. What part are you working on?",
            "That's interesting. What have you figured out so far?"
        ]
    },

    "achievement": {
        "patterns": [
            "i built my first project",
            "i completed my project",
            "i finally did it",
            "i achieved something",
            "i am proud of myself"
        ],
        "responses": [
            "That's a solid achievement. What did you build?",
            "You put in the work and got it done. How does it feel?",
            "Nice work! What's the next thing you want to try?"
        ]
    },

    "boredom": {
        "patterns": [
            "i am bored", "i feel bored",
            "nothing to do", "i have nothing to do",
            "i am getting bored"
        ],
        "responses": [
            "Want to talk about something random or explore a new idea?",
            "Sounds like you need a change of pace. What's usually fun for you?",
            "We could talk about coding, games, college, or anything else."
        ]
    },

    "thanks": {
        "patterns": [
            "thanks", "thank you", "thanks bro",
            "thank you so much", "that helped"
        ],
        "responses": [
            "Anytime!",
            "No problem. What's next?",
            "Glad that helped."
        ]
    },

    "goodbye": {
        "patterns": [
            "bye", "goodbye", "see you",
            "talk to you later", "i am leaving"
        ],
        "responses": [
            "See you later!",
            "Catch you next time.",
            "Take care. Come back whenever you want to chat."
        ]
    },

    "identity": {
        "patterns": [
            "who are you", "what is your name",
            "are you a bot", "what are you",
            "tell me about yourself"
        ],
        "responses": [
            "I'm Basepython, a small chatbot built with Flask and a response dataset.",
            "I'm Basepython! I match your messages to examples and respond accordingly.",
            "I'm a dataset-driven chatbot, still growing one response at a time."
        ]
    }
}


# Text normalization

def normalize_text(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


PATTERN_TO_INTENT = {}

for intent, details in CHATBOT_DATA.items():
    for pattern in details["patterns"]:
        normalized_pattern = normalize_text(pattern)
        PATTERN_TO_INTENT[normalized_pattern] = intent


# fuzzy matching and response generation

def generate_response(user_message):
    message = normalize_text(user_message)

    if not message:
        return "Type something and I'll respond."

    # Prefer an exact match when one exists.
    if message in PATTERN_TO_INTENT:
        intent = PATTERN_TO_INTENT[message]
        return random.choice(CHATBOT_DATA[intent]["responses"])

    # Find the closest known example.
    match = process.extractOne(
        message,
        list(PATTERN_TO_INTENT.keys()),
        scorer=fuzz.WRatio,
        score_cutoff=70
    )

    if match:
        matched_pattern, score, _ = match
        intent = PATTERN_TO_INTENT[matched_pattern]

        # Avoid accepting weak matches for longer messages.
        # The score cutoff above is a starting point, not
        # a guarantee that the selected intent is correct.
        return random.choice(CHATBOT_DATA[intent]["responses"])

    # Fallback when no example matches sufficiently.
    return (
        "I'm not quite sure what you mean yet. "
        "Could you tell me a little more?"
    )


# --------------------------------------------------
# Authentication helper
# Restricts chatbot pages and API access to logged-in
# users. The API receives JSON from the frontend.
# --------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            if request.path == "/chatbot":
                return jsonify({
                    "response": "Your session has expired. Please log in again.",
                    "login_required": True
                }), 401

            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("UsernameL", "").strip()
        password = request.form.get("PasswordL", "")

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("index"))

        flash("Invalid username or password.")

    return render_template("login.html")



@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("UsernameS", "").strip()
        password = request.form.get("PasswordS", "")

        if not username or not password:
            flash("Username and password are required.")
            return render_template("signup.html")

        if len(username) > 20:
            flash("Username must be 20 characters or fewer.")
            return render_template("signup.html")

        if User.query.filter_by(username=username).first():
            flash("User already exists. Please log in.")
            return render_template("signup.html")

        
        new_user = User(
            username=username,
            password=generate_password_hash(password)
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully. You can log in now.")
        return redirect(url_for("login"))

    return render_template("signup.html")


# Main chatbot page

@app.route("/index")
@login_required
def index():
    return render_template("index.html")



# Chat API
# Receives {"message": "..."} and returns JSON.

@app.route("/chatbot", methods=["POST"])
@login_required
def chatbot():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")

    if not isinstance(message, str):
        return jsonify({"error": "Message must be text."}), 400

    message = message.strip()

    if not message:
        return jsonify({"error": "Please enter a message."}), 400

    if len(message) > 1000:
        return jsonify({"error": "Message is too long."}), 400

    response = generate_response(message)

    return jsonify({"response": response})


# Logout

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# run the application

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)
