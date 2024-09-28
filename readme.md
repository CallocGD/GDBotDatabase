# Geometry Dash bot Database

A Simple Database script made with SQLModel/sqlalchemy for controlling a very big problem with modern gd bots.


## The Problem.

- Bots are Repeatedly hitting banned proxies (This happend to me before with one of An0bot's bans). This is one of the many reasons why I made this database.
This filters out the bad proxies for ones that can still send comments with. This database
is made to help you eliminate bad users and proxies from your list one by one and it allows you to keep track of your bot amry 
and if your accounts have been depleted or not. 2024 calls for smarter techniques and this tool is no exception as stricter
methods are needed to be enforced in order to prevent the wasting of your delequate resources and time.

## Code Example
I would high recommend you read my python script provided for more functions and details I made sure many things were packaged
however please use asyncio. python's Requests library is shit and slow. `aiohttp` and `httpx` are recommended replacements that are asyncio-friendly. **I hate seeing code with nothing but requests and threading. The skiddiness shows and the effort givien is lazy and so does it's retarded nature and waste of resources.**

```python

from database import Database

db = Database("my-gdbot-database.db")

# We've just barely scratched the surface here. There's many more functions packed inside the Database class alone that you can use.

async def on_account_registered(name:str, password:str, accountID:int):
    await db.new_bot_account(name, password, accountID)

```

## Eldermods
I am not responsible for any damages caused by this code. You can blame the countless people who have admitted to how much they love my code and shit I produce.



