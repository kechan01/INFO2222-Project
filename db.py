'''
db
database file, containing all the logic to interface with the sql database
'''

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models import *

from pathlib import Path

# creates the database directory
Path("database") \
    .mkdir(exist_ok=True)

# "database/main.db" specifies the database file
# change it if you wish
# turn echo = True to display the sql output
engine = create_engine("sqlite:///database/main.db", echo=False)

# initializes the database
Base.metadata.create_all(engine)

# inserts a user to the database
def insert_user(username: str, password: str):
    with Session(engine) as session:
        user = User(username=username, password=password)
        session.add(user)
        session.commit()

# gets a user from the database
def get_user(username: str):
    with Session(engine) as session:
        return session.get(User, username)
    
# gets user's list of friends
def insert_friend(username: str, friend: str):
    with Session(engine) as session:
        user = session.get(User, username)
        new_friend = session.get(User, friend)
        user.friends.append(new_friend)
        session.commit()

# def insert_test(username: str):
#     with Session(engine) as session:
#         friend = User(username="test", password="test")
#         session.add(friend)
#         user = session.get(User, username)
#         user.friends.append(friend)
#         session.commit()

# gets user's list of friends's usernames
def get_friends(username: str):
    with Session(engine) as session:
        user = session.get(User, username)
        friends = []
        for f in user.friends:
            friends.append(f.username)
        return friends


# sends a friend request from one user to another
def send_friend_request(sender: str, receiver: str):
    with Session(engine) as session:
        sender_user = session.get(User, sender)
        receiver_user = session.get(User, receiver)
        
        if sender_user is None or receiver_user is None:
            return False, "User not found."
        
        # Check if they are already friends
        if receiver_user in sender_user.friends:
            return False, "You are already friends with this user."

        sender_user.friends.append(receiver_user)
        session.commit()
        return True, "Friend request sent successfully."