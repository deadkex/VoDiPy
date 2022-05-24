import asyncio
import random
from datetime import timedelta, datetime
from typing import Union

from naff import Embed, Member, ActionRow, Button, ButtonStyles, \
    Select, SelectOption, ComponentContext, Message, Client
from naff.api.voice.audio import AudioVolume
from naff.client.errors import NotFound, VoiceConnectionTimeout, VoiceWebSocketClosed

from VoDiPy_defines import MusicPlayerSettings as MPSettings
from VoDiPy_defines import MusicPlayerStates as MPStates
from utils.VoDiPy_api import yt_dl_data
from utils.VoDiPy_utils import get_next_seq, can_join_voice


class MusicPlayerQueueSong:
    loaded = False
    error = False
    private = False
    duration = "loading..."
    title = ""
    uploader = ""
    desc = ""
    stream_url = ""
    thumbnail = ""
    text_width = 50

    def __init__(self, entry_yt_api=None, entry_yt_dl=None, video_url=None, playlist_url=None, playlist_pos=None):
        assert (entry_yt_api or entry_yt_dl or video_url or (playlist_url and playlist_pos and playlist_pos != 0))
        self.song_id = get_next_seq()
        self.video_url = video_url
        self.playlist_url = playlist_url
        self.playlist_pos = playlist_pos
        if entry_yt_api:
            self.process_data_yt_api(entry_yt_api)
        elif entry_yt_dl:
            self.process_data_yt_dl(entry_yt_dl)

    async def load_data(self):
        """Download the song data"""
        if self.private or self.error or self.loaded:
            return
        # prefer video_url when downloading
        data = await yt_dl_data(self.video_url if self.video_url else self.playlist_url, self.playlist_pos)
        if not data:
            self.error = True
        else:
            self.process_data_yt_dl(data)

    def process_data_yt_api(self, entry):
        """Fill Song with data received from the youtube api"""
        if entry["status"]["privacyStatus"] != "public":
            self.error = True
            self.private = True
            return
        self.title = entry["snippet"]["title"] if len(entry["snippet"]["title"]) < self.text_width \
            else (entry["snippet"]["title"][:self.text_width] + "...")
        if "playlistItem" in entry["kind"]:
            uploader = entry["snippet"]["videoOwnerChannelTitle"]
            self.video_url = "https://www.youtube.com/watch?v=" + entry["snippet"]["resourceId"]["videoId"]
            self.playlist_url = "https://www.youtube.com/playlist?list=" + entry["snippet"].get("playlistId")
            self.playlist_pos = entry["snippet"].get("position")
        else:
            uploader = entry["snippet"]["channelTitle"]
            self.video_url = "https://www.youtube.com/watch?v=" + entry["id"]
        self.uploader = uploader if len(uploader) < self.text_width else (uploader[:self.text_width] + "...")
        self.desc = self.uploader

    def process_data_yt_dl(self, entry):
        """Fill song with data received from yt-dlp/youtube_dl, song is 'loaded' in this case"""
        self.title = entry["title"] if len(entry["title"]) < self.text_width \
            else (entry["title"][:self.text_width] + "...")
        self.uploader = entry["uploader"] if len(entry["uploader"]) < self.text_width \
            else (entry["uploader"][:self.text_width] + "...")
        self.duration = str(timedelta(seconds=int(entry["duration"]))) \
            if entry.get("duration") and entry["duration"] > 0 else "Stream"
        self.desc = self.uploader + " - " + self.duration
        self.video_url = entry["webpage_url"]
        self.stream_url = entry["url"]
        if entry.get("thumbnail"):
            self.thumbnail = entry["thumbnail"]
        else:
            self.thumbnail = entry["thumbnails"][0]["url"]
        self.loaded = True


class MusicPlayerQueue:
    songs: list[MusicPlayerQueueSong] = []  # song queue in order
    queue_pos = 0  # current position in queue
    shuffle = False

    def add_yt_api_dummies(self, data):
        """Fill the queue with unloaded dummy songs"""
        for song_data in data["items"]:
            song = MusicPlayerQueueSong(entry_yt_api=song_data)
            if len(data["items"]) == 1:
                if not song.private:
                    self.songs.insert(1 if len(self.songs) == 0 else self.queue_pos + 1, song)
            else:
                if not song.private:
                    self.songs.append(song)

    def add_yt_dl_songs(self, data):
        """Fill the queue with data received from yt-dlp/youtube_dl (also non-YouTube)"""
        if not data.get("entries") or len(data["entries"]) == 1:
            song = MusicPlayerQueueSong(entry_yt_dl=data)
            if not song.private:
                self.songs.insert(1 if len(self.songs) == 0 else self.queue_pos + 1, song)
        else:
            for song_data in data["entries"]:
                song = MusicPlayerQueueSong(entry_yt_dl=song_data)
                if not song.private:
                    self.songs.append(song)

    async def get_next_song(self, increment=True, tries=0, check_loaded=False):
        """Get the next song from the queue

        :param increment: increment the queue_pos
        :param tries: needed internally to prevent infinite recursion
        :param check_loaded: needed internally to return a song that wasn't loaded before
        """
        # Prevents: Shuffle on & 1 Song with error
        if tries > 10:
            return None

        if self.shuffle and not check_loaded:
            self.queue_pos = random.randint(0, len(self.songs) - 1)  # could be improved with a smarter shuffle
            increment = False

        if increment:
            self.queue_pos += 1

        if len(self.songs) <= self.queue_pos:
            self.queue_pos = 0

        song = self.songs[self.queue_pos]
        if song.error:
            return await self.get_next_song(tries=tries + 1)
        elif not song.loaded:
            await song.load_data()
            return await self.get_next_song(increment=False, check_loaded=True)
        else:
            return song

    async def get_song_with_song_id(self, song_id, load_song=False, set_queue_pos_on_success=False):
        for pos, song in enumerate(self.songs):
            if song.song_id == song_id:
                if not song.loaded and not song.error and load_song:
                    await song.load_data()
                if song and song.loaded and not song.error and set_queue_pos_on_success:
                    self.queue_pos = pos
                return song
        return None

    def get_pos_with_song_id(self, song_id):
        for pos, song in enumerate(self.songs):
            if song.song_id == song_id:
                return pos
        return None

    def clear(self):
        """Reset the queue"""
        self.songs.clear()
        self.queue_pos = 0
        self.shuffle = False


class MusicPlayer:
    client: Client = None
    dj: Union[Member, None] = None
    guild_id: Union[int, None] = None
    queue: MusicPlayerQueue = MusicPlayerQueue()
    player_msg: Union[Message, None] = None
    volume: float = MPSettings.starting_volume
    state: int = MPStates.ready
    timer_empty: Union[datetime, None] = None
    timer_paused: Union[datetime, None] = None
    timer_new_dj: Union[datetime, None] = None
    q_lock = asyncio.Lock()

    def init(self, ctx):
        """Used to re-init the MusicPlayer in a guild"""
        self.client = ctx.bot
        self.state = MPStates.loading
        self.dj = ctx.author
        self.guild_id = ctx.guild_id

    def reset(self):
        """Reset the MusicPlayer"""
        self.dj = None
        self.guild_id = None
        self.queue.clear()
        self.player_msg = None
        self.volume = MPSettings.starting_volume
        self.state = MPStates.ready
        self.timer_empty = None
        self.timer_paused = None
        self.timer_new_dj = None

    async def stop(self):
        """Stop the mp"""
        await self.q_lock.acquire()
        if self.state != MPStates.ready:
            self.state = MPStates.exit
            if vc := self.client.get_bot_voice_state(self.guild_id):
                await vc.stop()
        self.q_lock.release()

    async def play_loop(self, song: MusicPlayerQueueSong, ctx=None):
        """Start the queue loop to continuously play songs"""
        await self.update_embed(song=song, ctx=ctx)
        vc = self.client.get_bot_voice_state(self.guild_id)

        if self.q_lock.locked():
            self.q_lock.release()

        while True:
            await self.play(song)
            self.timer_paused = None
            # Bot might have been kicked or lost connection to channel or was stopped
            if not vc or not vc.channel or self.state == MPStates.exit:
                break
            elif self.state == MPStates.on_next:  # return because button press
                return

            # continue automatic queue
            self.state = MPStates.on_next  # make sure to not react while loading song
            song = await self.queue.get_next_song()
            if not song:
                self.state = MPStates.exit
                break
            await self.update_embed(song=song)

        self.timer_empty = None
        self.timer_new_dj = None
        if vc and vc.channel:
            await vc.disconnect()
        try:
            await self.player_msg.edit(embed=self.get_empty_embed(title="STOPPED"), components=[])
        except NotFound:
            pass
        self.reset()

    async def play(self, song: MusicPlayerQueueSong):
        """Play a song

        :param song: A loaded MusicPlayerQueueSong
        """
        vc = self.client.get_bot_voice_state(self.guild_id)
        if not vc:  # sanity check
            await self.stop()
            return
        audio = AudioVolume(song.stream_url)
        audio.ffmpeg_before_args = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        # audio.locked_stream = song.duration == "Stream"  # livestream audio might lag
        self.state = MPStates.playing
        vc.volume = self.volume
        await vc.play(audio)

    async def update_embed(self, song: MusicPlayerQueueSong = None, ctx: ComponentContext = None):
        """Update the player embed

        :param song: the current song
        :param ctx: if this was triggered by a user, respond to it to make discord happy
        """
        vc = self.client.get_bot_voice_state(self.guild_id)
        if not song:
            song = self.queue.songs[self.queue.queue_pos]
        title = "Music Player" + (f" | {vc.channel.name}" if vc and vc.channel else "")
        title += " | Paused" if self.state == MPStates.paused else ""
        embed = Embed(title=title, description=f"**Current Song:**\n{song.title}", color=0x2983ef)
        embed.add_field(name="**Length**", value=song.duration, inline=True)
        embed.add_field(name="**Volume**", value=str(int(self.volume * 100)) + "%", inline=True)
        embed.add_field(name="**DJ**", value=self.dj.mention if self.dj else "-", inline=True)
        embed.add_field(name="**Video URL**", value=f"[Link]({song.video_url})", inline=True)
        if song.playlist_url:
            embed.add_field(name="**Playlist URL**", value=f"[Link]({song.playlist_url})", inline=True)
        embed.add_field(name="**Wiki**", value="[Link](https://github.com/deadkex/VoDiPy)", inline=True)
        embed.set_thumbnail(url=song.thumbnail)
        try:
            if ctx and not ctx.responded:
                try:
                    await ctx.edit_origin(embed=embed, components=self.create_components(song))
                except NotFound:  # responding took too long
                    await self.player_msg.edit(embed=embed, components=self.create_components(song))
            else:
                await self.player_msg.edit(embed=embed, components=self.create_components(song))
        except NotFound:  # the player message got deleted
            await self.stop()

    def create_components(self, current_song: MusicPlayerQueueSong = None):
        """Create the components for the player embed"""
        if not current_song:
            current_song = self.queue.songs[self.queue.queue_pos]

        options = []
        combo_num = self.queue.queue_pos - 4 if (self.queue.queue_pos - 4 >= 0 and len(self.queue.songs) >= 25) else 0
        for song in self.queue.songs[combo_num:combo_num + 25]:
            emoji = None
            if song.song_id == current_song.song_id:
                emoji = "🟢"
            elif song.error:
                emoji = "❌"
            options.append(SelectOption(label=song.title, value=str(song.song_id), description=song.desc, emoji=emoji))

        components: list[ActionRow] = [
            ActionRow(
                Select(
                    custom_id="player::select",
                    placeholder=f"Queue [{self.queue.queue_pos + 1}/{len(self.queue.songs)}]",
                    options=options
                )
            ),
            ActionRow(
                Button(
                    custom_id="player::pause",
                    style=ButtonStyles.GREEN,
                    label="Pause",
                    emoji="⏸"
                ) if self.state in [MPStates.loading, MPStates.playing, MPStates.on_next] else
                Button(
                    custom_id="player::play",
                    style=ButtonStyles.GREEN,
                    label="Play",
                    emoji="▶"
                ),
                Button(
                    custom_id="player::skip",
                    style=ButtonStyles.GREEN,
                    label="Skip",
                    emoji="⏭"
                ),
                Button(
                    custom_id="player::shuffle",
                    style=ButtonStyles.GREEN if self.queue.shuffle else ButtonStyles.GREY,
                    label="Shuffle",
                    emoji="🔀"
                )
            ),
            ActionRow(
                Button(
                    custom_id="player::lower",
                    style=ButtonStyles.GREEN,
                    emoji="➖"
                ),
                Button(
                    custom_id="player::higher",
                    style=ButtonStyles.GREEN,
                    emoji="➕"
                ),
                Button(
                    custom_id="player::move",
                    style=ButtonStyles.GREEN,
                    label="Move",
                    emoji="🚶‍♂️"
                ),
                Button(
                    custom_id="player::stop",
                    style=ButtonStyles.DANGER,
                    label="Stop",
                    emoji="⏹"
                ),
            )
        ]
        return components

    def get_empty_embed(self, title):
        """Get an empty embed at the start/end of the player cycle

        :param title: the title to use
        """
        song = self.queue.songs[self.queue.queue_pos]
        embed = Embed(title=f"Music Player | {title}", description="", color=0xffffff)
        if self.dj:
            embed.add_field(name="**DJ**", value=self.dj.mention, inline=True)
        embed.add_field(name="**Video URL**", value=f"[Link]({song.video_url})", inline=True)
        if song.playlist_url:
            embed.add_field(name="**Playlist URL**", value=f"[Link]({song.playlist_url})", inline=True)
        embed.add_field(name="**Wiki**", value="[Link](https://github.com/deadkex/VoDiPy)", inline=True)
        return embed

    async def acquire_and_can_continue(self):
        """Acquire the lock and check if the state is allowing continuation"""
        await self.q_lock.acquire()
        if self.state in [MPStates.exit, MPStates.ready]:
            self.q_lock.release()
            return False
        return True  # function/play_loop/stop release it

    def is_allowed(self, ctx: ComponentContext, restrict_to_dj=False):
        """A check to run on all user interactions

        :param ctx: the context
        :param restrict_to_dj: True: User has to be the dj or admin | False: User only has to be in the voice channel
        """
        if self.q_lock.locked() or self.state in [MPStates.exit, MPStates.on_next, MPStates.loading]:
            return False
        elif restrict_to_dj:
            return (self.dj and self.dj.id == ctx.author.id and MPSettings.leave_if_empty) \
                   or ctx.author.id in MPSettings.admin_user_ids
        else:
            return ctx.author.voice is not None and ctx.author.voice.channel is not None \
                   and ctx.author.voice.channel.id == ctx.voice_state.channel.id

    async def callback_select(self, ctx: ComponentContext):
        """Component callback: Select a song from the queue to play"""
        if not await self.acquire_and_can_continue():
            return
        song = await self.queue.get_song_with_song_id(int(ctx.values[0]), load_song=True, set_queue_pos_on_success=True)
        if song and not song.error:
            self.state = MPStates.on_next
            await ctx.voice_state.stop()
            await self.play_loop(song, ctx)
        else:
            self.q_lock.release()
            await ctx.send("The selected song is not available.", ephemeral=True)

    async def b_resume(self, ctx: ComponentContext):
        """Component callback: Resume the player"""
        self.timer_paused = None
        self.state = MPStates.playing
        if not ctx.voice_state.playing:
            ctx.voice_state.resume()
        await self.update_embed(ctx=ctx)

    async def b_pause(self, ctx: ComponentContext):
        """Component callback: Pause the player"""
        self.state = MPStates.paused
        if ctx.voice_state.playing:
            ctx.voice_state.pause()
        await self.update_embed(ctx=ctx)

        time = datetime.now()
        self.timer_paused = time
        await asyncio.sleep(MPSettings.timeout_paused)
        if self.timer_paused == time:
            await self.stop()

    async def b_skip(self, ctx: ComponentContext):
        """Component callback: Skip the current song"""
        if not await self.acquire_and_can_continue():
            return
        self.state = MPStates.on_next
        if song := await self.queue.get_next_song():
            await ctx.voice_state.stop()
            await self.play_loop(song, ctx)
            return
        await self.stop()

    async def b_shuffle(self, ctx: ComponentContext):
        """Component callback: Enable/Disable shuffle"""
        self.queue.shuffle = not self.queue.shuffle
        await self.update_embed(ctx=ctx)

    async def b_lower(self, ctx: ComponentContext):
        """Component callback: Lower the volume"""
        if self.volume > 0.1:
            self.volume = round(self.volume - 0.1, 1)
        elif self.volume > 0.02:
            self.volume = round(self.volume - 0.02, 2)
        ctx.voice_state.volume = self.volume
        await self.update_embed(ctx=ctx)

    async def b_higher(self, ctx: ComponentContext):
        """Component callback: Raise the volume"""
        if self.volume < 0.1:
            self.volume = round(self.volume + 0.02, 2)
        elif self.volume < MPSettings.max_volume:
            self.volume = round(self.volume + 0.1, 1)
        ctx.voice_state.volume = self.volume
        await self.update_embed(ctx=ctx)

    async def b_stop(self, ctx: ComponentContext):
        """Component callback: Stop the player"""
        await ctx.send("Stopping Musicbot...", ephemeral=True)
        await self.stop()

    async def b_move(self, ctx: ComponentContext):
        """Component callback: Move the bot to another voice channel"""
        if ctx.author.voice and ctx.author.voice.channel and ctx.author.voice.guild.id == ctx.voice_state.guild.id \
                and ctx.author.voice.channel.id != ctx.voice_state.channel.id:
            if not can_join_voice(ctx):
                await ctx.send(f"{ctx.author.mention} I have no permission to move to your voice channel!",
                               ephemeral=True)
                return
            self.timer_new_dj = None
            self.timer_paused = None
            try:
                await ctx.author.voice.channel.connect(deafened=True)
            except (VoiceConnectionTimeout, VoiceWebSocketClosed):
                await ctx.send(f"{ctx.author.mention} I have no permission to move to your voice channel!",
                               ephemeral=True)
                await self.stop()  # in this case the bot just disconnects from the old channel, so we have to stop
            else:
                await self.update_embed(ctx=ctx)
        else:
            await ctx.defer(edit_origin=True)
