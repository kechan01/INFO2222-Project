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

# gets user's list of friends's usernames
def get_friends(username: str):
    with Session(engine) as session:
        user = session.get(User, username)
        friends = []
        for f in user.friends:
            friends.append(f.username)
        return friends

def send_request(username: str, recipient: str):
    with Session(engine) as session:
        # Check if the sender and recipient exist in the database
        sender = session.get(User, username)
        receiver = session.get(User, recipient)

        if sender == receiver:
            print(f"Error: cannot send to yourself.")
            return

        if sender is None:
            print(f"Error: Sender '{username}' does not exist.")
            return
        
        if receiver is None:
            print(f"Error: Recipient '{recipient}' does not exist.")
            return
        
        # Check if the sender and recipient are already friends
        if receiver in sender.friends:
            print(f"Error: '{username}' and '{recipient}' are already friends.")
            return
        
        # Check if there's already a pending request between these users
        existing_request = session.query(FriendRequest).filter_by(sender_id=sender.username, recipient_id=receiver.username).first()
        if existing_request:
            print("Error: There is already a pending request between these users.")
            return
        
        # Create a new friend request
        new_request = FriendRequest(sender_id=username, recipient_id=recipient)
        session.add(new_request)
        session.commit()
        print(f"Friend request sent from '{username}' to '{recipient}'.")
        return True

def get_requests(username: str):
    with Session(engine) as session:
        # Query all pending friend requests where the recipient is the specified user
        requests = session.query(FriendRequest).filter_by(recipient_id=username, accepted=False).all()
        
        if not requests:
            print(f"No pending friend requests for user '{username}'.")
            return []
        
        # Extract sender usernames from the requests
        sender_usernames = [request.sender_id for request in requests]
        return sender_usernames

def delete_requests(username: str, recipient: str):
    with Session(engine) as session:
        # Query all pending friend requests where the recipient is the specified user
        requests = session.query(FriendRequest).filter_by(sender_id=username, recipient_id=recipient).all()
        
        if not requests:
            print(f"Could not find the friend request to delete")
            return []
        
        for request in requests:
            session.delete(request)
        
        session.commit()
        print(f"Friend requests from '{username}' to '{recipient}' deleted.")


# def insert_test(username: str):
#     with Session(engine) as session:
#         friend = User(username="test", password="test")
#         session.add(friend)
#         user = session.get(User, username)
#         user.friends.append(friend)
#         session.commit()
