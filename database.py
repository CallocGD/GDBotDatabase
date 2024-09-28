import base64
import hashlib
import itertools
from contextlib import asynccontextmanager
from hashlib import sha1
from typing import AnyStr, Optional, Union
from urllib.parse import urlparse

import attrs
from sqlalchemy.ext.asyncio import (AsyncEngine, async_sessionmaker,
                                    create_async_engine)
from sqlmodel import Field, Relationship, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


__author__ = "Calloc"
__version__ = "0.0.1"


def cyclic_xor(data:bytes, key:bytes):
    return bytes(d ^ k for d, k in zip(data, itertools.cycle(key)))

def xor_encode(data:bytes, key:bytes):
    return base64.urlsafe_b64encode(cyclic_xor(data, key))


def generate_chk(value:bytes, key:bytes, salt:bytes):
    return xor_encode(hashlib.sha1(value + salt).hexdigest().encode(), key)

# NOTE: Defaults are set for uploadAccComment which is the profile comment, 
# to change the id param should not zero and comment type should be set to "1"
def comment_chk(
    username: str,
    content: str,
    id: Union[str, int] = 0,
    percentage: Union[str, int] = 0,
    comment_type: Union[str, int] = 0,
):
    return generate_chk(f"{username}{content}{id}{percentage}{comment_type}".encode("utf-8"), b"29481", b"xPT6iUrtws0J")


def encode(data:AnyStr):
    return data.encode("utf-8", "strict") if isinstance(data, str) else bytes(data)



def fix_skid_proxy(ip:str):
    """Fixes proxy urls that are written by skids"""
    return f"all://{ip}" if "://" not in ip else ip



def parse_ban(raw_ban_str:str):
    """Attempts to return the user who caused the ban"""
    temp, length , reason = raw_ban_str.split("_", 2)

    # Remove whitespace characters if there's any to foil us...
    reason = reason.rstrip()
    # Check if reason is carrying the user who caused this to occur at the end of the string
    if reason.endswith(")") and reason.rfind("(") != -1:
        user = reason[reason.rfind("(") + 1 :reason.rfind(")")]
        return user 



class IDModel(SQLModel):
    id:Optional[int] = Field(primary_key=True, default=None)

class User(IDModel, table=True):
    """The User Model for a bot account"""
    name:str
    password:bytes
    accountID:int

    bans:list["Ban"] = Relationship(back_populates="user")
    """Possible bans on this account go here. We want this number to be at zero at all costs..."""


    # Most botters aren't using gjp2 but this should give you an advantage against filtering...
    # I would recommend looking into the https endpoints instead of the http endpoints and 
    # Look at the GameLevelManager's code or see it in ghidra.
    @property
    def gjp2(self):
        return sha1(self.password + b"mI29fmAnxgTs").hexdigest()

    def level_comment_chk(self, b64_content:str, levelID:Union[int, str]):
        """Makes a chk for level comment related content"""
        return comment_chk(self.username, b64_content, id=levelID, comment_type=1)

    def profile_comment_chk(self, b64_content:str):
        """Makes a chk for profile comment releated content"""
        return comment_chk(self.username, b64_content, id=0, comment_type=0)

    @property
    def isabstract(self):
        """Determines if we are the owner of this account"""
        return self.password is None and self.accountID is None


class Ban(IDModel, table=True):
    # I would except for each host IP to have a unique ban associated to it and not multiple.
    host:str = Field(unique=True)
    """The host ip the ban has been recieved from"""

    # Comment bans commonly are carrying unknown timeouts sizes as their own range can exceed the size of 
    # 34 days and 22 hours, those can't be calculated without contacting the issuer about the ban 
    # The issuer is commonly unknown however know that it can only be an eldermod or robtop himself 
    # that can do that. My ban for example from heda could be up to the total of a year and we just
    # don't know it yet.
    raw_ban_str:str 

    real_user:Optional[str] = None 
    """The banned user issued in the raw ban string, this may or may not be us."""

    user:Optional[User] = Relationship(back_populates="bans")
    user_id:Optional[int] = Relationship(back_populates="user.id")


@attrs.define
class Database:
    
    name:str = "bots.db"
    engine:AsyncEngine = attrs.field(init=False)
    initalized:bool = attrs.field(init=False, default=False)
    maker:async_sessionmaker[AsyncSession] = attrs.field(init=False)

    def __attrs_post_init__(self):
        self.engine = create_async_engine("aiosqlite+sqlite:///%s" % self.name)
        self.maker = async_sessionmaker(self.engine, class_=AsyncSession)

    async def init_db(self):
        # Prevent repeate initalization on the user's developing end...
        if not self.initalized:
            async with self.maker() as s:
                await s.run_sync(IDModel.metadata.create_all())
                await s.commit()
            self.initalized = True

    @asynccontextmanager
    async def session(self):
        """Issues a new session to the database, you can 
        find more information about what a session does on 
        sqlalchemy or sqlmodel's docs"""
        # Has the database been created yet?
        if not self.initalized:
            await self.init_db()

        async with self.maker() as s:
            yield s


    async def proxy_is_banned(self, proxy:str):
        """Checks if this proxy was banned
        this will return the ban the corresponds 
        to the host that's been banned good for when 
        we need more information such as who the hell 
        caused it

        proxy: the proxy url or IP address of the host to lookup
        
        returns: the user ban if found, None if we're safe to continue"""

        # Incase skid code is being performed...
        proxy = fix_skid_proxy(proxy)

        # I expect the user developer to be using http:// socks4:// socks5:// or all:// in their shit...
        host = urlparse(proxy).hostname
        async with self.session() as s:
            result = await s.exec(select(Ban).where(Ban.host == host))
            ban = result.one_or_none()
        return ban 

    async def new_bot_account(self, username:str, password:str, accountID:int):
        """Registers a new bot account to our database, remeber this should be done after registry completes."""
        async with self.session() as s:
            result = await s.merge(User(name=username, password=password.encode("utf-8"), accountID=accountID))
            await s.commit()
        return result

    async def get_bot(self, username:str):
        """Obtains a bot that is already registered in our database"""
        async with self.session() as s:
            result = await s.exec(select(User).where(User.name == username))
            user = result.one_or_none()
        return user
    
    async def issue_ban(self, ban_str:str, caused_by:User, proxy:str):
        """Issues the comment ban to the user and system so the script 
        will try not hitting it again. This bans the user and other possible casualties"""
        async with self.session() as s:
            await s.merge(
                Ban(
                    host=urlparse(fix_skid_proxy(proxy)).hostname, 
                    raw_ban_str=ban_str, 
                    real_user=parse_ban(ban_str), 
                    user=caused_by)
            )
            await s.commit()
    
    async def user_is_banned(self, username:str):
        """Checks if the user is banned,
        returns a boolean if found on either the username or any issued ban"""

        async with self.session() as s:
            result = await s.exec(select(User).where(User.name == username))
            user = result.one_or_none() 
            # are we carrying any bans with this user?
            if user.bans:
                return True

            result2 = await s.exec(select(Ban).where(Ban.real_user == username))
            
            if result2.one_or_none():
                return True 
        
        # We are 100% safe with using this specific self-bot
        return False 

    async def user_and_proxy_are_banned(self, username:str, proxy:str):
        """Checks to see if the user and proxy are banned,
        if one of these turn up as true then this function returns true as one of 
        these items are not safe to use.
        
        You really should be checking these individually if your goal is to save time in exection vs 
        writing"""

        if await self.proxy_is_banned(proxy):
            return True 
        if await self.user_is_banned(username):
            return True
        # Were safe to use both the proxy and username
        return False 


