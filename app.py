'''
app.py contains all of the server application
this is where you'll find all of the get/post request handlers
the socket event handlers are inside of socket_routes.py
'''

from flask import Flask, render_template, request, abort, url_for, session, redirect
from flask_socketio import SocketIO
import db
import secrets
import ssl
from flask import jsonify


import logging
 
# this turns off Flask Logging, uncomment this to turn off Logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

# secret key used to sign the session cookie
app.config['SECRET_KEY'] = secrets.token_hex()
socketio = SocketIO(app)


# SSL certificate and private key paths
certfile = './certs/localhost.crt'
keyfile = './certs/localhost.key'

# Create an SSL context with the certificate and private key
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain(certfile, keyfile)

# don't remove this!!
import socket_routes

# index page
@app.route("/")
def index():
    return render_template("index.jinja")

# login page
@app.route("/login")
def login():    
    return render_template("login.jinja")

@app.route("/logout")
def logout():    
    username = session.get('username')
    db.change_online_status(username, False)
    session.pop('username', default=None)
    return redirect(url_for('login'))

# handles a post request when the user clicks the log in button
@app.route("/login/user", methods=["POST"])
def login_user():
    if not request.is_json:
        abort(404)

    username = request.json.get("username")
    password = request.json.get("password")
    user =  db.get_user(username)
    if user is None:
        return "Error: User does not exist!"

    if not user.check_password(password):
        return "Error: Password does not match!"

    session['username'] = username  # Store username in session
    db.change_online_status(username, True) # Change user's online status to true

    return url_for('friends', username=request.json.get("username"))

# handles a get request to the signup page
@app.route("/signup")
def signup():
    return render_template("signup.jinja")

# handles a post request when the user clicks the signup button
@app.route("/signup/user", methods=["POST"])
def signup_user():
    if not request.is_json:
        abort(404)
    username = request.json.get("username")
    password = request.json.get("password")

    if db.get_user(username) is None:
        db.insert_user(username, password)
        return url_for('login')
    return "Error: User already exists!"

# handler when a "404" error happens
@app.errorhandler(404)
def page_not_found(_):
    return render_template('404.jinja'), 404

# home page, where the messaging app is
@app.route("/chat")
def chat():
    if request.args.get("username") is None:
        abort(404)
    
    if 'username' not in session:
        # Redirect to login if user is not authenticated
        return redirect(url_for('login'))
    else:
        # Retrieve username from session
        username = session['username']

        # Get the friend's username from the query parameter
        friends = db.get_friends(username)

        # get all group chat rooms available 
        chats = db.get_chat_room_names()

        # get all group chat rooms available 
        user_chats = db.get_user_chatrooms(username)
        
        can_chat = db.get_user(username).chat        

        # Here you can perform any additional logic you need, such as checking if the friend exists, etc.
        return render_template("chat.jinja", username=username, friends=friends, 
                               chats=chats, user_chats=user_chats,
                               can_chat=can_chat)

@app.route("/friends")
def friends():
    if 'username' not in session:
        # Redirect to login if user is not authenticated
        return redirect(url_for('login'))
    else:
        # Retrieve username from session
        username = session['username']
        
        # Get friends for the authenticated user
        friends = db.get_friends(username)
        requests = db.get_requests(username)
        account_type = db.get_user_role(username)
        
        online = []
        for f in friends:
            online.append(db.get_online_status(f))

        return render_template("profile.jinja", username=username, 
                               friends=friends, 
                               requests=requests, account_type=account_type, 
                               online=online)


@app.route("/friends/add", methods=["POST"])
def add_friend():
    if not request.is_json:
        abort(404)
    recipient = request.json.get("recipient")
    username = session.get('username')  # Retrieve username from session

    if db.get_user(recipient) is None or recipient == username:
        return "Error: recipient invalid"
    else:
        if db.send_request(username, recipient) == None:
            return "Error: recipient invalid"
    return url_for('friends')

@app.route("/friends/remove", methods=["POST"])
def remove_friend():
    if not request.is_json:
        abort(404)
    friend = request.json.get("friend")
    username = session.get('username')  # Retrieve username from session

    if db.get_user(friend) is None or friend == username:
        return "Error: recipient invalid"
    else:
        if db.remove_friend(username, friend) == None:
            return "Error: recipient invalid"
        elif db.remove_friend(friend, username) == None:
            return "Error: recipient invalid"
    return url_for('friends')

@app.route("/friends/accept", methods=["POST"])
def accept_friend_request():
    if not request.is_json:
        abort(404)
    sender = request.json.get("sender")
    username = session.get('username')  # Retrieve username from session
    
    db.delete_requests(sender, username)
    db.insert_friend(username, sender)
    db.insert_friend(sender, username)
    return url_for('friends')

@app.route("/friends/decline", methods=["POST"])
def decline_friend_request():
    if not request.is_json:
        abort(404)
    sender = request.json.get("sender")
    username = session.get('username')  # Retrieve username from session

    db.delete_requests(sender, username)
    return url_for('friends')

@app.route("/forum")
def forum():
    if 'username' not in session:
        # Redirect to login if user is not authenticated
        return redirect(url_for('login'))
    username = session.get('username')  # Retrieve username from session
    can_post = db.get_user(username).post
    articles = db.get_all_articles()
    account_type = db.get_user_role(username)

    return render_template("forum.jinja", username=username, can_post=can_post,
                           articles=articles, account_type=account_type)

@app.route("/forum/create")
def create_article():
    if request.args.get("username") is None:
        abort(404)
    
    if 'username' not in session:
        # Redirect to login if user is not authenticated
        return redirect(url_for('login'))
    
    username = session.get('username')  # Retrieve username from session
    return render_template("createArticle.jinja", username=username)

@app.route("/forum/post", methods=["POST"])
def post_article():
    username = session.get('username')  # Retrieve username from session

    # Retrieve the article data from the request
    article_name = request.form.get("fname")
    content = request.form.get("content")
    category = request.form.get("lname")

    db.add_article(username, article_name, content, category)

    return redirect(url_for('forum', username=username))

@app.route("/forum/delete", methods=["POST"])
def delete_article():
    username = session.get('username')  # Retrieve username from session
    article_id = request.json.get("articleId")
    db.delete_article(article_id)
    return url_for('forum', username=username)

@app.route("/forum/update", methods=["POST"])
def update_article():
    username = session.get('username')  # Retrieve username from session
    article_id = request.json.get("articleId")
    new_content = request.json.get("content")
    db.edit_article(article_id, new_content)

    return url_for('forum')

@app.route("/forum/submit")
def submit_comment():
    username = session.get('username')  # Retrieve username from session
    article_id = request.json.get("articleId")
    content = request.json.get("content")

    db.add_comment(article_id, username, content)
    return url_for('forum')

@app.route("/forum/comments")
def get_article_comments():

    article_id = request.args.get("article_id")
    if article_id is None:
        return jsonify({"error": "Article ID is required"}), 400

    # Assuming db.get_comments returns a list of comments for the given article ID
    comments = db.get_comments(article_id)

    return jsonify(comments)

@app.route("/friends/mute", methods=["POST"])
def mute_user():
    user = request.json.get("user")
    db.mute_user_post(user, False)
    return url_for('friends')

@app.route("/friends/unmute", methods=["POST"])
def unmute_user():
    user = request.json.get("user")
    db.mute_user_post(user, True)
    return url_for('friends')


@app.route('/heartbeat')
def heartbeat():
    # Endpoint to indicate server is running
    return 'OK', 200

if __name__ == '__main__':
    if db.get_user("admin") == None:
        db.create_admin_user()
    socketio.run(app, host='127.0.0.1', port=5000, ssl_context=ssl_context)
