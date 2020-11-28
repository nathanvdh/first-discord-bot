import aiosqlite
from aiosqlite import Error
import traceback

DB_PATH = "database.db"

async def create_connection():
    """ Create a database connection to a SQLite database """
    conn = None
    try:
        conn = await aiosqlite.connect(DB_PATH)
        return conn
    except Error as e:
        print(e)
    return conn

async def write(sql, values=()):
	conn = await create_connection()
	try:
		await conn.execute(sql, values)
	except Error as e:
		print(e)
	await conn.commit()
	await conn.close()

async def fetchone(sql, values=()):
	conn = await create_connection()
	try:
		cursor = await conn.execute(sql, values)
	except Error as e:
		print(e)
	result = await cursor.fetchone()
	await cursor.close()
	await conn.close()
	if result:
		return result[0]
	else:
		return None

async def fetchall(sql, values=()):
	conn = await create_connection()
	try:
		cursor = await conn.execute(sql, values)
	except Error as e:
		print(e)
	result = await cursor.fetchall()
	await cursor.close()
	await conn.close()
	return result
