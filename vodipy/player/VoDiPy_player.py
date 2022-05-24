from typing import Union

from naff import InteractionContext, PrefixedContext, ChannelTypes, Permissions
from naff.client.errors import VoiceConnectionTimeout, VoiceWebSocketClosed

from VoDiPy_defines import MusicPlayerSettings as MPSettings
from VoDiPy_defines import MusicPlayerStates as MPStates
from player.VoDiPy_classes import MusicPlayer
from utils.VoDiPy_api import yt_api_playlist_songs_count, yt_api_playlist_data, yt_api_video_data, yt_dl_data
from utils.VoDiPy_utils import can_join_voice


async def case_command_play(ctx: Union[InteractionContext, PrefixedContext], link):
    """Callback for the play command

    :param ctx: context
    :param link: either a keyword or a youtube link
    """
    if ctx.channel.type == ChannelTypes.DM:
        await ctx.send("This command cannot be used in private messages!")
        return

    # remove automatic embedding
    if type(ctx) == PrefixedContext:
        if ctx.guild.me.has_permission(Permissions.MANAGE_MESSAGES):
            await ctx.message.suppress_embeds()

    # create/get the music player for this guild
    if not ctx.bot.mps.get(ctx.guild_id):
        ctx.bot.mps[ctx.guild_id] = MusicPlayer()
    mp: MusicPlayer = ctx.bot.mps.get(ctx.guild_id)

    if mp.state == MPStates.loading:
        await ctx.send("Another person just started the musicbot.", ephemeral=True)
        return
    elif mp.state == MPStates.exit:
        await ctx.send("Please try again, the musicbot is stopping right now.", ephemeral=True)
        return

    is_slash = type(ctx) == InteractionContext
    vc = ctx.bot.get_bot_voice_state(ctx.guild.id)

    # Check if is allowed to use
    if not ctx.author.voice or not ctx.author.voice.channel or ctx.author.voice.guild.id != ctx.guild_id:
        await ctx.send("You have to be in a voice channel in this guild!", ephemeral=True)
        return
    elif not (vc and ctx.author.voice and ctx.author.voice.channel.id == vc.channel.id
              or not vc and ctx.author.voice and ctx.author.voice.channel):
        await ctx.send("The musicplayer is already getting used in another channel!", ephemeral=True)
        return

    # Local link validation
    if len(link.split()) != 1:
        await ctx.send("Please provide a correct link!", ephemeral=True)
        return

    # Get the actual link
    if MPSettings.player_keywords.get(link):
        link = MPSettings.player_keywords.get(link)
    if "youtube.com" in link:
        if "&list=" in link:
            link = link.split("&list=", 1)[0]
        if "&index=" in link:
            link = link.split("&index=", 1)[0]

    # Check if only add to queue, defer and perms to join channel
    if vc:
        only_queue = True
    else:
        if not can_join_voice(ctx):
            await ctx.send(f"{ctx.author.mention} I have no permission to join your voice channel!", ephemeral=True)
            return
        only_queue = False
        mp.init(ctx)
    if is_slash:
        await ctx.defer(ephemeral=bool(vc))

    if "youtube.com/playlist?list=" in link:  # case YouTube playlist
        pl_id = link.split("youtube.com/playlist?list=", 1)[1]
        pl_count = await yt_api_playlist_songs_count(pl_id)
        if not pl_count:
            await ctx.send("YouTube Playlist not found!", ephemeral=True)
            if not only_queue:
                mp.reset()
            return
        elif pl_count > MPSettings.warning_pl_count:
            await (await ctx.channel.send(ctx.author.mention + " Loading big playlists might take a bit longer."))\
                .delete(10)
        data = await yt_api_playlist_data(pl_id)
        while True:
            mp.queue.add_yt_api_dummies(data)
            if not data.get("nextPageToken"):
                break
            data = await yt_api_playlist_data(pl_id, data["nextPageToken"])
    elif "youtube.com/watch?v=" in link:  # case YouTube video
        vid = link.split("youtube.com/watch?v=", 1)[1]
        data = await yt_api_video_data(vid)
        if not data:
            if not only_queue:
                mp.reset()
            await ctx.send("YouTube Song not found or is age restricted!", ephemeral=True)
            return
        mp.queue.add_yt_api_dummies(data)
    else:  # case non-YouTube
        await (await ctx.send(ctx.author.mention + " Using non-youtube sources takes longer to load")).delete(delay=10)
        data = await yt_dl_data(link)
        if not data:
            if not only_queue:
                mp.reset()
            await ctx.send("Found nothing to play!", ephemeral=True)
            return
        mp.queue.add_yt_dl_songs(data)

    if not only_queue:  # Init MP: Preload first song /of the playlist
        song = await mp.queue.get_next_song(increment=False)
        if not song:
            await ctx.send("Song not found or is age restricted!", ephemeral=True)
            mp.reset()
            return
    else:  # MP running: add song/playlist
        if is_slash:
            await ctx.send("Added 👍", ephemeral=True)
        else:
            await ctx.message.add_reaction("👍")
        await mp.update_embed()
        return

    # maybe move this before fetching songs
    # and delete the msg in mp.reset() if state is loading
    mp.player_msg = await ctx.send(embed=mp.get_empty_embed(title="STARTING"))

    try:
        await ctx.author.voice.channel.connect(deafened=True)
    except (VoiceConnectionTimeout, VoiceWebSocketClosed):
        # bot cannot see the authors channel
        await ctx.channel.send(f"{ctx.author.mention} I have no permission to join your voice channel!")
        await mp.player_msg.delete()
        mp.reset()
        return

    await mp.play_loop(song)
