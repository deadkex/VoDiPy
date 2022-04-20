# simple permission system
permissions = {
    # command is only allowed in these channels in this guild & slash command synced locally without 1h delay
    # not added here -> not restricted
    # nothing added here -> slash command globally synced
    # guild_id_a: [channel_id_a, channel_id_b],
    # guild_id_b: [],
}

# these people are allowed to use dj-restricted buttons (f.e. stop the bot)
admin_user_ids = [
    # user_id_a, user_id_b, ...
]

# these words can be used instead of a link
player_keywords = {
    "streams": "https://www.youtube.com/playlist?list=PL1GYPt1guOb_djy0HAVsZj3ZOXP9CvGVF",
    "test": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
}


class MusicPlayerSettings:
    message_command_prefix = "<"  # the prefix when using message commands -> '<play link'
    timeout_paused = 90  # seconds after which the player disconnects if paused
    timeout_empty = 60  # seconds after which the player disconnects if nobody is in the channel
    timeout_new_dj = 15  # seconds after which a new dj gets set if the current dj leaves
    leave_if_empty = True  # leave the channel if nobody is listening; False: Only admins can use stop & move
    warning_pl_count = 200  # warning if YouTube playlist is bigger than x
    no_playlist = True  # if video of a playlist is sent, use video
    starting_volume = 0.1  # 10% volume
    max_volume = 1.0  # 100% volume


# don't edit this
class MusicPlayerStates:
    ready = 0
    loading = 1
    playing = 2
    paused = 3
    on_next = 4  # skip & select
    exit = 5
