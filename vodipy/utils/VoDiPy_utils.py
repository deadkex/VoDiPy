from typing import Union

from dis_snek import Permissions, ComponentContext, InteractionContext, MessageContext

__SESSION_SEQUENCE = 0


def get_next_seq():
    """Get a unique sequence number from the current session"""
    global __SESSION_SEQUENCE
    __SESSION_SEQUENCE += 1
    return __SESSION_SEQUENCE


def can_join_voice(ctx: Union[InteractionContext, MessageContext, ComponentContext]):
    """Check if the bot has enough permissions to join the ctx.authors voice channel"""
    perms = ctx.guild.me.channel_permissions(ctx.author.voice.channel)
    return Permissions.ADMINISTRATOR in perms \
        or all(x in perms for x in [Permissions.CONNECT, Permissions.SPEAK, Permissions.VIEW_CHANNEL,
                                    Permissions.MOVE_MEMBERS]) \
        or (all(x in perms for x in [Permissions.CONNECT, Permissions.SPEAK, Permissions.VIEW_CHANNEL])
            and not ctx.author.voice.channel.user_limit == len(ctx.author.voice.channel.voice_members))
