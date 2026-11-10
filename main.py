
import os
import time
import aiohttp
import discord
from discord.ext import tasks

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
TWITCH_CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
TWITCH_CLIENT_SECRET = os.environ["TWITCH_CLIENT_SECRET"]
CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
STATUS_MESSAGE_ID = os.getenv("STATUS_MESSAGE_ID")

TWITCH_LOGIN = "moxenlive"
TWITCH_URL = "https://twitch.tv/moxenlive"
CHECK_INTERVAL = 60

intents = discord.Intents.default()
client = discord.Client(intents=intents)

session = None
status_message = None
access_token = None
token_expires_at = 0


async def get_twitch_token():
    global access_token, token_expires_at

    if access_token and time.monotonic() < token_expires_at - 60:
        return access_token

    url = "https://id.twitch.tv/oauth2/token"

    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }

    async with session.post(url, params=params) as response:
        if response.status != 200:
            print(f"Twitch token-feil: HTTP {response.status}")
            raise RuntimeError("Kunne ikke hente Twitch-token")

        data = await response.json()

    access_token = data["access_token"]
    token_expires_at = time.monotonic() + data["expires_in"]

    print("Twitch-token oppdatert")
    return access_token


async def is_live():
    url = "https://api.twitch.tv/helix/streams"

    for attempt in range(2):
        token = await get_twitch_token()

        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}"
        }

        params = {"user_login": TWITCH_LOGIN}

        async with session.get(
            url,
            headers=headers,
            params=params
        ) as response:

            if response.status == 401 and attempt == 0:
                print("Twitch avviste token. Henter nytt token.")
                global access_token, token_expires_at
                access_token = None
                token_expires_at = 0
                continue

            if response.status != 200:
                print(f"Twitch API-feil: HTTP {response.status}")
                raise RuntimeError("Twitch API svarte med feil")

            data = await response.json()

            streams = data.get("data", [])
            return len(streams) > 0

    raise RuntimeError("Kunne ikke kontrollere Twitch-status")


def make_embed(live):
    if live:
        embed = discord.Embed(
            title="🔴 MOXENLIVE ER LIVE!",
            description="Jeg er live på Twitch akkurat nå!",
            color=0xFF6A00
        )
        embed.add_field(
            name="Status",
            value="🟢 LIVE",
            inline=True
        )
    else:
        embed = discord.Embed(
            title="⚫ MOXENLIVE ER OFFLINE",
            description="Jeg er ikke live akkurat nå.",
            color=0x303030
        )
        embed.add_field(
            name="Status",
            value="⚫ OFFLINE",
            inline=True
        )

    embed.add_field(
        name="Se streamen",
        value=f"[Åpne Twitch-kanalen]({TWITCH_URL})",
        inline=False
    )

    embed.set_footer(text="MOXENLIVE • Automatisk status")
    return embed


@tasks.loop(seconds=CHECK_INTERVAL)
async def update_status():
    global status_message

    try:
        live = await is_live()

        if status_message is None:
            print("Statusmelding mangler. Hopper over oppdatering.")
            return

        await status_message.edit(embed=make_embed(live))

        print(
            f"Status oppdatert: {'LIVE' if live else 'OFFLINE'}"
        )

    except Exception as error:
        print(
            f"Statuskontroll feilet: "
            f"{type(error).__name__}: {error}"
        )
        print("Beholder forrige status.")


@update_status.before_loop
async def before_status_update():
    await client.wait_until_ready()


@client.event
async def on_ready():
    global session, status_message

    print(f"Logget inn som {client.user}")

    if session is None or session.closed:
        timeout = aiohttp.ClientTimeout(total=20)
        session = aiohttp.ClientSession(timeout=timeout)

    channel = client.get_channel(CHANNEL_ID)

    if channel is None:
        channel = await client.fetch_channel(CHANNEL_ID)

    if STATUS_MESSAGE_ID:
        try:
            status_message = await channel.fetch_message(
                int(STATUS_MESSAGE_ID)
            )
            print("Eksisterende statusmelding funnet.")

        except discord.NotFound:
            status_message = await channel.send(
                embed=make_embed(False)
            )
            print(
                f"Ny statusmelding opprettet: {status_message.id}"
            )
    else:
        status_message = await channel.send(
            embed=make_embed(False)
        )
        print(
            f"STATUS_MESSAGE_ID={status_message.id}"
        )

    if not update_status.is_running():
        update_status.start()
        print("Automatisk statuskontroll startet.")


client.run(DISCORD_TOKEN)
