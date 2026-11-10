
import os
import asyncio
import aiohttp
import discord

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

async def get_twitch_token(session):
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }

    async with session.post(url, params=params) as response:
        response.raise_for_status()
        data = await response.json()
        return data["access_token"]

async def is_live(session, token):
    url = "https://api.twitch.tv/helix/streams"
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {token}"
    }
    params = {"user_login": TWITCH_LOGIN}

    async with session.get(url, headers=headers, params=params) as response:
        response.raise_for_status()
        data = await response.json()
        return len(data.get("data", [])) > 0

def make_embed(live):
    if live:
        embed = discord.Embed(
            title="🔴 MOXENLIVE ER LIVE!",
            description="Jeg er live på Twitch akkurat nå!",
            color=0xFF6A00
        )
        embed.add_field(name="Status", value="🟢 LIVE", inline=True)
    else:
        embed = discord.Embed(
            title="⚫ MOXENLIVE ER OFFLINE",
            description="Jeg er ikke live akkurat nå.",
            color=0x303030
        )
        embed.add_field(name="Status", value="⚫ OFFLINE", inline=True)

    embed.add_field(
        name="Se streamen",
        value=f"[Åpne Twitch-kanalen]({TWITCH_URL})",
        inline=False
    )
    embed.set_footer(text="MOXENLIVE • Automatisk status")
    return embed

@client.event
async def on_ready():
    global STATUS_MESSAGE_ID

    print(f"Logget inn som {client.user}")

    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        channel = await client.fetch_channel(CHANNEL_ID)

    if STATUS_MESSAGE_ID:
        try:
            status_message = await channel.fetch_message(int(STATUS_MESSAGE_ID))
        except discord.NotFound:
            status_message = await channel.send(embed=make_embed(False))
    else:
        status_message = await channel.send(embed=make_embed(False))
        print(f"STATUS_MESSAGE_ID={status_message.id}")

    async with aiohttp.ClientSession() as session:
        token = await get_twitch_token(session)

        while not client.is_closed():
            try:
                live = await is_live(session, token)
                await status_message.edit(embed=make_embed(live))
                print(f"Status oppdatert: {'LIVE' if live else 'OFFLINE'}")
            except Exception as error:
                print(f"Feil ved statusoppdatering: {error}")

            await asyncio.sleep(CHECK_INTERVAL)

client.run(DISCORD_TOKEN)
