from datetime import datetime

from naff import listen, Client, Activity, ActivityType, Intents
from naff.client.const import __version__ as naff_version

import VoDiPy_secrets
from VoDiPy_defines import MusicPlayerSettings as MPSettings


class CustomClient(Client):
    mps = {}
    """{guild_id: MusicPlayer}"""


client = CustomClient(
    intents=Intents.GUILD_VOICE_STATES | Intents.GUILD_MESSAGES | Intents.GUILD_MESSAGE_CONTENT | Intents.GUILDS,
    sync_interactions=True,
    # delete_unused_application_cmds=True,
    default_prefix=MPSettings.message_command_prefix,
    activity=Activity(type=ActivityType.LISTENING, name="all your favorite songs"),
    send_command_tracebacks=False
)


@listen()
async def on_startup():
    print(f"* {'-' * 40}\n"
          f"* [{datetime.now().replace(microsecond=0)}]\n"
          f"* Bot started.\n"
          f"* Naff: {naff_version}\n"
          f"* {'-' * 40}")


client.load_extension("extensions.VoDiPy_extension_player")
# client.load_extension("naff.debug_extension")  # adds /debug commands

client.start(VoDiPy_secrets.token)
