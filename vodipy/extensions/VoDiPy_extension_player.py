import asyncio
from datetime import datetime

from naff import Extension, listen, InteractionContext, OptionTypes, slash_option, slash_command, ComponentContext, \
    prefixed_command, PrefixedContext
from naff.api.events import VoiceStateUpdate

from player.VoDiPy_player import case_command_play
from player.VoDiPy_classes import MusicPlayer
from VoDiPy_defines import MusicPlayerStates as MPStates
from VoDiPy_defines import MusicPlayerSettings as MPSettings


class PlayerExtension(Extension):
    @prefixed_command()
    async def play(self, ctx: PrefixedContext):
        if len(ctx.args) == 1:
            await case_command_play(ctx, ctx.args[0])
        else:
            await ctx.reply(f"Please provide a link! `{MPSettings.message_command_prefix}play link`")

    @slash_command(
        name="play",
        description="Play music from youtube(videos/playlists), soundcloud, ...",
        scopes=[x for x in MPSettings.guilds_to_sync],
        dm_permission=False
    )
    @slash_option(
        name="link",
        description="Link to youtube(video/playlist), soundcloud, ...",
        required=True,
        opt_type=OptionTypes.STRING
    )
    async def slash_player(self, ctx: InteractionContext, link):
        await case_command_play(ctx, link)

    @listen()
    async def on_component(self, event):
        """Called on button press / select choice. Don't defer to prevent spamming."""
        ctx: ComponentContext = event.context
        if ctx.custom_id.startswith("player::"):
            c_id = ctx.custom_id.split("player::")[1]
            mp: MusicPlayer = self.bot.mps.get(ctx.guild_id)
            if not mp or not mp.player_msg or ctx.message.id != mp.player_msg.id:
                embed = ctx.message.embeds[0] if ctx.message.embeds else None
                if embed:
                    embed.title = "Music Player | STOPPED"
                await ctx.edit_origin("**Musicplayer outdated, please create a new one for this guild.**",
                                      embed=embed, components=[])
                return
            elif not ctx.voice_state or not ctx.voice_state.connected:
                await mp.stop()
                return
            elif not mp.is_allowed(ctx, restrict_to_dj=c_id in ["stop", "move"]):
                await ctx.send("You cannot use this right now.", ephemeral=True)
                return

            match c_id:
                case "play":
                    await mp.b_resume(ctx)
                case "pause":
                    await mp.b_pause(ctx)
                case "skip":
                    await mp.b_skip(ctx)
                case "shuffle":
                    await mp.b_shuffle(ctx)
                case "lower":
                    await mp.b_lower(ctx)
                case "higher":
                    await mp.b_higher(ctx)
                case "stop":
                    await mp.b_stop(ctx)
                case "move":
                    await mp.b_move(ctx)
                case "select":
                    await mp.callback_select(ctx)

    @listen()
    async def on_voice_state_update(self, event: VoiceStateUpdate):
        # check if cached
        if not event.before and not event.after:
            return

        # check if bot or still in same channel
        state = event.before if event.before else event.after
        if state.member.bot or (event.before and event.after and event.before.channel.id == event.after.channel.id):
            return

        # check if mp currently playing in this guild
        mp: MusicPlayer = self.bot.mps.get(state.guild.id)
        if not mp or mp.state in [MPStates.exit, MPStates.ready, MPStates.loading]:
            return

        if not event.after or (event.before and event.after):  # left voice
            # if dj left, check timeout
            if state.member.id == mp.dj.id:
                time = datetime.now()
                mp.timer_new_dj = time
                await asyncio.sleep(MPSettings.timeout_new_dj)
                if mp.timer_new_dj != time:
                    return
                mp.timer_new_dj = None

            vc = self.bot.get_bot_voice_state(state.guild.id)

            # if dj left, assign new dj
            if state.member.id == mp.dj.id and len(vc.channel.voice_members) > 1:
                for new_dj in vc.channel.voice_members:
                    if not new_dj.bot:
                        mp.dj = new_dj
                        await mp.update_embed()
                        break
            else:
                # if dj left & channel empty remove dj
                if state.member.id == mp.dj.id:
                    mp.dj = None
                    await mp.update_embed()

                # if empty channel, check leave timeout
                if MPSettings.leave_if_empty and vc and len(vc.channel.voice_members) == 1:
                    time = datetime.now()
                    mp.timer_empty = time
                    await asyncio.sleep(MPSettings.timeout_empty)
                    if mp.timer_empty == time:
                        await mp.stop()
                        mp.timer_empty = None
                elif not vc and mp.state in [MPStates.playing, MPStates.on_next, MPStates.paused]:
                    await mp.stop()
        else:  # joined voice
            mp.timer_empty = None
            if not mp.dj:
                mp.dj = state.member
                await mp.update_embed()
            elif mp.dj.id == state.member.id:
                mp.timer_new_dj = None


def setup(client):
    PlayerExtension(client)
