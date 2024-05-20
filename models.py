'''
models
defines sql alchemy data models
also contains the definition for the room class used to keep track of socket.io rooms

Just a sidenote, using SQLAlchemy is a pain. If you want to go above and beyond, 
do this whole project in Node.js + Express and use Prisma instead, 
Prisma docs also looks so much better in comparison

or use SQLite, if you're not into fancy ORMs (but be mindful of Injection attacks :) )
'''

from sqlalchemy import String, Table,  Column, Integer, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
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
    ACADEMIC = "academic"
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
    post: Mapped[bool] = mapped_column(Boolean, default=True)  # Added post column
    chat: Mapped[bool] = mapped_column(Boolean, default=True)  # Added chat column


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
class Room(Base):
    __tablename__ = "room"

    room_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_name: Mapped[str] = mapped_column(String, unique=True)
    is_group: Mapped[bool] = mapped_column(Boolean, default=False)
    participants = relationship("Participant", backref="room")
    room_salt: Mapped[str] = mapped_column(String)
        
class Participant(Base):
    __tablename__ = "participant"

    participant_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, ForeignKey('user.username'))
    room_id: Mapped[int] = mapped_column(Integer, ForeignKey('room.room_id'))


class Article(Base):
    __tablename__ = "article"

    article_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[str] = mapped_column(String, ForeignKey('user.username'))
    title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(String)
    date_posted: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    category: Mapped[str] = mapped_column(String)

    # Relationship with Comments table
    comments = relationship("Comment", backref="article")

class Comment(Base):
    __tablename__ = "comment"
 
    comment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(Integer, ForeignKey('article.article_id'))
    author_id: Mapped[str] = mapped_column(String, ForeignKey('user.username'))
    content: Mapped[str] = mapped_column(String)
    date_posted: Mapped[datetime]= mapped_column(DateTime, default=datetime.now)
    
