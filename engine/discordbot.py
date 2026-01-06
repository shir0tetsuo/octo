import engine.security
import engine.ratelimits
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("discordbot")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
TREE = bot.tree

ROOT_DIR = Path(__file__).parent
PAGE_SIZE = 25  # Discord select menu max options per select

KEY_FILE = Path("key.json")

@TREE.command(
    name="create_api_key",
    description="Create a new Octo API key (sent to you via DM)"
)
async def create_api_key(
    interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    discord_id = interaction.user.id

    if (not engine.ratelimits.within_discord_rate_limit(discord_id)):
        dm = await interaction.user.create_dm()
        await dm.send(
            f"🔑 **Rate-limit exceeded.**\n\n"
        )
        return

    tokendata = [
        f"user:{discord_id}",
        f"isLevel1",
    ]

    try:
        # Create key
        api_key_bytes = engine.security.create_api_key(
            *tokendata,
            key_storage_file=KEY_FILE,
        )
        api_key = api_key_bytes.decode()

        # Decrypt to inspect metadata
        decrypted = engine.security.decrypt_api_key(
            api_key,
            key_storage_file=KEY_FILE,
        )


        MAX_KEY_AGE_DAYS = 365 

        # ---- Expiry handling (adjust if needed) ----
        issued_at = datetime.now(timezone.utc) - timedelta(days=decrypted.days_old)

        if not decrypted.decryption_success:
            raise RuntimeError("Failed to decrypt newly created API key")

        now = datetime.now(timezone.utc)

        issued_at = now - timedelta(days=decrypted.days_old)
        expires_at = issued_at + timedelta(days=MAX_KEY_AGE_DAYS)

        expires_unix = int(expires_at.timestamp())

        log.info(f'New key generated for {discord_id}')

        # ---- DM the user ----
        dm = await interaction.user.create_dm()
        await dm.send(
            f"🔑 **Your X-API-Key**\n\n"
            f"```\n{api_key}\n```\n"
            f"**Expires:** <t:{expires_unix}:F> (<t:{expires_unix}:R>)\n"
            f"[Login to Online Cartographer Tool/Observatory](https://shir0tetsuo.github.io/octo/login.html)"
        )

        await interaction.followup.send(
            "✅ Your API key has been created and sent to you via DM.",
            ephemeral=True,
        )

    except discord.Forbidden:
        await interaction.followup.send(
            "❌ I couldn’t DM you. Please enable DMs from server members and try again.",
            ephemeral=True,
        )

    except Exception:
        log.exception("Failed to create API key")
        await interaction.followup.send(
            "❌ Failed to create API key. Please contact an administrator.",
            ephemeral=True,
        )




# ---------- Tree sync and ready ----------
@bot.event
async def on_ready():
    log.info("Bot ready. Logged in as %s (%s)", bot.user, getattr(bot.user, "id", None))
    try:
        synced = await TREE.sync()
        # Put the bot online 
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Game("with fire.") 
        )
        log.info("Application commands synced. Count: %s", len(synced))
    except Exception:
        log.exception("Failed to sync application commands")

# ---------- Run ----------

async def run_discordbot(TOKEN):
    await bot.start(TOKEN)
