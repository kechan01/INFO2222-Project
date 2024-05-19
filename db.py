'''
db
database file, containing all the logic to interface with the sql database
'''

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session
from models import *

from pathlib import Path
import atexit
import hashlib
import secrets


# creates the database directory
Path("database") \
    .mkdir(exist_ok=True)

# "database/main.db" specifies the database file
# change it if you wish
# turn echo = True to display the sql output
engine = create_engine("sqlite:///database/main.db", echo=False)

# initializes the database
Base.metadata.create_all(engine)

def create_admin_user():
    with Session(engine) as session:
        default_user = User(
            username="admin",  # Specify the username
            role=UserRole.ADMIN.value,  # Specify the role
            online_status=False  # Specify the online status
        )
        password = "admin"
        password_bytes = password.encode('utf-8')
    
        # Compute the SHA-256 hash
        hashed_password = hashlib.sha256(password_bytes).hexdigest()

        default_user.set_password(hashed_password)
        session.add(default_user)
        session.commit()

# inserts a user to the database
def insert_user(username: str, password: str):
    with Session(engine) as session:
        user = User(username=username)
        user.set_password(password)
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

# sends a friend request from one user to another    
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


def insert_encryption_key(username: str, room_id: int, encrypted_key: str):
    with Session(engine) as session:
        try:
            # Check if the combination of username and room_id already exists in the table
            existing_key = session.query(MessageDecryptionKeys).filter_by(username=username, room_id=room_id).first()

            if existing_key:
                # If the combination already exists, update the encrypted key
                existing_key.encrypted_key = encrypted_key
            else:
                # If the combination doesn't exist, create a new entry
                new_key = MessageDecryptionKeys(username=username, room_id=room_id, encrypted_key=encrypted_key)
                session.add(new_key)
            
            # Commit the changes to the database
            session.commit()
            return True  # Return True to indicate successful insertion/update
        except Exception as e:
            # Handle any exceptions
            session.rollback()  # Rollback the transaction
            print(f"Error occurred: {e}")
            return False  # Return False to indicate failure

def get_encryption_key(username: str, room_id: int):
    # Create a session
    with Session(engine) as session:
        try:
            # Query the MessageDecryptionKeys table for the encryption key
            encryption_key = session.query(MessageDecryptionKeys).filter_by(username=username, room_id=room_id).first()

            if encryption_key:
                # If an encryption key is found, return it
                return encryption_key.encrypted_key
            else:
                # If no encryption key is found, return None
                return None
        except Exception as e:
            # Handle any exceptions
            print(f"Error occurred: {e}")
            return None  # Return None to indicate failure

def store_encrypted_message(room_id: int, encrypted_message: str):
    with Session(engine) as session:
        try:
            # Create a new MessageHistory object and add it to the session
            new_message = MessageHistory(room_id=room_id, encrypted_message=encrypted_message)
            session.add(new_message)
            session.commit()
            return True  # Return True to indicate successful insertion
        except Exception as e:
            # Handle any exceptions
            session.rollback()  # Rollback the transaction
            print(f"Error occurred: {e}")
            return False  # Return False to indicate failure

def retrieve_encrypted_messages(room_id: int):
    with Session(engine) as session:
        try:
            # Query the MessageHistory table for encrypted messages ordered by message ID in ascending order
            messages = session.query(MessageHistory).filter_by(room_id=room_id).order_by(MessageHistory.message_id.asc()).all()
            return [message.encrypted_message for message in messages]
        except Exception as e:
            # Handle any exceptions
            print(f"Error occurred: {e}")
            return None  # Return None to indicate failure

def create_room(username: str, receiver: str, group: bool):
    with Session(engine) as session:
        try:
            user = session.get(User, username)
            if user is None:
                print(f"Error: User '{username}' does not exist.")
                return

            if (not group):
                user2 = session.get(User, receiver)
                
                if user2 is None and not group:
                    print(f"Error: receiver '{receiver}' does not exist.")
                    return

                # Create a new Room object
                new_room = Room(room_name=(username+receiver))
            else:
                new_room = Room(room_name=receiver)
                new_room.is_group = True

            new_room.room_salt = secrets.token_hex(16)                

            session.add(new_room)
            session.commit()
            print("Room created successfully.")
            add_participant(username, new_room.room_id)

            if (not group):
                add_participant(receiver, new_room.room_id)
            return True
        except Exception as e:
            session.rollback()
            print("An error occurred while creating the room:", e)
            return None

def get_room_id_by_name(room_name: str):
    with Session(engine) as session:
        try:
            # Query the Room object by room_name
            room = session.query(Room).filter_by(room_name=room_name).first()
            if room:
                # Return the room_id if the room is found
                return room.room_id
            else:
                print(f"Room with name '{room_name}' not found.")
                return None
        except Exception as e:
            print("An error occurred while retrieving room_id by room_name:", e)
            return None

def get_chat_room_names():
    with Session(engine) as session:
        try:
            # Query all room names
            room_names = session.query(Room.room_name).all()
            # Extract the room names from the query result
            return [name[0] for name in room_names]
        except Exception as e:
            print("An error occurred while retrieving chat room names:", e)
            return None

def add_participant(username: str, room_id: int):
    # Assuming 'username' is the username of the participant
    with Session(engine) as session:
        # Query the User object by username
        user = session.get(User, username)
        room = session.get(Room, room_id)
        if user and room:
            # Add the user to the list of participants in the room
            participant = Participant(username=username, room_id=room_id)
            session.add(participant)
            session.commit()
            print(f"Participant '{username}' added to room '{room.room_name}'.")
        else:
            print(f"User or room not found.")

def delete_participant(username: str, room_id: int):
    with Session(engine) as session:
        try:
            # Query the Room object by room_id
            room = session.query(Room).filter_by(room_id=room_id).first()
            if room:
                # Query the User object by username
                user = session.query(User).filter_by(username=username).first()
                if user:
                    # Check if the user is a participant in the room
                    if user in room.participants:
                        # Remove the user from the list of participants
                        room.participants.remove(user)
                        session.commit()
                        print(f"Participant '{username}' deleted from room ID {room_id}.")
                        return True
                    else:
                        print(f"Participant '{username}' is not in room ID {room_id}.")
                        return False
                else:
                    print(f"User '{username}' not found.")
                    return False
            else:
                print("Room not found.")
                return False
        except Exception as e:
            session.rollback()
            print("An error occurred while deleting participant:", e)
            return False
        
def get_participants(room_id: int):
    with Session(engine) as session:
        try:
            # Query the Room object by room_id
            room = session.query(Room).filter_by(room_id=room_id).first()
            if room:
                # Return the list of participants' usernames
                return [participant.username for participant in room.participants]
            else:
                print("Room not found.")
                return None
        except Exception as e:
            print("An error occurred while retrieving participants:", e)
            return None

def find_exclusive_room(user1: str, user2: str):
    with Session(engine) as session:
        try:
            # Subquery to get the room IDs where both users are participants
            subquery = (
                session.query(Participant.room_id)
                .filter(Participant.username.in_([user1, user2]))
                .group_by(Participant.room_id)
                .having(func.count(Participant.room_id) == 2)
                .subquery()
            )

            # Query rooms where only the two specified users are participants
            rooms = (
                session.query(Room)
                .join(subquery, Room.room_id == subquery.c.room_id)
                .filter(Room.is_group == False)
                .all()
            )
            
            if rooms:
                return rooms[0].room_id  # Return the first exclusive room found
            else:
                print(f"No exclusive room found for users '{user1}' and '{user2}'.")
                return None
        except Exception as e:
            print("An error occurred while finding an exclusive room:", e)
            return None

def change_online_status(username: str, new_status: bool):
    with Session(engine) as session:
        try:
            user = session.query(User).filter_by(username=username).first()
            if user:
                user.online_status = new_status
                session.commit()
                print(f"User '{username}' online status updated to {new_status}")
            else:
                print(f"User '{username}' not found.")
        except Exception as e:
            print("An error occurred:", e)


def get_online_status(username: str):
    with Session(engine) as session:
        try:
            user = session.query(User).filter_by(username=username).first()
            if user:
                return user.online_status
            else:
                print(f"User '{username}' not found.")
                return None
        except Exception as e:
            print("An error occurred:", e)
            return None

def set_all_users_offline():
    with Session(engine) as session:
        try:
            # Update the online status of all users to False
            session.query(User).update({User.online_status: False})
            session.commit()
            print("All users set to offline.")
        except Exception as e:
            session.rollback()
            print("An error occurred while setting all users offline:", e)

def add_article(author_username: str, title: str, content: str, category: str):
    with Session(engine) as session:
        try:
            # Create a new Article object
            new_article = Article(author_id=author_username, title=title, content=content, category=category)
            session.add(new_article)
            session.commit()
            print("Article added successfully.")
            return True
        except Exception as e:
            session.rollback()
            print("An error occurred while adding the article:", e)
            return False

def delete_article(article_id: int):
    with Session(engine) as session:
        try:
            # Query the Article object to be deleted
            article_to_delete = session.query(Article).filter_by(article_id=article_id).first()
            if article_to_delete:
                session.delete(article_to_delete)
                session.commit()
                print("Article deleted successfully.")
                return True
            else:
                print("Article not found.")
                return False
        except Exception as e:
            session.rollback()
            print("An error occurred while deleting the article:", e)
            return False

def edit_article(article_id: int, new_title: str, new_content: str, new_category: str):
    with Session(engine) as session:
        try:
            # Query the Article object to be edited
            article_to_edit = session.query(Article).filter_by(article_id=article_id).first()
            if article_to_edit:
                # Update the article attributes
                article_to_edit.title = new_title
                article_to_edit.content = new_content
                article_to_edit.category = new_category
                session.commit()
                print("Article edited successfully.")
                return True
            else:
                print("Article not found.")
                return False
        except Exception as e:
            session.rollback()
            print("An error occurred while editing the article:", e)
            return False

def get_article(article_id: int):
    with Session(engine) as session:
        try:
            # Query the Article object by its ID
            article = session.query(Article).filter_by(article_id=article_id).first()
            if article:
                # Return the article object
                return article
            else:
                print("Article not found.")
                return None
        except Exception as e:
            print("An error occurred while retrieving the article:", e)
            return None
        
def get_article_by_name(title: str):
    with Session(engine) as session:
        try:
            # Query the Article object by its title
            article = session.query(Article).filter_by(title=title).first()
            if article:
                # Return the article object
                return article
            else:
                print("Article not found.")
                return None
        except Exception as e:
            print("An error occurred while retrieving the article:", e)
            return None

def get_articles_by_category(category: str):
    with Session(engine) as session:
        try:
            # Query articles by category
            articles = session.query(Article).filter_by(category=category).all()
            return articles
        except Exception as e:
            print("An error occurred while retrieving articles by category:", e)
            return None


def get_comments(article_id: int):
    with Session(engine) as session:
        try:
            # Query all comments associated with the specified article
            comments = session.query(Comment).filter_by(article_id=article_id).all()
            return comments
        except Exception as e:
            print("An error occurred while retrieving comments:", e)
            return None

def delete_comment(comment_id: int):
    with Session(engine) as session:
        try:
            # Query the Comment object to be deleted
            comment_to_delete = session.query(Comment).filter_by(comment_id=comment_id).first()
            if comment_to_delete:
                session.delete(comment_to_delete)
                session.commit()
                print("Comment deleted successfully.")
                return True
            else:
                print("Comment not found.")
                return False
        except Exception as e:
            session.rollback()
            print("An error occurred while deleting the comment:", e)
            return False

def change_user_role(username: str, new_role: str):
    with Session(engine) as session:
        try:
            # Query the user object to be updated
            user_to_update = session.query(User).filter_by(username=username).first()
            if user_to_update:
                # Update the user's role
                user_to_update.role = new_role
                session.commit()
                print(f"User '{username}' role updated to '{new_role}'.")
                return True
            else:
                print("User not found.")
                return False
        except Exception as e:
            session.rollback()
            print("An error occurred while changing the user's role:", e)
            return False

def get_user_role(username: str):
    with Session(engine) as session:
        try:
            # Query the user object by username
            user = session.query(User).filter_by(username=username).first()
            if user:
                # Return the user's role
                return user.role
            else:
                print("User not found.")
                return None
        except Exception as e:
            print("An error occurred while retrieving the user's role:", e)
            return None

# Register the set_all_users_offline function to be called when the script exits
atexit.register(set_all_users_offline)
