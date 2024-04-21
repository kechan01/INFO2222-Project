'''
socket_routes
file containing all the routes related to socket.io
'''
from models import EncryptedMessage
from cryptography.hazmat.primitives import serialization
from flask_socketio import join_room, emit, leave_room, SocketIO, rooms, emit
from flask import request

#imports for encryption 
from flask import Flask, render_template, request, abort, url_for, session, redirect
from cryptography.hazmat.primitives.asymmetric import dh

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

try:
    from __main__ import socketio
except ImportError:
    from app import socketio

from models import Room

import db

room = Room()
online_users = {}

# Diffie-Hellman parameters
parameters = dh.generate_parameters(generator=2, key_size=2048)
private_key = parameters.generate_private_key()
public_key = private_key.public_key()

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
        join_room(int(room_id))
        user = room.get_users(int(room_id))
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

def is_user_online(username):
    return username in online_users

# send message event handler
@socketio.on("send")
def send(username, message, room_id):
    # Retrieve shared key from the database for the recipient
    shared_key = db.get_shared_key(username)
    
    if shared_key:
        # Encrypt the message using the shared key
        encrypted_message = encrypt_message(message.encode(), shared_key)
            # Store the encrypted message in the database
        encrypted_message_obj = EncryptedMessage(
            sender_id=username,
            encrypted_message=encrypted_message,
            room_id=room_id
        )
        db.session.add(encrypted_message_obj)
        db.session.commit()
        # Emit the encrypted message
        emit("encrypted_message", {"sender_username": username, "encrypted_message": encrypted_message}, to=room_id)
        
        # Check if the recipient is online
        user = room.get_users(int(room_id))
        receiver = None
        
        for u in user:
            if u != username:
                receiver = u
        
        if len(user) == 2 and receiver not in online_users:
            emit("incoming", (f"{receiver} is not online. Messages will not be received!", "green"), to=room_id)
    else:
        emit("incoming", ("Error: Shared key not found for recipient!", "red"))

@socketio.on("receive")
def receive(data):
    # Extract sender's username and encrypted message from the received data
    sender_username = data.get("sender_username")
    encrypted_message = data.get("encrypted_message")
    
    # Retrieve shared key for the sender
    shared_key = db.get_shared_key(sender_username)
    
    if shared_key:
        # Decrypt the message using the shared key
        decrypted_message = decrypt_message(encrypted_message, shared_key)
        
        # Emit the decrypted message
        emit("incoming", (f"{sender_username}: {decrypted_message}"))
    else:
        emit("incoming", ("Error: Shared key not found for sender!", "red"))
    
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

         # Perform key exchange here
        start_dh_exchange(sender_name, receiver_name)

        # emit to everyone in the room except the sender
        emit("incoming", (f"{sender_name} has joined the room.", "green"), to=room_id, include_self=False)
        # emit only to the sender
        emit("incoming", (f"{sender_name} has joined the room. Now talking to {receiver_name}.", "green"))
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
    if username in online_users:
        del online_users[username]  # Remove the user from the online list

    emit("incoming", (f"{username} has left the room.", "red"), to=room_id)
    leave_room(room_id)
    room.leave_room(username)

def find_receiver(username, room_id):
    users_in_room = rooms(room_id)

    for user in users_in_room:
        if username != user:
            return username

    return


#function to exchange the public_private key for encryption
def start_dh_exchange(data):

    sender_username = data['sender_username']
    recipient_username = data['recipient_username']
    
    # Retrieve public keys from the database for both sender and recipient
    sender_public_key_pem = db.get_public_key(sender_username)
    recipient_public_key_pem = db.get_public_key(recipient_username)
    
    if sender_public_key_pem and recipient_public_key_pem:
        # Load public keys from PEM format
        sender_public_key = serialization.load_pem_public_key(sender_public_key_pem)
        recipient_public_key = serialization.load_pem_public_key(recipient_public_key_pem)
        
        # Generate private key for the server
        server_private_key = dh.generate_private_key()
        
        # Perform key exchange between sender and server
        shared_key1 = server_private_key.exchange(sender_public_key)
        
        # Perform key exchange between recipient and server
        shared_key2 = server_private_key.exchange(recipient_public_key)
        
        # Store shared keys in the database
        db.store_shared_key(shared_key1, sender_username)
        db.store_shared_key(shared_key2, recipient_username)
        
        # Emit event to notify clients that shared keys are ready
        emit('shared_key_ready', to=sender_username)
        emit('shared_key_ready', to=recipient_username)

# Function to encrypt a message
def encrypt_message(message, shared_key):
    # Generate a random initialization vector (IV)
    iv = os.urandom(16)

    # Pad the message to ensure it's a multiple of the block size
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_message = padder.update(message) + padder.finalize()

    # Create a cipher object using AES in CBC mode with the shared key and IV
    cipher = Cipher(algorithms.AES(shared_key), modes.CBC(iv))
    encryptor = cipher.encryptor()

    # Encrypt the padded message
    ciphertext = encryptor.update(padded_message) + encryptor.finalize()

    # Return the IV and ciphertext
    return iv + ciphertext

# Function to decrypt a message
def decrypt_message(encrypted_message, shared_key):
    # Extract the IV from the encrypted message
    iv = encrypted_message[:16]

    # Extract the ciphertext from the encrypted message
    ciphertext = encrypted_message[16:]

    # Create a cipher object using AES in CBC mode with the shared key and IV
    cipher = Cipher(algorithms.AES(shared_key), modes.CBC(iv))
    decryptor = cipher.decryptor()

    # Decrypt the ciphertext
    padded_message = decryptor.update(ciphertext) + decryptor.finalize()

    # Unpad the decrypted message
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    message = unpadder.update(padded_message) + unpadder.finalize()

    # Return the decrypted message
    return message
