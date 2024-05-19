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
import hashlib 
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

# Dictionary to store shared keys by room ID
shared_keys = {}

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

    # if the user is already inside of a room 
    if room_id is not None:
        join_room(int(room_id))
        emit("warnings", (f"{username} has connected", "green"), to=int(room_id))
        
        user = db.get_participants(room_id)
        # checking online status
        online_count = 0
        receiver = None
        for u in user: 
            if (db.get_online_status(u) == True):
                online_count += 1
            if u != username:
                receiver = u

        if online_count == 1:
            emit("warnings", (f"{receiver} is not online. Messages will not be received!", "green"))

        emit("connected", room_id)
        return room_id


# event when client disconnects
# quite unreliable use sparingly
@socketio.on('disconnect')
def disconnect():
    username = request.cookies.get("username")
    room_id = request.cookies.get("room_id")
    if room_id is None or username is None:
        return
        
    emit("warnings", (f"{username} has left the room.", "red"), to=int(room_id))
    leave_room(room_id)

# send message event handler
@socketio.on("send")
def send(username, message, room_id):
    emit("incoming", (f"{username}: {message}"), to=room_id)
    user = db.get_participants(room_id)
    print(user)
    # checking online status
    online_count = 0
    receiver = None
    for u in user: 
        if (db.get_online_status(u) == True):
            online_count += 1
        if u != username:
            receiver = u

    # if the receiver is not online, notify the sender
    if online_count < 2 and receiver != None:
        emit("warnings", (f"{receiver} is not online. Messages will not be received!", "green"))
    
    if len(user) < 2:
        emit("warnings", ("Your the only one in the chat room!", "green"))

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

    room_id = db.find_exclusive_room(sender_name, receiver_name)
    # if the user isn't inside of any room, 
    # perhaps this user has recently left a room
    # or is simply a new user looking to chat with someone

    if (room_id is None):
        if not db.create_room(sender_name, receiver_name, False):
            print("Error: cannot create a room")
            return
        room_id = db.find_exclusive_room(sender_name, receiver_name)
        join_room(room_id)
        # emit to everyone in the room except the sender
        emit("warnings", (f"{sender_name} has joined the room.", "green"), to=room_id, include_self=False)
        # emit only to the sender
        emit("warnings", (f"{sender_name} has joined the room. Now talking to {receiver_name}.", "green"))
    else:
        join_room(room_id)
        emit("warnings", (f"{sender_name} has joined the room.", "green"), to=room_id, include_self=False)
        # emit only to the sender
        emit("warnings", (f"{sender_name} has joined the room. Now talking to {receiver_name}.", "green"))
    

    # if the receiver is not online, notify the sender
    if db.get_online_status(receiver_name) == False and receiver != None:
        emit("warnings", (f"{receiver_name} is not online. Messages will not be received!", "green"))
    
    return int(room_id)

# leave room event handler
@socketio.on("leave")
def leave(username, room_id):
    emit("warnings", (f"{username} has left the room.", "red"), to=room_id)
    leave_room(room_id)
    db.delete_participant(username, room_id)

@socketio.on("ask_receiver_public_key")
def ask_receiver_public_key(room_id):
    # emit to everyone in the room except the sender
    emit("ask_receiver_public_key", (), to=room_id, include_self=False)

@socketio.on("send_receiver_public_key")
def send_receiver_public_key(public_key, room_id):
    # emit to everyone in the room except the sender
    emit("send_receiver_public_key", public_key, to=room_id, include_self=False)

@socketio.on("send_receiver_secret_key")
def send_receiver_secret_key(secretKey, room_id):
    # emit to everyone in the room except the sender
    emit("send_receiver_secret_key", secretKey, to=room_id, include_self=False)

@socketio.on("get_hashed_passwords")
def get_hashed_passwords(sender_name, receiver_name):
    sender_hashed_password = db.get_user(sender_name).password
    receiver_hashed_password = db.get_user(receiver_name).password
    return sender_hashed_password + receiver_hashed_password

@socketio.on("get_room_salt")
def get_room_salt(room_id):
    return room.get_room_salt(room_id)

@socketio.on("store_encrypted_key")
def store_encrypted_key(username, room_id, encryptedKey):
    db.insert_encryption_key(username, room_id, encryptedKey)
    db.get_encryption_key(username, room_id)
    return True

@socketio.on("get_encrypted_key")
def get_encrypted_key(username, room_id):
    db.get_encryption_key(username, room_id)
    return True

@socketio.on("store_encrypted_message")
def store_encrypted_message(room_id, encryptedMessage):
    db.store_encrypted_message(room_id, encryptedMessage)
    return True

@socketio.on("get_encrypted_messages")
def get_encrypted_messages(room_id):
    return db.retrieve_encrypted_messages(room_id)

@socketio.on("send_mac")
def send_mac(mac, room_id):
    emit("send_mac", mac, to=room_id)

@socketio.on("send_combined_key")
def send_combined_key(combined_key, room_id):
    emit("send_combined_key", combined_key, to=room_id, include_self=False)

@socketio.on("request_combined_key")
def request_combined_key(room_id):
    emit("request_combined_key", to=room_id, include_self=False)

@socketio.on("send_encrypt_message")
def send_encrypt_message(mac, room_id):
    emit("send_mac", mac, to=room_id)