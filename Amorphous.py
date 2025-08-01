from google import genai
from google.genai import types
search_tool = types.Tool(google_search=types.GoogleSearch())

# import wikipedia
import discord
import requests
import random
import re
import threading
from datetime import datetime, timedelta
import discord.utils
import json

from time import sleep
import os, os.path
from keep_alive import keep_alive

keep_alive()


def update_watcher():
    while True:
        sleep(20)
        if os.path.exists("update2"):
            break


channel_sep = True
threading.Thread(target=update_watcher).start()
conversation = []
bot_configs = {}
intents = discord.Intents.all()
intents.message_content = True

client = discord.Client(intents=intents)
# Config_start
amorphous_config = {"""shape-name""": os.environ.get("Name"),
                    """backstory""": os.environ.get("Rp"),
                    """token""": os.environ.get("Discord"),
                    """api_key""": os.environ.get("Gemini"),
                    """prefix""": os.environ.get("Id"), """hosting""": """download"""}
# Config_end
rp = amorphous_config["backstory"]
prefix = amorphous_config["prefix"]
gemini_api_key = amorphous_config["api_key"]
token = amorphous_config["token"]
shape_name = amorphous_config["shape-name"]
knowledge_db = []
user = os.environ.get("User")

# Trusted users system - Add your trusted user IDs here
TRUSTED_USERS = [user]  # Add more IDs as needed
TRUSTED_USERS_FILE = "trusted_users.json"

def load_trusted_users():
    """Load trusted users from file"""
    global TRUSTED_USERS
    try:
        if os.path.exists(TRUSTED_USERS_FILE):
            with open(TRUSTED_USERS_FILE, 'r') as f:
                TRUSTED_USERS = json.load(f)
    except Exception as e:
        print(f"Error loading trusted users: {e}")

def save_trusted_users():
    """Save trusted users to file"""
    try:
        with open(TRUSTED_USERS_FILE, 'w') as f:
            json.dump(TRUSTED_USERS, f)
    except Exception as e:
        print(f"Error saving trusted users: {e}")

def is_trusted_user(user_id):
    """Check if user is trusted"""
    return user_id in TRUSTED_USERS

def can_moderate(user_id, guild_permissions):
    """Check if user can moderate (trusted or has permissions)"""
    return is_trusted_user(user_id) or guild_permissions.kick_members or guild_permissions.ban_members or guild_permissions.moderate_members

# Load trusted users on startup
load_trusted_users()

model = 'gemini-2.0-flash'
model1= 'gemini-2.5-flash'
model2= 'gemini-2.0-flash-lite'
model3= 'gemini-2.5-pro'

gemini_client = genai.Client(
    api_key=gemini_api_key,
    http_options=types.HttpOptions(api_version='v1alpha')
)

safety_settings = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
]

config = types.GenerateContentConfig(safety_settings=safety_settings, tools=[search_tool])


def get_convo(guild_id):
    """Retrieves the bot configuration for a given guild, creating a default one if it doesn't exist."""
    if guild_id not in bot_configs:
        bot_configs[guild_id] = {
            "conversation": [],
            "toggle": True  # Default: Ignore commands from bots
        }
    return bot_configs[guild_id]


def update_convo(conversation, guild_id):
    bot_configs[guild_id]["conversation"] = conversation

    return True


async def check_permissions(message):
    # Allow user with specific ID to bypass permission checks
    if message.author.id == user:
        return True
    if not (message.author.guild_permissions.manage_guild or message.author.guild_permissions.administrator):
        await message.channel.send("You need 'Manage Server' or 'Administrator' permissions to use this command.")
        return False
    return True

async def check_moderation_permissions(message):
    """Check if user can use moderation commands"""
    if is_trusted_user(message.author.id):
        return True
    if message.author.guild_permissions.kick_members or message.author.guild_permissions.ban_members or message.author.guild_permissions.moderate_members:
        return True
    await message.channel.send("You need mod perms to use this command")
    return False

def parse_time_duration(duration_str):
    """Parse duration string like '1h', '30m', '1d' into timedelta"""
    if not duration_str:
        return None
    
    duration_str = duration_str.lower()
    if duration_str[-1] == 's':
        return timedelta(seconds=int(duration_str[:-1]))
    elif duration_str[-1] == 'm':
        return timedelta(minutes=int(duration_str[:-1]))
    elif duration_str[-1] == 'h':
        return timedelta(hours=int(duration_str[:-1]))
    elif duration_str[-1] == 'd':
        return timedelta(days=int(duration_str[:-1]))
    else:
        # Default to minutes if no unit specified
        return timedelta(minutes=int(duration_str))

def gen(model, prompt, streaming=False):
    if streaming:
        return gemini_client.models.generate_content_stream(
            model=model, contents=prompt, config=config
        )
    else:
        return gemini_client.models.generate_content(
            model=model, contents=prompt, config=config
        )


def safesplit(text):
    chunks = []
    chunk_size = 2000
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = end
    return chunks


async def safesend(function, text):
    safechunks = safesplit(text)
    for m in safechunks:
        await function(m)


intents = discord.Intents.all()
intents.message_content = True

client = discord.Client(intents=intents)


async def replace_mentions_with_usernames(content: str, message: discord.Message) -> str:
    """
    Replaces user mentions (<@USER_ID> or <@!USER_ID>) in a string
    with their corresponding display names (@DisplayName).

    Args:
        content: The original string content (e.g., message.content).
        message: The discord.Message object containing the mentions.

    Returns:
        The string with mentions replaced by usernames.
    """
    # Start with the original content
    processed_content = content

    # Iterate through each user mentioned in the message
    # message.mentions contains a list of discord.Member or discord.User objects
    for user in message.mentions:
        # user.mention creates the standard mention string (<@USER_ID>)
        # user.display_name gets the user's server nickname if available, otherwise their global username
        mention_string = user.mention
        replacement_string = f"@{user.display_name}"

        # Replace all occurrences of the mention string in the processed content
        # We need to handle both <@USER_ID> and <@!USER_ID> (nickname mention) formats.
        # discord.py's user.mention usually gives <@USER_ID>, but let's be safe.
        # A simple string replace works well here.
        processed_content = processed_content.replace(mention_string, replacement_string)

        # Handle the potential nickname mention format <@!USER_ID> just in case
        # Although user.mention might not produce this directly, it could appear in raw content
        nickname_mention_string = f"<@!{user.id}>"
        processed_content = processed_content.replace(nickname_mention_string, replacement_string)

    return processed_content


async def find_member(message, member_identifier):
    member = None

    # Attempt to get member by mention
    if member_identifier.startswith('<@') and member_identifier.endswith('>'):
        # Handle both normal mentions and nickname mentions
        member_id = ''.join(filter(str.isdigit, member_identifier))
        try:
            member_id = int(member_id)
            member = message.guild.get_member(member_id)
        except ValueError:
            await message.channel.send("Invalid member mention format.")
            return None
    else:
        # Try to convert to int (user ID)
        try:
            member_id = int(member_identifier)
            member = message.guild.get_member(member_id)
            if member:
                return member
        except ValueError:
            pass
        
        # Attempt to find by exact match first
        for m in message.guild.members:
            # Check nickname exact match
            if m.nick and m.nick.lower() == member_identifier.lower():
                member = m
                break
            # Check username exact match
            if m.name.lower() == member_identifier.lower():
                member = m
                break

        # If no exact match, try partial match
        if member is None:
            # Attempt to find by nickname or username (partial match)
            for m in message.guild.members:
                if m.nick and member_identifier.lower() in m.nick.lower():
                    member = m
                    break

            # If not found by nickname, try by username
            if member is None:
                for m in message.guild.members:
                    if member_identifier.lower() in m.name.lower():
                        member = m
                        break

    if not member:
        return None

    return member


async def fix_member(msg, dmessage):
    temp = msg
    replaced = []
    replace = re.findall("@?(.*) ", msg + " ")
    for m in replace:
        replace.append(await find_member(dmessage, m))
    d = 0
    for m in replaced:
        temp = temp.replace(replace[d], m)
        d += 1
    return temp


toggle = False


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    await client.change_presence(activity=discord.CustomActivity(name="something"))


activated_channels = []
ignored_channels = []


@client.event
async def on_message(message):
    global activated_channels
    # Support both DMs and guild channels
    if message.guild:
        guild_id = message.guild.id
    else:
        guild_id = f"user_{message.author.id}"

    toggle = get_convo(guild_id=guild_id)["toggle"]
    conversation = get_convo(guild_id=guild_id)["conversation"]

    if (message.author == client.user) and message.content.startswith("(system response)\n"): return
    channel_tag = ""
    if channel_sep:
        channel_tag = "{" + message.channel.name + "}"
    else:
        channel_tag = ""
    cleanedup = await replace_mentions_with_usernames(message.content, message)
    print(f"[{message.author}]({message.author.display_name}){channel_tag}  : {cleanedup}")
    conversation.append(f"[{message.author.name}]({message.author.display_name}){channel_tag}:" + cleanedup)

    update_convo(conversation, guild_id)
    if message.attachments:
        rem = len(conversation) - 1
        for attachment in message.attachments:
            # Download the attachment using requests
            r = requests.get(attachment.url)
            if r:
                # Check if the request was successful
                if r.status_code == 200:
                    content = r.content
                    # base64.b64encode(bytes(r.text)).decode()
                    response = gemini_client.models.generate_content(

                        contents=[
                            types.Part.from_bytes(

                                data=content,
                                mime_type='image/png',
                            ),
                            'Describe this image in detail! Do not use markdown. keep all of it in a single line!'
                        ], model=model, config=config
                    )
                    print(response.text)

                    conversation[rem] += "(System image support)[File attached, Image description:" + response.text

                    print(f"Downloaded {attachment.filename}")

    if message.author == client.user:
        return
    ran_command = False
    
    # Help command
    if message.content.startswith(f'{prefix} help'):
        help_text = (
            f"**{shape_name} Bot Commands:**\n"
            f"`{prefix} help` - Show this help message\n"
            f"`{prefix} activate` - Activate bot in this channel\n"
            f"`{prefix} deactivate` - Deactivate bot in this channel (or add channel to exclusion list with manage server perms)\n"
            f"`{prefix} wack` - Wipe conversation history\n"
            f"`{prefix} toggle` - Toggle bot ignoring other bots\n"
            f"`{prefix} allow` - Allow bot to respond in channel\n"
            f"`{prefix} reset` - Reset bot to default state\n"
            f"`{prefix} search (the thing you want to search)` - Makes the bot search\n\n"
            "**Moderation Commands:**\n"
            f"`{prefix} ban @user [reason]` - Ban a user\n"
            f"`{prefix} kick @user [reason]` - Kick a user\n"
            f"`{prefix} timeout @user <duration> [reason]` - Timeout a user (e.g., 10m, 1h, 1d)\n"
            "Mention the bot or reply to its message to chat.\n\n"
            "Powered by Amorphous Discord Engine and Gemini 2.0 Flash"
        )
        await message.channel.send(help_text)
        ran_command = True
    
    # Ban command
    if message.content.startswith(f"{prefix} ban "):
        if not await check_moderation_permissions(message):
            ran_command = True
        else:
            args = message.content[len(f"{prefix} ban "):].split(" ", 1)
            if len(args) < 1:
                await message.channel.send("Usage: `ban @user [reason]`")
                ran_command = True
            else:
                target_member = await find_member(message, args[0])
                if not target_member:
                    await message.channel.send("User not found")
                    ran_command = True
                elif is_trusted_user(target_member.id):
                    await message.channel.send("blud u aint banning da owner")
                    ran_command = True
                else:
                    reason = args[1] if len(args) > 1 else f"Banned by {message.author.display_name}"
                    try:
                        await target_member.ban(reason=reason)
                        await message.channel.send(f"Banned **{target_member.display_name}** | Reason: {reason}")
                    except discord.Forbidden:
                        await message.channel.send("I don't have permission to ban this user")
                    except Exception as e:
                        await message.channel.send("Error banning user")
                    ran_command = True

    # Kick command
    if message.content.startswith(f"{prefix} kick "):
        if not await check_moderation_permissions(message):
            ran_command = True
        else:
            args = message.content[len(f"{prefix} kick "):].split(" ", 1)
            if len(args) < 1:
                await message.channel.send("Usage: `kick @user [reason]`")
                ran_command = True
            else:
                target_member = await find_member(message, args[0])
                if not target_member:
                    await message.channel.send("User not found!")
                    ran_command = True
                elif is_trusted_user(target_member.id):
                    await message.channel.send("blud u aint kicking da owner")
                    ran_command = True
                else:
                    reason = args[1] if len(args) > 1 else f"Kicked by {message.author.display_name}"
                    try:
                        await target_member.kick(reason=reason)
                        await message.channel.send(f"Kicked **{target_member.display_name}** | Reason: {reason}")
                    except discord.Forbidden:
                        await message.channel.send("I don't have permission to kick this user!")
                    except Exception as e:
                        await message.channel.send("Error kicking user")
                    ran_command = True

    # Timeout command
    if message.content.startswith(f"{prefix} timeout "):
        if not await check_moderation_permissions(message):
            ran_command = True
        else:
            args = message.content[len(f"{prefix} timeout "):].split(" ", 2)
            if len(args) < 2:
                await message.channel.send("Usage: `timeout @user <duration> [reason]`\nDuration examples: 10m, 1h, 2d")
                ran_command = True
            else:
                target_member = await find_member(message, args[0])
                if not target_member:
                    await message.channel.send("User not found!")
                    ran_command = True
                elif is_trusted_user(target_member.id):
                    await message.channel.send("blud u aint timiming out da owner")
                    ran_command = True
                else:
                    try:
                        duration = parse_time_duration(args[1])
                        if not duration:
                            await message.channel.send("Invalid duration format. Use: 10m, 1h, 2d, etc.")
                            ran_command = True
                        else:
                            reason = args[2] if len(args) > 2 else f"Timed out by {message.author.display_name}"
                            until = discord.utils.utcnow() + duration
                            await target_member.timeout(until, reason=reason)
                            await message.channel.send(f"Timed out **{target_member.display_name}** for {args[1]} | Reason: {reason}")
                    except discord.Forbidden:
                        await message.channel.send("I don't have permission to timeout this user!")
                    except Exception as e:
                        await message.channel.send("Error timing out user")
                    ran_command = True



    # Search command
    if message.content.startswith(f"{prefix} search "):
        query = message.content[len(f"{prefix} search "):]
        try:
            async with message.channel.typing():
                response = gemini_client.models.generate_content(
                    model=model,
                    contents=f"Please search and answer this: {query}. Your prompt is {rp}. Stay in character like in the prompt and answer the question. Keep answer short (70-100 tokens).",
                    config=config
                )
                answer = response.text
                if not answer:
                    answer = "I couldn't find anything."
        except Exception as e:
            print(f"[ERROR in search command]: {e}")
            try:
                async with message.channel.typing():
                    response = gemini_client.models.generate_content(
                        model=model1,
                        contents=f"Please search and answer this: {query}. Your prompt is {rp}. Stay in character like in the prompt and answer the question. Keep answer short (70-100 tokens).",
                        config=config
                    )
                    answer = response.text
                    if not answer:
                        answer = "I couldn't find anything."
            except Exception as modelone_e:
                try:
                    async with message.channel.typing():
                        response = gemini_client.models.generate_content(
                            model=model2,
                            contents=f"Please search and answer this: {query}. Your prompt is {rp}. Stay in character like in the prompt and answer the question. Keep answer short (70-100 tokens).",
                            config=config
                        )
                        answer = response.text
                        if not answer:
                            answer = "I couldn't find anything."
                except Exception as modeltwo_e:
                    await message.channel.send(f"(system response)\n> An error occurred while searching: `{e}`")
                    print("Search error (maybe rate limited)")
        await safesend(message.channel.send, answer)
        ran_command = True
        
    # Allow command        
    if message.content.startswith(f'{prefix} allow'):
        await message.channel.send("Allowed.")
        if message.channel.id in ignored_channels:
            ignored_channels.remove(message.channel.id)
        ran_command = True
        
    # Activate command
    if message.content.startswith(f'{prefix} activate'):
        activated_channels.append(message.channel.id)
        await message.channel.send('(system response)\n>(activated)')
        ran_command = True
        
    # Deactivate command
    if message.content.startswith(f'{prefix} deactivate'):
        if message.channel.id in activated_channels:
            activated_channels.remove(message.channel.id)
            await message.channel.send('(system response)\n> Deactivated.')
        else:
            if await check_permissions(message):
                if message.channel.id not in ignored_channels:
                    await message.channel.send('(system response)\nAdded to exclusion.')
                    ignored_channels.append(message.channel.id)
            else:
                await message.channel.send('(system response)\nHELL NAW; ')
        ran_command = True

    # Toggle command
    if message.content.startswith(f"{prefix} toggle"):
        await message.channel.send("(system response)\n Bro this is dangerous af u sure? Activated prepare for chaOS")
        toggle = not (toggle)
        ran_command = True
        
    # Wack command
    if message.content.startswith(f'{prefix} wack'):
        conversation.clear()
        await message.channel.send('(system response)\n> Conversation history wiped! рџ’Ђ')
        ran_command = True
        
    if len(conversation) > 600:
        conversation.remove(conversation[0])
    update_convo(conversation, guild_id)

    bot_configs[guild_id]["toggle"] = toggle
    if ran_command:
        return
    # Ignore messages from bots (including itself and other bots)
    if message.author.bot and toggle:
        return
    # Always respond if this is a reply to the bot's own message
    if message.reference:
        try:
            replied_message = await message.channel.fetch_message(message.reference.message_id)
            if replied_message.author == client.user:
                should_respond = True
        except Exception:
            pass
    # replace with your channel IDs

    should_respond = False

    # Check if channel is activated
    if message.channel.id in activated_channels:
        should_respond = True
    else:
        # Respond if pinged or random chance (1 in 5)
        if client.user in message.mentions or random.randint(1, 5) == 1:
            should_respond = True
    if message.channel.id in ignored_channels:
        should_respond = False
    if isinstance(message.channel, discord.channel.DMChannel):
        should_respond = True
    if should_respond:
        try:
            async with message.channel.typing():
                l = gen(model, rp + str(
                    conversation) + f";You username here is {client.user}; Please generate a response based on the text above!  ").text.removeprefix(
                    str(client.user)).removeprefix(":")
        except Exception as e:
            try:
                l = ("(API CREDITS RAN OUT; Using free model; Please wait.) \n") + str(e)
                print(l)
                l = ""
                l += gen(model1, rp + str(conversation) + f";Your username here is {client.user}; Please generate a response based on the text above!  ").text.removeprefix(
                    str(client.user)).removeprefix(":")
            except Exception as inner_e:
                l += "PRIMARY AND FALLBACK MODEL FAILED. MORE INFORMATION: " + str(inner_e)
                print(l)
                l= ""
                try:
                    l += gen(model2, rp + str(conversation) + f";Your username here is {client.user}; Please generate a response based on the text above!  ").text.removeprefix(
                    str(client.user)).removeprefix(":")
                except Exception as another_e:
                    l += "PRIMARY AND 2 OTHER FALLBACK MODELS FAILED. MORE INFORMATION: " + str(another_e)
                    print(l)
                    l= ""
                    try:
                        l += gen(model3, rp + str(
                    conversation) + f";Your username here is {client.user}; Please generate a response based on the text above!  ").text.removeprefix(
                            str(client.user)).removeprefix(":")
                    except Exception as why_e:
                        l += "PRIMARY AND 3 OTHER FALLBACK MODELS FAILED. MORE INFORMATION: " + str(why_e)
                    

        print(l)
        await safesend(message.channel.send, l)


client.run(token)
