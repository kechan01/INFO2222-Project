'''
socket_routes
file containing all the routes related to socket.io
'''


from flask_socketio import join_room, emit, leave_room, SocketIO, rooms
from flask import request

try:
    from __main__ import socketio
except ImportError:
    from app import socketio

from models import Room

import db

room = Room()
online_users = {}

# when the client connects to a socket
# this event is emitted when the io() function is called in JS
@socketio.on('connect')
def connect():
    username = request.cookies.get("username")
    room_id = request.cookies.get("room_id")
    if room_id is None or username is None:
        return
    # socket automatically leaves a room on client disconnect
    # so on client connect, the room needs to be rejoined
    online_users[username] = request.sid

    # if the user is already inside of a room 
    if room_id is not None:
        room.join_room(username, room_id)
        join_room(int(room_id))
        user = room.get_users(room_id)
        emit("incoming", (f"{username} has connected", "green"), to=int(room_id))
        if len(user) == 1:
            emit("incoming", ("Receiver is not online. Messages will not be received!", "green"))

        return room_id


# event when client disconnects
# quite unreliable use sparingly
@socketio.on('disconnect')
def disconnect():
    username = request.cookies.get("username")
    room_id = request.cookies.get("room_id")
    if room_id is None or username is None:
        return
    
    if username in online_users:
        del online_users[username]  # Remove the user from the online list
    
    emit("incoming", (f"{username} has left the room.", "red"), to=int(room_id))
    leave_room(room_id)
    room.leave_room(username)


def is_user_online(username):
    return username in online_users

# send message event handler
@socketio.on("send")
def send(username, message, room_id):
    emit("incoming", (f"{username}: {message}"), to=room_id)
    user = room.get_users(room_id)
    if len(user) == 1:
        emit("incoming", ("Receiver is not online. Messages will not be received!", "green"))

    
# join room event handler
# sent when the user joins a room
@socketio.on("join")
def join(sender_name, receiver_name):
    receiver = db.get_user(receiver_name)
    if receiver is None:
        return "Unknown receiver!"
    
    sender = db.get_user(sender_name)
    if sender is None:
        return "Unknown sender!"

    room_id = room.get_room_id(receiver_name)
    online_users[sender_name] = request.sid

    # if the user is already inside of a room 
    if room_id is not None:
        room.join_room(sender_name, room_id)
        join_room(room_id)

        # emit to everyone in the room except the sender
        emit("incoming", (f"{sender_name} has joined the room.", "green"), to=room_id, include_self=False)
        # emit only to the sender
        emit("incoming", (f"{sender_name} has joined the room. Now talking to {receiver_name}.", "green"))
        print("INNNN")
        return int(room_id)

    # if the user isn't inside of any room, 
    # perhaps this user has recently left a room
    # or is simply a new user looking to chat with someone
    room_id = room.create_room(sender_name, receiver_name)
    join_room(room_id)

    emit("incoming", (f"{sender_name} has joined the room. Now talking to {receiver_name}.", "green"), to=room_id)

    if not receiver_name in online_users:
        emit("incoming", (f"{receiver_name} is not online. Messages will not be received!", "green"))

    return room_id

# leave room event handler
@socketio.on("leave")
def leave(username, room_id):
    emit("incoming", (f"{username} has left the room.", "red"), to=room_id)
    leave_room(room_id)
    room.leave_room(username)

def find_receiver(username, room_id):
    users_in_room = rooms(room_id)

    for user in users_in_room:
        if username != user:
            return username

    return