'''
app.py contains all of the server application
this is where you'll find all of the get/post request handlers
the socket event handlers are inside of socket_routes.py
'''

from flask import Flask, render_template, request, abort, url_for, session, redirect
from flask_socketio import SocketIO
import db
import secrets


# import logging
 
# this turns off Flask Logging, uncomment this to turn off Logging
# log = logging.getLogger('werkzeug')
# log.setLevel(logging.ERROR)

app = Flask(__name__)

# secret key used to sign the session cookie
app.config['SECRET_KEY'] = secrets.token_hex()
socketio = SocketIO(app)

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
        # Here you can perform any additional logic you need, such as checking if the friend exists, etc.
        return render_template("chat.jinja", username=username, friends=friends)

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

        return render_template("friends.jinja", username=username, friends=friends, requests=requests)


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

if __name__ == '__main__':
    socketio.run(app)
