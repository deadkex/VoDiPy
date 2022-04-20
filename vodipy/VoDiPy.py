from datetime import datetime

from dis_snek import listen, Snake, Activity, ActivityType, Intents
from dis_snek.client.const import __version__ as dis_snek_version

import VoDiPy_secrets
from VoDiPy_defines import MusicPlayerSettings


class CustomSnake(Snake):
    mps = {}
    """{guild_id: MusicPlayer}"""


client = CustomSnake(
    intents=Intents.GUILD_VOICE_STATES | Intents.GUILD_MESSAGES | Intents.GUILD_MESSAGE_CONTENT | Intents.GUILDS,
    sync_interactions=True,
    delete_unused_application_cmds=True,
    default_prefix=MusicPlayerSettings.message_command_prefix,
    activity=Activity(type=ActivityType.LISTENING, name="all your favorite songs"),
    send_command_tracebacks=False
)


@listen()
async def on_startup():
    print(f"* {'-' * 40}\n"
          f"* [{datetime.now().replace(microsecond=0)}]\n"
          f"* Bot started.\n"
          f"* Dis-Snek: {dis_snek_version}\n"
          f"* {'-' * 40}")


client.load_extension("scales.VoDiPy_scale_player")
# client.load_extension("dis_snek.debug_scale")  # adds /debug commands

client.start(VoDiPy_secrets.token)
