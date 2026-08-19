import discord
from discord.ext import commands, tasks
import asyncio
import random
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

THAI_TZ = ZoneInfo("Asia/Bangkok")

# =========================
# SETTINGS
# =========================

# ตอนทดสอบใช้ 10 วินาที
TIMER_SECONDS = 50 * 60
CUSTOM_MINUTES_MIN = 1
CUSTOM_MINUTES_MAX = 50
REMINDER_DELETE_AFTER = 24 * 60 * 60  # 24 hours

# ตอนใช้งานจริง 50 นาที ให้เปลี่ยนเป็น:
# TIMER_SECONDS = 50 * 60


# ข้อความสุ่มตอน Timer จบ
reminder_messages = [
    "Hope the fan runs are worth it. See you in the Group B Finals.",
    "The run is done, trainer. Akikawa and Tazuna would like to speak with you.",
    "Roses are red, violets are blue, your uma's done and they want you.",
    "Your uma says that you can only keep 10% of the fans, she earned them by herself after all.",
    "Fwuu~! Ywour Uma's twaining is aww done! Pwease give hew lots of headpats~ ♡",
    "Hey {trainer}, you're finally awake, you were trying to farm Fans, right?",
    "Another autorun done. Do you even actually play this game anymore?",
    "มื้อคืนข่อยนอนบ่หลับ เพราะฮู้ว่าเรื่องระหว่างเฮามันจบแล้ว ข่อยบ่เศร้าอีกต่อไปแล้ว เพราะฮู้ว่าเฮาเลิกกันอีหลี",
    "Your uma has finished training. Time for umapyoi",
    "ኃጢ Uma አተኛ ነፍስህ Independent Training ከመዳን በላይ ወይም ሥቃይን Fans አታውቅም",
    "Your trainee is starting to wonder how you even got this job.",
    "Cygames, give this trainer the worst sparks they've ever seen.",
    "Remember to rewards your trainee with a lot of headpats, torena.",
    "Did you forget something? It's probably not important anyways.",
    " F̴͆̑͑̈́i̷̔͌̈́͝n̸͗̂̇̚i̶͋̂͊͊t̶̎́̽͠a̶͕̠̣̚ est,̒̂͠ ̷̈́̀͠inutilis͒̈́ ̷̨̟̏̓m̴̽͝agi̶̓̈́̈̕s̵t̴er.̨͔̰ Sũ̓p̀̋e̶̋r̂̆͒̈́b̴̀̿̋͝i̷sne ̶͊ẗě̶͛͊̀ ̴̈́̓ip̓͒sum̸͐?",
    "Your uma is looking around wondering where you went.",
    "Your uma will remember this.",
    "I-it's not like I care or anything, but your Uma just finished her training... BAKA!",
    "Hey, your autorun is done. That'll be $10.",
    "The parent of your dreams has finished! I hope you like your 1 star guts.",
    "Please come pick up your child."
]


# =========================
# BOT SETUP
# =========================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================
# DATA
# =========================

# Timer ที่กำลังทำงาน
active_timers = {}

# Task ของแต่ละคน
timer_tasks = {}

# ข้อความแจ้งเตือนล่าสุดของแต่ละคน
last_reminder_messages = {}

# ข้อความ Embed หลัก
timer_message = None


# =========================
# CREATE / UPDATE EMBED
# =========================

async def update_timer_embed():

    global timer_message

    if timer_message is None:
        return

    embed = discord.Embed(
        title="🏇 Abandoned Uma Training Overwatch (AUTO)",
        description=(
            "**Start** a timer. "
            "Pretend you're a good trainer. I know what you are. "
"Use Custom for 1-50 minutes."
        )
    )

    now = datetime.now(THAI_TZ)
    lines = []

    sorted_timers = sorted(
        active_timers.values(),
        key=lambda x: x["end_time"]
    )

    for data in sorted_timers:
        user = data["user"]
        end_time = data["end_time"]

        remaining_seconds = max(
            0,
            int((end_time - now).total_seconds())
        )

        if remaining_seconds < 60:
            remaining_text = f"in {remaining_seconds} seconds"
        else:
            minutes = remaining_seconds // 60
            remaining_text = f"in {minutes} minutes"

        end_text = end_time.strftime("%H:%M")

        lines.append(
            f"**{user.display_name}:** "
            f"Timer ends `{end_text}`, {remaining_text}"
        )

    if lines:
        embed.add_field(
            name="Active Trainers",
            value="\n".join(lines),
            inline=False
        )
    else:
        embed.add_field(
            name="Active Trainers",
            value="No active timers.",
            inline=False
        )

    for attempt in range(3):
        try:
            await timer_message.edit(
                embed=embed,
                view=TimerView()
            )
            return

        except discord.NotFound:
            timer_message = None
            return

        except discord.HTTPException as e:
            if e.status >= 500:
                wait_seconds = 2 ** attempt
                print(
                    f"Discord API error {e.status} while editing timer embed. "
                    f"Retrying in {wait_seconds}s ({attempt + 1}/3)."
                )
                await asyncio.sleep(wait_seconds)
                continue
            raise

    print("Could not update timer embed after 3 attempts.")


# =========================
# TIMER
# =========================

async def run_timer(
    user,
    channel,
    end_time
):

    user_id = user.id

    try:
        delay = (
            end_time - datetime.now(THAI_TZ)
        ).total_seconds()

        if delay > 0:
            await asyncio.sleep(delay)

        data = active_timers.get(user_id)

        if data is None:
            return

        if data["end_time"] != end_time:
            return

        message = random.choice(reminder_messages)
        message = message.replace("{trainer}", user.display_name).replace("{Trainer}", user.display_name)

        reminder = None

        # Retry temporary Discord API/server failures.
        for attempt in range(3):
            try:
                reminder = await channel.send(
                    f"{user.mention} {message}",
                    delete_after=REMINDER_DELETE_AFTER
                )
                break

            except discord.HTTPException as e:
                if e.status >= 500:
                    wait_seconds = 2 ** attempt
                    print(
                        f"Discord API error {e.status} while sending reminder. "
                        f"Retrying in {wait_seconds}s ({attempt + 1}/3)."
                    )
                    await asyncio.sleep(wait_seconds)
                    continue
                raise

        if reminder is None:
            print(f"Could not send reminder for {user} after 3 attempts.")
            return

        last_reminder_messages[user_id] = reminder
        active_timers.pop(user_id, None)
        timer_tasks.pop(user_id, None)

        # Do not let an embed-edit failure kill the completed timer task.
        try:
            await update_timer_embed()
        except discord.HTTPException as e:
            print(
                f"Reminder sent, but timer embed update failed for {user}: {e}"
            )

    except asyncio.CancelledError:
        pass

    except discord.HTTPException as e:
        print(f"Discord HTTP error in run_timer for {user}: {e}")

    except Exception as e:
        print(f"Unexpected error in run_timer for {user}: {e}")


# =========================
# START BUTTON
# =========================

async def start_timer_for_minutes(
    interaction: discord.Interaction,
    minutes: int
):
    user = interaction.user
    user_id = user.id

    # ตอบ Discord ก่อน เพื่อไม่ให้ interaction timeout
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    # ถ้ามี Timer เดิม ให้ยกเลิกและเริ่มใหม่
    if user_id in timer_tasks:
        old_task = timer_tasks[user_id]
        old_task.cancel()
        timer_tasks.pop(user_id, None)

    # ถ้ามี Reminder เก่า ให้ลบเมื่อคนเดิมเริ่ม Timer ใหม่
    old_reminder = last_reminder_messages.get(user_id)

    if old_reminder is not None:
        try:
            await old_reminder.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            pass
        except discord.HTTPException as e:
            print(f"Could not delete old reminder for {user}: {e}")

        last_reminder_messages.pop(user_id, None)

    # สร้าง Timer ใหม่
    end_time = datetime.now(THAI_TZ) + timedelta(minutes=minutes)

    active_timers[user_id] = {
        "user": user,
        "end_time": end_time,
        "reminder": None,
        "minutes": minutes
    }

    task = asyncio.create_task(
        run_timer(
            user,
            interaction.channel,
            end_time
        )
    )

    timer_tasks[user_id] = task

    print(
        f"[TIMER START] {user} started/reset a {minutes}-minute timer "
        f"(ends {end_time.strftime('%H:%M:%S')} Asia/Bangkok)"
    )

    await update_timer_embed()


class CustomTimerModal(discord.ui.Modal):

    def __init__(self):
        super().__init__(title="Custom Timer")

        self.minutes_input = discord.ui.TextInput(
            label="Minutes",
            placeholder="Enter 1-50",
            required=True,
            min_length=1,
            max_length=2
        )

        self.add_item(self.minutes_input)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.minutes_input.value.strip()

        if not value.isdigit():
            await interaction.response.send_message(
                "Please enter a whole number from 1 to 50.",
                ephemeral=True
            )
            return

        minutes = int(value)

        if not (CUSTOM_MINUTES_MIN <= minutes <= CUSTOM_MINUTES_MAX):
            await interaction.response.send_message(
                "Custom timer must be between 1 and 50 minutes.",
                ephemeral=True
            )
            return

        await start_timer_for_minutes(interaction, minutes)


class TimerView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Start 50m",
        style=discord.ButtonStyle.green,
        emoji="⏱️",
        custom_id="uma_timer_start_50"
    )
    async def start_timer(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await start_timer_for_minutes(interaction, 50)

    @discord.ui.button(
        label="Custom",
        style=discord.ButtonStyle.secondary,
        emoji="⚙️",
        custom_id="uma_timer_custom"
    )
    async def custom_timer(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(CustomTimerModal())


# =========================
# AUTO REFRESH DISPLAY
# =========================

@tasks.loop(seconds=10)
async def refresh_timer_display():

    if timer_message is not None:

        await update_timer_embed()


# =========================
# BOT START
# =========================

@bot.event
async def on_ready():

    print(
        f"Bot is online as {bot.user}"
    )

    if not refresh_timer_display.is_running():

        refresh_timer_display.start()


@bot.event
async def setup_hook():

    # ทำให้ปุ่มยังฟัง interaction
    # หลัง reconnect / restart
    bot.add_view(
        TimerView()
    )


# =========================
# COMMAND
# =========================

@bot.command()
async def autorun(ctx):

    global timer_message

    embed = discord.Embed(
        title="🏇 Abandoned Uma Training Overwatch (AUTO)",
        description=(
            "**Start** a timer. "
            "Pretend you're a good trainer. I know what you are. "
"Use Custom for 1-50 minutes."
        )
    )

    embed.add_field(
        name="Active Trainers",
        value="No active timers.",
        inline=False
    )

    timer_message = await ctx.send(
        embed=embed,
        view=TimerView()
    )


# =========================
# TOKEN
# =========================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN environment variable is not set")

bot.run(TOKEN)
