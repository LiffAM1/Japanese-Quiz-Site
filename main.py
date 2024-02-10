import json
import os
import transaction
from flask import Flask, redirect, request, url_for, abort, make_response, render_template
from models import *
from repo import * 
from quizutils import QuizUtils
from secretutils import SecretUtils
from miscutils import MiscUtils
from flask_cors import CORS

from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from oauthlib.oauth2 import WebApplicationClient
import requests

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.config["IMAGE_UPLOADS"] = "static"

secret_util = SecretUtils()

# Env setup
GOOGLE_CLIENT_ID = secret_util.get_secret("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = secret_util.get_secret("GOOGLE_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration")
BASE_URL = os.environ.get("BASE_URL", None)

users_repo = UsersRepo()
quizzes_repo = QuizzesRepo()
quiz_attempts_repo = QuizAttemptsRepo()


client = WebApplicationClient(GOOGLE_CLIENT_ID)
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return users_repo.get(user_id)

# Temp landing page
def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

# Google login logic
@app.route("/login")
def login():
    url = request.args.get('url')
    if url is None:
        url = "/"

    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    resp = make_response(make_response(redirect(request_uri)))
    resp.set_cookie('redirect_url', url) 
    return resp

@app.route("/logout")
@login_required
def logout():
    user = load_user(current_user.id)
    users_repo.set_inactive(user.id)
    logout_user()
    return redirect("/")

@app.route("/login/callback")
def callback():
    # Get the code from the querystring
    code = request.args.get("code")

    # Find the token issuer endpoint
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    # Get token via code
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
    )

    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
    )

    client.parse_request_body_response(json.dumps(token_response.json()))

    # Hit user info endpoint
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        users_name = userinfo_response.json()["given_name"]
    else:
        return "User email not available or not verified by Google.", 400

    user = users_repo.get(unique_id)
    if not user:
        user = User(id=unique_id, name=users_name, display_name=users_name, email=users_email, is_active=True, is_authenticated=True, average_score=0, count_quizzes=0)
        users_repo.save(user)
    else:
        users_repo.set_active(user.id)
    user = users_repo.get(unique_id)

    # Begin user session by logging the user in
    login_user(user, remember=True)
    url = request.cookies.get('redirect_url') 
    return redirect(url)


# Other routes
@app.route("/")
def home():
    def format_leaderboard(leaderboard):
        for u in leaderboard:
            av_score = leaderboard[u].average_score
            leaderboard[u].average_score = MiscUtils.format_percent(av_score)
        return leaderboard 

    try:
        # Calculate the leaderboard
        all_users = users_repo.get_all()
        leaderboard = QuizUtils.calculate_leaderboard(all_users)

        # quizzes test
        quizzes = quizzes_repo.get_all()
        user_logged_in = (current_user and current_user.is_active)
        return render_template('home.html', base_url=BASE_URL, user_logged_in=user_logged_in, ranks=list(format_leaderboard(leaderboard).values()), quizzes=quizzes, nav=get_nav(), head=get_head(), foot=get_foot())
    except Exception as e:
        return abort(500, str(e))

@app.route("/user/profile")
@login_required
def user_profile():
    user = load_user(current_user.id)
    attempts = quiz_attempts_repo.get_all_for_user(user.id)
    return render_template('profile.html', user=user.to_display_dict(), attempts=[a.to_display_dict() for a in attempts], base_url=BASE_URL, nav=get_nav(), head=get_head(), foot=get_foot())

@app.route("/quiz/<quiz_id>")
def quiz(quiz_id):
    try:
        question_language = request.args.get('question_language')
        answer_language = request.args.get('answer_language')

        if not current_user or not current_user.is_active:
            return redirect(url_for('login', url = f"/quiz/{quiz_id}?question_language={question_language}&answer_language={answer_language}"))
        
        # If someone tries to go directly to the URL
        if question_language == answer_language:
            return redirect("/")

        quiz = quizzes_repo.get(quiz_id)
        if not quiz:
            return abort(404)

        quiz_view = quiz.get_quiz_view(question_language)

        return render_template('quiz.html', \
            quiz_id=quiz.id,
            quiz=quiz_view,
            quiz_question_ids = list(quiz.questions.keys()),
            question_language=question_language,
            answer_language=answer_language,
            base_url=BASE_URL,
            nav=get_nav(),
            head=get_head(),
            foot=get_foot())
    except Exception as e:
        print(e)
        return abort(500, str(e))

@app.route('/quiz/<quiz_id>/submit', methods=['POST'])
@login_required
def quiz_submit(quiz_id):
    try:
        user = load_user(current_user.id)
        data = request.get_json()
        quiz = quizzes_repo.get(quiz_id)
        if not quiz:
            return abort(404)

        # Score quiz
        attempt = QuizUtils.score(user, quiz, data)

        # User updates
        user.average_score = ((user.average_score * (user.count_quizzes)) + attempt.score)/(user.count_quizzes + 1)
        user.count_quizzes = user.count_quizzes + 1
        users_repo.save(user)
        quiz_attempts_repo.save(attempt)

        # Commit the changes and return
        response = {
            'results': attempt.get_results(),
            'score': MiscUtils.format_percent(attempt.score)
        }
        transaction.commit()
        return json.dumps(response, ensure_ascii=False)
    except Exception as e:
        transaction.abort()
        return abort(500, str(e))

@app.route('/user/display_name', methods=['POST'])
@login_required
def user_display_name():
    try:
        user = load_user(current_user.id)
        data = request.get_json()

        users_repo.set_display_name(user.id, data['display_name'])

        return json.dumps({'success':True}), 200, {'ContentType':'application/json'} 
    except Exception as e:
        return abort(500, str(e))

@app.route("/about")
def about():
    return render_template('about.html', nav=get_nav(), head=get_head(), foot=get_foot())

@app.route("/links")
def links():
    return render_template('links.html', nav=get_nav(), head=get_head(), foot=get_foot())


# Janky templating ¯\_(ツ)_/¯
def get_nav():
    user_logged_in = (current_user and current_user.is_active)

    profile_styling = f"""<a class="nav-link" href="{BASE_URL}/user/profile">""" if user_logged_in else """<a class="nav-link disabled" href="#" tabindex="-1" aria-disabled="true">"""
    login_logout_link = f"""{BASE_URL}/logout""" if user_logged_in else f"""{BASE_URL}/login""" 
    login_logout_text = "Log Out" if user_logged_in else "Log In"
    login_logout_toast = "Logging Out..." if user_logged_in else "Logging In..."

    return f"""
        <nav class="navbar navbar-expand-lg navbar-light bg-light">
            <div class="container-fluid">
                <a class="navbar-brand" href="{BASE_URL}/">JCE Quiz Portal</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="navbarNav">
                    <ul class="navbar-nav me-auto">
                        <li class="nav-item">
                            <a class="nav-link" href="{BASE_URL}/">Home</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{BASE_URL}/about">About</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{BASE_URL}/links">Links</a>
                        </li>
                    </ul>
                    <ul class="navbar-nav ms-auto">
                        <li class="nav-item">
                            {profile_styling}Profile</a>
                        </li>
                        <li class="nav-item">
                            <a class="btn btn-outline-secondary" href="{login_logout_link}" role="button" onclick="$('#loginToast').toast('show');">{login_logout_text}</a>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>
        <div class="position-fixed bottom-0 end-0 p-3" style="z-index: 11">
            <div class="toast align-items-center bg-secondary fade hide" role="alert" aria-live="assertive" aria-atomic="true" id="loginToast">
                <div class="d-flex">
                    <div class="toast-body">
                        {login_logout_toast}
                    </div>
                    <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        </div>
        """

def get_head():
    return f"""
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="X-UA-Compatible" content="IE=edge">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
        <script src="https://code.jquery.com/jquery-3.7.1.min.js" integrity="sha256-/JqT3SQfawRcv/BIHPThkBvs0OEvtFFmqPF/lYI/Cxo=" crossorigin="anonymous"></script>
        <link rel="stylesheet" type="text/css" href="{url_for('static',filename='index.css')}">
        <title>JCE Class Study Resource Portal</title>
    </head>
    """

def get_foot():
    return """
    <footer>
        <p class="text-center">Copyright &copy; 2024</p>
    </footer>
    """

if __name__ == "__main__":
    app.run(host="127.0.0.1", ssl_context=('adhoc'), port=8080, debug=True)