echo "
import asyncio
import asyncpg
import os

async def run():
    print('🔌 DATABASE_URL =', os.environ.get('DATABASE_URL'))
    try:
        conn = await asyncpg.connect(os.environ['DATABASE_URL'])
        row = await conn.fetchrow('SELECT 1')
        print('✅ DB OK:', row[0])
        await conn.close()
    except Exception as e:
        print('❌ DB ERROR:', e)

asyncio.run(run())
" > check_db.py
