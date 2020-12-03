import aiosqlite
from aiosqlite import Error
import traceback

DB_PATH = "database.db"
BUILD_PATH = "build.sql"

async def create_connection():
    """ Create a database connection to a SQLite database """
    conn = None
    try:
        conn = await aiosqlite.connect(DB_PATH)
        await conn.execute("PRAGMA foreign_keys = 1")
        return conn
    except Error as e:
        print(e)
    return conn

async def build():
	conn = await create_connection()
	with open(BUILD_PATH, "r", encoding="utf-8") as script:
		try: 
			await conn.executescript(script.read())
		except Error as e:
			print(e)

async def write(sql, values=()):
	conn = await create_connection()
	try:
		result = await conn.execute(sql, values)
	except Error as e:
		print(e)
	await conn.commit()
	await conn.close()
	return result

async def writescript(sql):
	conn = await create_connection()
	try:
		await conn.executescript(sql)
	except Error as e:
		print(e)
	await conn.commit()
	await conn.close()

async def write_multi_row(sql, rows_list):
	conn = await create_connection()
	try:
		await conn.executemany(sql, rows_list)
	except Error as e:
		print(e)
	await conn.commit()
	await conn.close()

async def fetchfield(sql, values=()):
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
	return result

async def fetchrow(sql, values=()):
	conn = await create_connection()
	try:
		cursor = await conn.execute(sql, values)
	except Error as e:
		print(e)
	result = await cursor.fetchone()
	await cursor.close()
	await conn.close()
	return result

async def fetchcolumn(sql, values=()):
	conn = await create_connection()
	try:
		cursor = await conn.execute(sql, values)
	except Error as e:
		print(e)
		return
	result = await cursor.fetchall()
	await cursor.close()
	await conn.close()
	return [row[0] for row in result]


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