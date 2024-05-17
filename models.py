'''
models
defines sql alchemy data models
also contains the definition for the room class used to keep track of socket.io rooms

Just a sidenote, using SQLAlchemy is a pain. If you want to go above and beyond, 
do this whole project in Node.js + Express and use Prisma instead, 
Prisma docs also looks so much better in comparison

or use SQLite, if you're not into fancy ORMs (but be mindful of Injection attacks :) )
'''

from sqlalchemy import String, Table,  Column, Integer, ForeignKey, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import Dict
import hashlib
import secrets
from enum import Enum
from datetime import datetime

# data models
class Base(DeclarativeBase):
    pass

association_table = Table('association', Base.metadata,
    Column('user_id', Integer, ForeignKey('user.username')),
    Column('friend_id', Integer, ForeignKey('user.username'))
)

class UserRole(Enum):
    STUDENT = "student"
    STAFF = "staff"
    ADMIN = "admin"

# model to store user information
class User(Base):
    __tablename__ = "user"
    
    # looks complicated but basically means
    # I want a username column of type string,
    # and I want this column to be my primary key
    # then accessing john.username -> will give me some data of type string
    # in other words we've mapped the username Python object property to an SQL column of type String 
    username: Mapped[str] = mapped_column(String, primary_key=True)
    password: Mapped[str] = mapped_column(String)
    salt: Mapped[str] = mapped_column(String)
    online_status: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[str] = mapped_column(String, default=UserRole.STUDENT.value)

    # creation of another table which is related to user in our database
    friends = relationship("User",
                secondary=association_table,
                primaryjoin=username==association_table.c.user_id,
                secondaryjoin=username==association_table.c.friend_id,
                backref="friend_of"
            )
    
    # Field to store pending friend requests
    requests = relationship("FriendRequest", primaryjoin="or_(User.username==FriendRequest.sender_id, User.username==FriendRequest.recipient_id)", backref="recipient")
    
    # Relationship with DecryptionRoomMessages table
    message_decryption_keys = relationship("MessageDecryptionKeys", backref="user")

    def set_password(self, password: str):
        # Generate a salt
        self.salt = secrets.token_hex(16)
        # Hash the password with the salt
        self.password = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), self.salt.encode('utf-8'), 600000)

    def check_password(self, password: str) -> bool:
        # Hash the provided password using the stored salt
        hashed_password = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), self.salt.encode('utf-8'), 600000)
        # Compare the hashed passwords
        return hashed_password == self.password


# Model to represent friend requests
class FriendRequest(Base):
    __tablename__ = "friend_request"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_id: Mapped[str] = mapped_column(String, ForeignKey('user.username'))
    recipient_id: Mapped[str] = mapped_column(String, ForeignKey('user.username'))
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)

# Table to store decryption room messages
class MessageDecryptionKeys(Base):
    __tablename__ = "message_decryption_keys"

    username: Mapped[str] = mapped_column(String, ForeignKey('user.username'), primary_key=True)
    room_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    encrypted_key: Mapped[str] = mapped_column(String)

# Table to store message history
class MessageHistory(Base):
    __tablename__ = "message_history"

    message_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(Integer)
    encrypted_message: Mapped[str] = mapped_column(String)


# stateful counter used to generate the room id
class Counter():
    def __init__(self):
        self.counter = 0
    
    def get(self):
        self.counter += 1
        return self.counter

# Room class, used to keep track of which username is in which room
class Room():
    def __init__(self):
        self.counter = Counter()
        # dictionary that maps the username to the room id
        # for example self.dict["John"] -> gives you the room id of 
        # the room where John is in
        self.dict: Dict[str, int] = {}
        self.salt: Dict[int, str] = {}  # Dictionary to store room-specific salt

    def create_room(self, sender: str, receiver: str) -> int:
        room_id = self.counter.get()
        self.dict[sender] = room_id
        self.dict[receiver] = room_id
        self.salt[room_id] = secrets.token_hex(16)  # Generate and store room-specific salt
        return room_id
    
    def join_room(self,  sender: str, room_id: int) -> int:
        self.dict[sender] = room_id

    def leave_room(self, user):
        if user not in self.dict.keys():
            return
        del self.dict[user]

    # gets the room id from a user
    def get_room_id(self, user: str):
        if user not in self.dict.keys():
            return None
        return self.dict[user]
    
        # gets the room id from a user
    def get_users(self, room_id: int):
        users = []
        for user, id in self.dict.items():
            if int(id) == room_id:
                users.append(user)
        return users
    
    def get_room_salt(self, room_id: int):
        return self.salt.get(room_id)


class Article(Base):
    __tablename__ = "article"

    article_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[str] = mapped_column(String, ForeignKey('user.username'))
    title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(String)
    date_posted: Mapped[datetime] = mapped_column(datetime, default=datetime.now)
    category: Mapped[str] = mapped_column(String)

    # Relationship with Comments table
    comments = relationship("Comment", backref="article")

class Comment(Base):
    __tablename__ = "comment"

    comment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(Integer, ForeignKey('article.article_id'))
    author_id: Mapped[str] = mapped_column(String, ForeignKey('user.username'))
    content: Mapped[str] = mapped_column(String)
    date_posted: Mapped[datetime] = mapped_column(datetime, default=datetime.now)
