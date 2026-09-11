import os
import re
import aiosqlite
import discord
from discord.ext import commands

OWNER_ROLE_ID = 1533463569683845160
CO_OWNER_ROLE_ID = 1533463570564649121
NEW_ROLE_ID = 1533463593201307780
POINTS_ONLY_ROLE_ID = 1533463608145477712

ALLOWED_ROLE_IDS = {OWNER_ROLE_ID, CO_OWNER_ROLE_ID, NEW_ROLE_ID, POINTS_ONLY_ROLE_ID}
RESET_ALLOWED_ROLE_IDS = {CO_OWNER_ROLE_ID, OWNER_ROLE_ID}

ALLOWED_CHANNEL_IDS = {
    1533464111399174287,
    1533463964594340032,
    1533464115446808731,
    1533607940228120707
}

# مسار القرص الدائم المطلق
DB_NAME = "/data/points_bot2.db"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="#", intents=intents, help_command=None)

async def init_db():
    os.makedirs("/data", exist_ok=True)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS points_bot2 (
                user_id TEXT PRIMARY KEY,
                points INTEGER DEFAULT 0
            )
        """)
        await db.commit()

async def get_points(user_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT points FROM points_bot2 WHERE user_id = ?", (str(user_id),)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def set_points(user_id: int, points: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO points_bot2 (user_id, points)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET points = excluded.points
        """, (str(user_id), points))
        await db.commit()

def has_points_permission(member: discord.Member) -> bool:
    return any(role.id in ALLOWED_ROLE_IDS for role in member.roles)

def has_reset_permission(member: discord.Member) -> bool:
    return any(role.id in RESET_ALLOWED_ROLE_IDS for role in member.roles)

@bot.event
async def on_ready():
    await init_db()
    print(f"✅ تم تشغيل reg point بنجاح باسم: {bot.user}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.channel.id not in ALLOWED_CHANNEL_IDS:
        return

    content = message.content.strip()

    if content.startswith("#"):
        await bot.process_commands(message)
        return

    if message.reference:
        try:
            referenced_msg = await message.channel.fetch_message(message.reference.message_id)
            target_member = referenced_msg.author
        except Exception:
            return

        if target_member.bot and (content == "نقاط" or re.search(r"^نقاط\s*[\+\-]\d+$", content)):
            await message.channel.send("❌ لا يمكنك التعامل مع البوتات!")
            return

        if content == "نقاط":
            user_pts = await get_points(target_member.id)
            embed = discord.Embed(
                description=f"⭐ نقاط العضو {target_member.mention}: **{user_pts}**",
                color=discord.Color.purple()
            )
            await message.reply(embed=embed, mention_author=False)
            return

        match = re.search(r"^نقاط\s*([\+\-]\d+)$", content)
        if match:
            if not has_points_permission(message.author):
                await message.reply("❌ ليس لديك صلاحية لتعديل النقاط.", mention_author=False)
                return

            amount = int(match.group(1))
            current_pts = await get_points(target_member.id)
            new_pts = max(0, current_pts + amount)
            await set_points(target_member.id, new_pts)

            color = discord.Color.green() if amount >= 0 else discord.Color.red()
            action_text = f"إضافة **{amount}**" if amount >= 0 else f"خصم **{abs(amount)}**"

            embed = discord.Embed(
                title="✨ تحديث النقاط",
                description=f"✅ تم {action_text} نقطة لـ {target_member.mention}\n⭐ المجموع الحالي: **{new_pts}**",
                color=color
            )
            await message.reply(embed=embed, mention_author=False)
            return

@bot.command(name="مساعدة")
async def help_command(ctx):
    if ctx.channel.id not in ALLOWED_CHANNEL_IDS:
        return
    embed = discord.Embed(
        title="📋 قائمة أوامر reg point",
        description=(
            "**بالرد على العضو:**\n"
            "• `نقاط` ➜ عرض النقاط مع المنشن\n"
            "• `نقاط+5` ➜ إضافة نقاط\n"
            "• `نقاط-2` ➜ خصم نقاط\n\n"
            "**الأوامر العامة (تبدأ بـ #):**\n"
            "• `#قائمة` ➜ قائمة أفضل 10 أعضاء\n"
            "• `#مسح` ➜ تصفير الجميع\n"
            "• `#مسح @العضو` ➜ تصفير عضو معين"
        ),
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)

@bot.command(name="قائمة")
async def top(ctx):
    if ctx.channel.id not in ALLOWED_CHANNEL_IDS:
        return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, points FROM points_bot2 ORDER BY points DESC LIMIT 10") as cursor:
            users = await cursor.fetchall()

    if not users:
        await ctx.send("📭 لا توجد نقاط مسجلة في قاعدة بيانات reg point.")
        return

    description = ""
    for index, (user_id, points) in enumerate(users, start=1):
        member = ctx.guild.get_member(int(user_id))
        mention_name = member.mention if member else f"<@{user_id}>"
        medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"**{index}.**"
        description += f"{medal} {mention_name} — ⭐ **{points}** نقطة\n"

    embed = discord.Embed(title="🏆 قائمة المتصدرين (reg point)", description=description, color=discord.Color.purple())
    await ctx.send(embed=embed)

@bot.command(name="مسح")
async def reset_points(ctx, member: discord.Member = None):
    if ctx.channel.id not in ALLOWED_CHANNEL_IDS:
        return
    if not has_reset_permission(ctx.author):
        await ctx.send("❌ ليس لديك صلاحية لإجراء التصفير.")
        return

    async with aiosqlite.connect(DB_NAME) as db:
        if member:
            await set_points(member.id, 0)
            await ctx.send(f"🔄 تم تصفير نقاط {member.mention} بنجاح!")
        else:
            await db.execute("DELETE FROM points_bot2")
            await db.commit()
            await ctx.send("⚠️ **تم تصفير جميع نقاط reg point بنجاح!**")

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN_BOT2")
    if token:
        bot.run(token)
    else:
        print("❌ لم يتم العثور على DISCORD_TOKEN_BOT2 في البيئة!")
