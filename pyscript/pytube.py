import os
import requests
import random
import asyncio
import glob
from datetime import datetime, timezone, timedelta

from file_manager import read_file_as_dict, write_dict_to_file, write_file, remove_file, create_folder
from utils import create_date_state

# PUT YOUR CHANGES HERE
__PYTUBE_BASE_URL = 'http://XX.XX.XX.XX:114'      # Base URL for your PyTube API server
__PYTUBE_CACHE_DAY = 30                           # Cache duration in days (30 days = 1 month). Songs won't be played until cache expires or playlist completes
__PYTUBE_TIME_OUT = 60                            # API request timeout in seconds

# App config
__PYTUBE_HEADER = { "Content-Type": "application/json" }
__PYTUBE_MP3_FOLDER = "/config/www/tts"
__PYTUBE_MEDIA_CACHE_FOLDER = '/config/pyscript/cache'
__PYTUBE_MEDIA_CACHE_FILE_PATH = f'{__PYTUBE_MEDIA_CACHE_FOLDER}/pytube_media_cache.json'
__PYTUBE_MIN_ACCEPT_TOTAL_SONG_IN_PLAYLIST = 2
__PYTUBE_MAX_ATTEMPT = 5

class __MediaPlayerStatus:
    OFF = "off"                     # The media player is turned off and is not accepting commands until turned on
    ON = "on"                       # The media player is turned on, but no details on its state are currently known
    IDLE = "idle"                   # The media player is turned on and accepting commands, but currently not playing any media
    PLAYING = "playing"             # The media player is currently playing media
    PAUSED = "paused"               # The media player has an active media and is currently paused
    BUFFERING = "buffering"         # The media player is preparing to start playbook of media
    UNAVAILABLE = "unavailable"     # The entity is currently unavailable
    UNKNOWN = "unknown"             # The state is not yet known

class __MediaPlayer:
    def __init__(
        self, 
        entity_id: str = "",
        status: __MediaPlayerStatus = __MediaPlayerStatus.OFF,
        song_play_index: int = 0,
        playing_current_time: int = 0,
        playing_remaining_time: int = 0,
        playing_attempt: int = 0,
        playlist_url: str = "",
        playlist: list = None,
        original_playlist: list = None,
        seek_position: float = None,
        play_time_check: bool = False,
        shuffle: bool = False
    ):
        self.entity_id = entity_id
        self.status = status
        self.song_play_index = song_play_index
        self.playing_current_time = playing_current_time
        self.playing_remaining_time = playing_remaining_time
        self.playing_attempt = playing_attempt
        self.seek_position = seek_position
        self.playlist_url = playlist_url
        self.playlist = playlist if playlist is not None else []
        self.original_playlist = original_playlist if original_playlist is not None else [] 
        self.play_time_check = play_time_check
        self.shuffle = shuffle
        self.listener_task = None  # Task for the individual listener
        self.is_listening = False  # Flag to track if listener is running

    def restore(self):
        try:
            dict = self.get_player_info()
            if dict != {}:
                self.status = dict.get("status", self.status)
                self.song_play_index = dict.get("song_play_index", self.song_play_index)
                self.playing_current_time = dict.get("playing_current_time", self.playing_current_time)
                self.playing_remaining_time = dict.get("playing_remaining_time", self.playing_remaining_time)
                self.playing_attempt = dict.get("playing_attempt", self.playing_attempt)
                self.seek_position = dict.get("seek_position", self.seek_position)
                self.play_time_check = dict.get("play_time_check", self.play_time_check)
                self.shuffle = dict.get("shuffle", self.shuffle)
                self.playlist_url = dict.get("playlist_url", self.playlist_url)
                self.playlist = dict.get("playlist", self.playlist)
                self.original_playlist = dict.get("original_playlist", self.original_playlist)
                self.is_listening = dict.get("is_listening", self.is_listening)
        except Exception as e:
            log.error(f"❌ [MediaPlayer][restore][{self.entity_id}] Exception occurred: {e}")

    def get_cache_file_path(self) -> str:
        return f"{__PYTUBE_MEDIA_CACHE_FOLDER}/{self.entity_id}.json"

    def get_player_info(self) -> dict:
        try:
            cache_file = self.get_cache_file_path()
            return read_file_as_dict(cache_file)
        except Exception as e:
            return {}
    
    def update_play_status(
        self,
        status: __MediaPlayerStatus = None,
        song_play_index: int = None,
        playing_current_time: int = None,
        playing_remaining_time: int = None,
        playing_attempt: int = None,
        playlist_url: str = None,
        playlist: list = None,
        original_playlist: list = None,
        seek_position: float = None,
        play_time_check: bool = None,
        shuffle: bool = None,
        save_to_cache: bool = True
    ):
        __status = status if status is not None else self.status
        state.set(self.entity_id, __status)

        __song_play_index = song_play_index if song_play_index is not None else self.song_play_index
        __playing_current_time = playing_current_time if playing_current_time is not None else self.playing_current_time
        __playing_remaining_time = playing_remaining_time if playing_remaining_time is not None else self.playing_remaining_time
        __playing_attempt = playing_attempt if playing_attempt is not None else self.playing_attempt        
        __seek_position = seek_position if seek_position is not None else self.seek_position
        __play_time_check = play_time_check if play_time_check is not None else self.play_time_check
        __shuffle = shuffle if shuffle is not None else self.shuffle
        __playlist_url = playlist_url if playlist_url is not None else self.playlist_url
        __playlist = playlist if playlist is not None else self.playlist
        __original_playlist = original_playlist if original_playlist is not None else self.original_playlist

        # Update instance variables with new values
        self.status = __status
        self.song_play_index = __song_play_index
        self.playing_current_time = __playing_current_time
        self.playing_remaining_time = __playing_remaining_time
        self.playing_attempt = __playing_attempt
        self.playlist_url = __playlist_url
        self.playlist = __playlist
        self.original_playlist = __original_playlist
        self.seek_position = __seek_position
        self.shuffle = __shuffle
        self.play_time_check = __play_time_check

        try:
            pytube_media_player_attribute = {
                "entity_id": self.entity_id,
                "status": self.status,
                "song_play_index": self.song_play_index,
                "playing_current_time": self.playing_current_time,
                "playing_remaining_time": self.playing_remaining_time,
                "playing_attempt": self.playing_attempt,
                "seek_position": self.seek_position,
                "play_time_check": self.play_time_check,
                "shuffle": self.shuffle,
                "playlist_url": self.playlist_url,
                "is_listening": self.is_listening,
                "last_time_update": create_date_state()
            }

            if save_to_cache:
                # Write to dict if need
                cache_file = self.get_cache_file_path()
                copied_pytube_media_player_attribute = pytube_media_player_attribute.copy()
                copied_pytube_media_player_attribute["playlist"] = self.playlist
                copied_pytube_media_player_attribute["original_playlist"] = self.original_playlist
                write_dict_to_file(cache_file, copied_pytube_media_player_attribute)

                # Update state
                original_media_player_attribute = state.getattr(self.entity_id)
                original_media_player_attribute.update(pytube_media_player_attribute)
                state.set(f"{self.entity_id}_pytube", self.status, original_media_player_attribute)

        except Exception as e:
            log.error(f"❌ [MediaPlayer][update_play_status][{self.entity_id}] Exception occurred: {e}")

    def is_playing(self) -> bool:
        try:
            media_player_info = self.get_player_info()
            return __MediaPlayerStatus.PLAYING == media_player_info.get("status", "")
        except Exception as e:
            log.error(f"❌ [MediaPlayer][is_playing][{self.entity_id}] Exception occurred: {e}")
            return False

    def should_go_next_song(self) -> bool:
        # Reject incase the media player's status is buffering or playing. However, its `media_duration` is None 
        if self.playing_current_time == 0 and self.playing_remaining_time == 0:
            return False

        if self.is_playing() and self.playing_remaining_time < 5:
            self.update_play_status(
                status = __MediaPlayerStatus.BUFFERING
            )
            return True

        return False

    def current_playing_video(self) -> dict:
        try:
            if self.is_playing:
                total_video = len(self.playlist)
                if self.song_play_index >= 0 or self.song_play_index < total_video:
                    return self.playlist[self.song_play_index]
                return {}
            else:
                return None
        except Exception as e:
            log.error(f"❌ [MediaPlayer][is_playing][{self.entity_id}] Exception occurred: {e}")
            return None

    def reload(self):
        try:
            media_state = state.get(self.entity_id)
            media_title = ""
            try:
                media_title = state.get(f"{self.entity_id}.media_title")
                pytube_media_title = state.get(f"{self.entity_id}_pytube.media_title")
                if media_state == __MediaPlayerStatus.PLAYING and self.status == __MediaPlayerStatus.PAUSED and media_title == pytube_media_title:
                    self.update_play_status(
                        status = __MediaPlayerStatus.PLAYING,
                    )
            except Exception as e:
                ""
                #log.warning(f"[Pytube][update_status][{self.entity_id}] Exception occurred: {e}")

            if self.is_playing() == False:
                return

            if media_state == __MediaPlayerStatus.OFF or media_state == __MediaPlayerStatus.UNAVAILABLE:
                log.warning(f"[Pytube][update_status][{self.entity_id}] The media player is {media_state}. Stopped!")
                self.update_play_status(
                    status = __MediaPlayerStatus.OFF,
                    playlist = []
                )
                self.stop_listener()
                __MediaPlayerManager.remove_media_player_sync(entity_id = self.entity_id)
                return
            elif media_state == __MediaPlayerStatus.PAUSED:
                log.info(f"[Pytube][update_status][{self.entity_id}] The media player is paused.")
                self.update_play_status(
                    status = __MediaPlayerStatus.PAUSED,
                )
                return

            now = datetime.now(timezone.utc)

            try:
                media_duration = state.get(f"{self.entity_id}.media_duration")
            except Exception as e:
                media_duration = None

            try:
                media_position = state.get(f"{self.entity_id}.media_position")
            except Exception as e:
                media_position = None

            try:
                media_position_updated_at = state.get(f"{self.entity_id}.media_position_updated_at")
            except Exception as e:
                media_position_updated_at = None

            if media_duration is None or media_position is None or media_position_updated_at is None:
                log.warning(f"[Pytube][update_status][{self.entity_id}] Exception occurred when getting info from media player. Details: media_duration = {media_duration}, media_position = {media_position}, media_position_updated_at = {media_position_updated_at}")
                self.update_play_status(
                    playing_current_time = 0,
                    playing_remaining_time = 0
                )
                return

            media_playing_time = now - media_position_updated_at
            elapsed_since_update = media_playing_time.total_seconds()
            media_playing_current_time = media_position + elapsed_since_update
            media_playing_remaining_time = media_duration - media_playing_current_time

            self.update_play_status(
                playing_current_time = media_playing_current_time,
                playing_remaining_time = media_playing_remaining_time
            )

            log.info(f"[Pytube][update_status][{self.entity_id}] {media_title}. Current position = {media_playing_current_time:.1f}, Remaining time = {media_playing_remaining_time:.1f}")        
        except Exception as e:
            log.error(f"❌ [Pytube][update_status][{self.entity_id}] Exception occurred: {e}")

    def start_listener(self):
        if not self.is_listening:
            self.is_listening = True
            log.info(f"[Pytube][start_listener][{self.entity_id}] Individual listener started.")

    def stop_listener(self):
        if self.is_listening:
            self.is_listening = False
            log.info(f"[Pytube][stop_listener][{self.entity_id}] Individual listener stopped.")


__pytube_media_player_list: dict = {}

class __MediaPlayerManager:
    @staticmethod
    def get_media_player_list_from_cache() -> list:
        try:
            pattern = os.path.join(__PYTUBE_MEDIA_CACHE_FOLDER, f"media_player.*.json")
            matches = glob.glob(pattern)
            # Remove path and .json extension, keep media_player. prefix
            return [os.path.basename(match)[:-5] for match in matches]  # Remove last 5 characters (.json)
        except Exception as e:
            log.warning(f"[Pytube][get_cache_file_path] Exception occurred: {e}")
            return []

    @staticmethod
    def get_all_media_players() -> dict:
        # Load from cache if need
        if __pytube_media_player_list == {}:
            for entity_id in __MediaPlayerManager.get_media_player_list_from_cache():
                new_media_player = __MediaPlayer(entity_id=entity_id)
                new_media_player.restore()
                __pytube_media_player_list[entity_id] = new_media_player
        return __pytube_media_player_list

    @staticmethod
    def get_media_player_list() -> list:
        all_media_players = __MediaPlayerManager.get_all_media_players()
        return list(all_media_players.values())

    @staticmethod
    def get_media_player(entity_id: str) -> __MediaPlayer:
        all_media_players = __MediaPlayerManager.get_all_media_players()
        if entity_id not in all_media_players:
            all_media_players[entity_id] = __MediaPlayer(entity_id=entity_id)
            log.info(f"[Pytube][get_media_player][{entity_id}] Added media player... {entity_id} -- {__MediaPlayerManager.get_entity_id_list()}")
        return all_media_players.get(entity_id)

    def get_entity_id_list() -> list:
        all_media_players = __MediaPlayerManager.get_all_media_players()
        return list(all_media_players.keys())

    @staticmethod
    def remove_media_player_sync(entity_id: str) -> bool:
        log.info(f"[Pytube][remove_media_player_sync][{entity_id}] Removing media player...")
        all_media_players = __MediaPlayerManager.get_all_media_players()
        remove_result = False
        if entity_id in all_media_players:
            # Stop the individual listener before removing
            media_player = all_media_players[entity_id]
            media_player.stop_listener()
            # Remove cache file
            cache_path = media_player.get_cache_file_path()
            remove_file(cache_path)
            # Remove referrence
            del all_media_players[entity_id]
            remove_result = True
        log.info(f"[Pytube][remove_media_player_sync][{entity_id}] Removing media player... {remove_result} -- {__MediaPlayerManager.get_entity_id_list()}")
        return remove_result

    @staticmethod
    async def remove_media_player(entity_id: str) -> bool:
        log.info(f"[Pytube][remove_media_player][{entity_id}] Removing media player...")
        all_media_players = __MediaPlayerManager.get_all_media_players()
        remove_result = False
        if entity_id in all_media_players:
            # Stop the individual listener before removing
            media_player = all_media_players[entity_id]
            media_player.stop_listener()
            del all_media_players[entity_id]
            remove_result = True
        log.info(f"[Pytube][remove_media_player][{entity_id}] Removing media player... {remove_result} -- {__MediaPlayerManager.get_entity_id_list()}")
        return remove_result


class __MediaService:
    @staticmethod
    def get_playlist(
        entity_id: str,
        playlist_url: str
    ): 
        url = f'{__PYTUBE_BASE_URL}/v3/playlist?url={playlist_url}&device={entity_id}'
        try:
            response = task.executor(requests.get, url, headers=__PYTUBE_HEADER, timeout=__PYTUBE_TIME_OUT)
            if response.status_code == 200:
                return response.json()
            else:
                log.error(f"❌ [Pytube][get_playlist] Failed with status {response.status_code}: {response.text}")
                return None
        except Exception as e:
            log.error(f"❌ [Pytube][get_playlist] Exception occurred: {e}")
            return None

    @staticmethod
    def get_video_info(
        entity_id: str,
        video_id: str
    ):
        log.info(f"[Pytube][get_video_info] Getting video info with id={video_id}....")
        return __MediaService.__get_video_info_v3(entity_id, video_id)

    @staticmethod
    def download_mp3_file(
        mp3_path: str
    ):
        url = f'{__PYTUBE_BASE_URL}/{mp3_path}'
        try:
            response = task.executor(requests.get, url, headers=__PYTUBE_HEADER, timeout=__PYTUBE_TIME_OUT)
            if response.status_code == 200:
                return response.content
            else:
                return None
        except Exception as e:
            log.error(f"❌ [Pytube][download_mp3_file] Exception occurred: {e}")
            return None

    @staticmethod
    def __get_video_info_v2(
        entity_id: str,
        video_id: str
    ):
        url = f'{__PYTUBE_BASE_URL}/v2/video/{video_id}?device={entity_id}'
        try:
            response = task.executor(requests.get, url, headers=__PYTUBE_HEADER, timeout=15)
            if response.status_code == 200:
                return response.json()
            else:
                log.error(f"❌ [Pytube][__get_video_info_v2] Failed with status {response.status_code}: {response.text}")
                return None
        except Exception as e:
            log.error(f"❌ [Pytube][__get_video_info_v2] Exception occurred: {e}")
            return None

    @staticmethod
    def __get_video_info_v3(
        entity_id: str,
        video_id: str
    ):
        url = f'{__PYTUBE_BASE_URL}/v3/video/{video_id}?device={entity_id}'
        try:
            response = task.executor(requests.get, url, headers=__PYTUBE_HEADER, timeout=__PYTUBE_TIME_OUT)
            if response.status_code == 200:
                return response.json()
            else:
                log.error(f"❌ [Pytube][__get_video_info_v3] Failed with status {response.status_code}: {response.text}")
                return None
        except Exception as e:
            log.error(f"❌ [Pytube][__get_video_info_v3] Exception occurred: {e}")
            return None

def __is_more_than_days(
    initial_date_str: str, 
    days: float = __PYTUBE_CACHE_DAY
):
    if initial_date_str is None:
        return True

    try:
        initial_date = datetime.strptime(initial_date_str, '%Y-%m-%d %H:%M:%S') 
        today = datetime.now()
        difference = abs(today - initial_date)
        return difference >= timedelta(days=days)
    except Exception as e:
        return True

async def __pytube_play(
    entity_id: str,
    video_id: str,
    video_title: str,
    video_thumnnail: str,
    mp3_path: str
):
    pytube_media_player = __MediaPlayerManager.get_media_player(entity_id = entity_id)
    try:
        file_name = f'{entity_id}_stream_video.mp3'
        file_path = f'{__PYTUBE_MP3_FOLDER}/{file_name}'
        media_content_id = f'/local/tts/{file_name}'
        os.makedirs(__PYTUBE_MP3_FOLDER, exist_ok=True)
        try:
            os.remove(file_path)
        except Exception as e:
            log.warning(f"[Pytube][__pytube_play][{entity_id}] Exception occurred: {e}")

        log.info(f"[Pytube][__pytube_play][{entity_id}] Downloading song... {video_id}/{video_title}")
        data = __MediaService.download_mp3_file(
            mp3_path = mp3_path
        )
        
        if data is None:
            log.error(f"❌ [Pytube][__pytube_play][{entity_id}] Downloading song error. Reason: Unknown. Mp3 path: {mp3_path}")
            return False
        else:
            log.info(f"[Pytube][__pytube_play][{entity_id}] Downloading song... Success -- {video_id}/{video_title}")
            write_file(data, file_path)

            state.set(f"{entity_id}", __MediaPlayerStatus.BUFFERING)
            await asyncio.sleep(1)
            await hass.services.async_call(
                "media_player", 
                "play_media",
                {
                    "entity_id": entity_id,
                    "media_content_id": media_content_id,
                    "media_content_type": "audio/mpeg",
                    "announce": True,
                    "extra": {
                        "title": video_title,
                        "thumb": video_thumnnail
                    }
                }
            )
            return True
    except Exception as e:
        log.error(f"❌ [Pytube][__pytube_play][{entity_id}] Exception occurred: {e}")
        return False
    return False

async def __pytube_goto_song_at_index(
    entity_id: str,
    song_index: int
):
    pytube_media_player = __MediaPlayerManager.get_media_player(entity_id)
    try:
        seek_position = pytube_media_player.seek_position
        playlist_size = len(pytube_media_player.playlist)

        pytube_media_player.update_play_status(
            status = __MediaPlayerStatus.BUFFERING,
            playing_current_time = 0,
            playing_remaining_time = 0
        )


        if playlist_size == 0:
            pytube_media_player.song_play_index = 0
            log.error(f"❌ [Pytube][__pytube_goto_song_at_index][{entity_id}] Playlist if empty")
            return False

        if song_index >= playlist_size:
            log.error(f"❌ [Pytube][__pytube_goto_song_at_index][{entity_id}] Reach end of playlist. {song_index}/{playlist_size}")
            return False

        pytube_media_player.song_play_index = song_index
        playlist_item = pytube_media_player.playlist[song_index]
        video_id = playlist_item["video_id"]
        video_info = __MediaService.get_video_info(
            entity_id = entity_id,
            video_id = video_id
        )
        log.info(f"[Pytube][__pytube_goto_song_at_index][{entity_id}] video_info = {video_info}")

        if video_info is None:
            log.error(f"❌ [Pytube][__pytube_goto_song_at_index][{entity_id}] Error when getting the video info. Reason: video_info = None")
            return False


        video_title = video_info["video_title"]
        video_thumbnail_url = video_info["video_thumbnail_url"]
        mp3_path = video_info["mp3_url"]
        is_loaded_from_cache = video_info["is_loaded_from_cache"]

        video_title = f"[{song_index + 1}/{playlist_size}] {video_title}"
        if is_loaded_from_cache == True:
            video_title = f"♻️ {video_title}"
        else:
            video_title = f"📥 {video_title}"

        result = await __pytube_play(
                entity_id = entity_id,
                video_id = video_id,
                video_title = video_title,
                video_thumnnail = video_thumbnail_url,
                mp3_path = mp3_path
            )

        if result:
            # seek to position if needed
            if seek_position is not None and seek_position > 0:
                # Delay time, the media player need to time to load mp3 file
                await asyncio.sleep(2)
                await hass.services.async_call(
                    "media_player", 
                    "media_seek",
                    {
                        "entity_id": entity_id,
                        "seek_position": seek_position
                    }
                )

            pytube_media_player.update_play_status(
                status = __MediaPlayerStatus.PLAYING,
                seek_position = 0,
                playing_attempt = 0
            )

        return result  
    except Exception as e:
        log.error(f"❌ [Pytube][__pytube_goto_song_at_index][{entity_id}] Exception occurred: {e}")
        return False


async def __pytube_next_song(
    entity_id: str
):
    pytube_media_player = __MediaPlayerManager.get_media_player(entity_id)

    song_index = pytube_media_player.song_play_index
    play_time_check = pytube_media_player.play_time_check
    playing_attempt = pytube_media_player.playing_attempt
    playlist = pytube_media_player.playlist

    next_song_index = (song_index + 1)
    try:
        if next_song_index < len(playlist):
            song_info = playlist[next_song_index]
            video_id = song_info["video_id"]

            result = await __pytube_goto_song_at_index(
                entity_id = entity_id,
                song_index = next_song_index
            )

            if not result:
                if playing_attempt < __PYTUBE_MAX_ATTEMPT:
                    log.warning(f"[Pytube][__pytube_next_song][{entity_id}] 1. Exception occurred (video_id = {video_id}). Continuing play next song.... Attempt: {playing_attempt}/{__PYTUBE_MAX_ATTEMPT}")
                    await asyncio.sleep(1)
                    pytube_media_player.update_play_status(
                        song_play_index = next_song_index,
                        playing_attempt = playing_attempt + 1
                    )
                    task.create(__pytube_next_song(entity_id = entity_id))
                else:
                    log.error(f"❌ [Pytube][__pytube_next_song][{entity_id}] 1. Reached max retries. Stopped!!! {playing_attempt}/{__PYTUBE_MAX_ATTEMPT}")
                    pytube_media_player.update_play_status(
                        status = __MediaPlayerStatus.OFF,
                        playlist = []
                    )
                    await __MediaPlayerManager.remove_media_player(entity_id = entity_id)
            else:
                pytube_media_player.update_play_status(
                    playing_attempt = 0
                )

            # Write cache
            media_played_song_cache = read_file_as_dict(__PYTUBE_MEDIA_CACHE_FILE_PATH)
            media_played_song_cache[video_id] = create_date_state()
            write_dict_to_file(__PYTUBE_MEDIA_CACHE_FILE_PATH, media_played_song_cache)
        else:
            log.warning(f"[Pytube][__pytube_next_song][{entity_id}] Reached the last video in playlist: {next_song_index}/{len(playlist)}. Reloading playlist...")
            await pytube_play_playlist(
                entity_id = entity_id,
                playlist_url = pytube_media_player.playlist_url,
                is_shuffle = pytube_media_player.shuffle,
                play_time_check = pytube_media_player.play_time_check
            )

    except Exception as e:
        log.error(f"❌ [Pytube][__pytube_next_song][{entity_id}] Reached max retries. Stopped!!! Exception: {e}")
        pytube_media_player.update_play_status(
            status = __MediaPlayerStatus.OFF,
            playlist = []
        )
        await __MediaPlayerManager.remove_media_player(entity_id = entity_id)


# Global time trigger that checks all active media players
@time_trigger('period(now, 5s)')
def pytube_individual_listeners():
    try:
        media_player_list = __MediaPlayerManager.get_media_player_list()
        active_count = 0

        for pytube_media_player in media_player_list:
            if pytube_media_player.is_listening:
                active_count += 1
                pytube_media_player.reload()
                
                # Check if this media player needs to go to next song
                if pytube_media_player.should_go_next_song():
                    entity_id = pytube_media_player.entity_id
                    log.info(f"[Pytube][pytube_individual_listeners][{entity_id}] ######## Creating next song task...")
                    # Use task.create to run the async function properly
                    task.create(__pytube_next_song(entity_id))
        
        # Log active status occasionally for debugging
        if active_count > 0:
            log.debug(f"[Pytube][pytube_individual_listeners] Checked {active_count} active media players")
            
    except Exception as e:
        log.error(f"❌ [Pytube][pytube_individual_listeners] Exception occurred: {e}")

@service
async def pytube_play_playlist(
    entity_id: str,
    playlist_url: str,
    is_shuffle: bool = True,
    play_time_check = True
):
    # Create the cache folder
    create_folder(__PYTUBE_MEDIA_CACHE_FOLDER)

    pytube_media_player = __MediaPlayerManager.get_media_player(entity_id)
    
    pytube_media_player.update_play_status(
        status = __MediaPlayerStatus.BUFFERING,
        playing_attempt = 0
    )

    log.info(f"[Pytube][pytube_play_playlist][{entity_id}] Playing...")

    original_playlist = __MediaService.get_playlist(
        entity_id = entity_id,
        playlist_url = playlist_url
    )

    if original_playlist is None or original_playlist == []:
        log.error(f"❌ [Pytube][pytube_play_playlist][{entity_id}] Cannot load the playlist: {playlist_url}")
        pytube_media_player.update_play_status(
            status = __MediaPlayerStatus.OFF,
            original_playlist = []
        )
        await __MediaPlayerManager.remove_media_player(entity_id = entity_id)
        return

    total_songs = len(original_playlist)

    # Filter the valid videos if `play_time_check` is enabled
    if play_time_check:
        new_original_playlist = []
        media_played_song_cache = read_file_as_dict(__PYTUBE_MEDIA_CACHE_FILE_PATH)

        for item in original_playlist:
            video_id = item.get("video_id", "")
            media_played_time = media_played_song_cache.get(video_id)
            is_more_than_days = __is_more_than_days(initial_date_str = media_played_time)
            if is_more_than_days:
                new_original_playlist.append(item)

        if len(new_original_playlist) >= __PYTUBE_MIN_ACCEPT_TOTAL_SONG_IN_PLAYLIST:
            original_playlist = new_original_playlist
        else:
            log.warning(f"[Pytube][pytube_play_playlist][{entity_id}][play_time_check=True] The playlist is smaller than {__PYTUBE_MIN_ACCEPT_TOTAL_SONG_IN_PLAYLIST} songs => Load the original playlist now")
            for item in original_playlist:
                video_id = item.get("video_id", "")
                if video_id in media_played_song_cache:
                    del media_played_song_cache[video_id]
            write_dict_to_file(__PYTUBE_MEDIA_CACHE_FILE_PATH, media_played_song_cache)

    # Shuffle
    playlist = original_playlist.copy()
    if is_shuffle:
        random.shuffle(playlist)

    pytube_media_player.update_play_status(
        playlist_url = playlist_url,
        playlist = playlist,
        original_playlist = original_playlist,
        play_time_check = play_time_check,
        shuffle = is_shuffle,
        song_play_index = -1
    )

    log.info(f"[Pytube][pytube_play_playlist][{entity_id}] Playing {len(playlist)}/{total_songs} songs in playlist: {playlist_url}")

    # Start the individual listener for this media player
    pytube_media_player.start_listener()

    task.create(__pytube_next_song(
        entity_id = entity_id
    ))

@service
async def pytube_shuffle_toggle(
    entity_id: str
):
    log.info(f"[Pytube][pytube_shuffle_toggle][{entity_id}] Shuffling...")
    pytube_media_player = __MediaPlayerManager.get_media_player(entity_id = entity_id)

    if pytube_media_player.status == __MediaPlayerStatus.BUFFERING:
        log.warning(f"[Pytube][shuffle_toggle][{entity_id}] Cannot do the action. Reason: pytube_media_player.status = buffering")
        return

    current_video = pytube_media_player.current_playing_video()
    
    if current_video is None:
        log.warning(f"[Pytube][shuffle_toggle][{entity_id}] Cannot do the action. Reason: is_playing == False")
        return

    if len(pytube_media_player.original_playlist) <= 0:
        log.warning(f"[Pytube][shuffle_toggle][{entity_id}] Cannot do the action. Reason: Playlist is empty")
        return

    original_playlist = pytube_media_player.original_playlist.copy()

    # Shuffle playlist if need
    should_shuffle = not pytube_media_player.shuffle
    if should_shuffle:
        random.shuffle(original_playlist)

    # Creating a new playlist by following:
    # - Insert the playing video in the top of new playlist
    # - Check from cache if the video is already played => remove from the list

    new_original_playlist = []
    new_original_playlist.append(current_video)
    current_video_id = current_video.get("video_id", "")
    media_played_song_cache = read_file_as_dict(__PYTUBE_MEDIA_CACHE_FILE_PATH)
    
    for item in original_playlist:
        video_id = item.get("video_id", "")
        if video_id != current_video_id:
            media_played_time = media_played_song_cache.get(video_id)
            is_more_than_days = __is_more_than_days(initial_date_str = media_played_time)
            if is_more_than_days and video_id != current_video_id:
                new_original_playlist.append(item)

    pytube_media_player.update_play_status(
        playlist = new_original_playlist,
        shuffle = should_shuffle,
        song_play_index = 0
    )

    total_songs = len(original_playlist)
    log.info(f"[Pytube][shuffle_toggle][{entity_id}] Shuffle = {pytube_media_player.shuffle}. Playing {len(new_original_playlist)}/{total_songs} songs in playlist")

@service
async def pytube_next_song(
    entity_id: str
):
    log.info(f"[Pytube][pytube_next_song][{entity_id}] Next song...")

    pytube_media_player = __MediaPlayerManager.get_media_player(entity_id = entity_id)

    if pytube_media_player.status == __MediaPlayerStatus.BUFFERING:
        log.warning(f"[Pytube][pytube_next_song][{entity_id}] Cannot go next song. Reason: pytube_media_player.status = buffering")
        return

    current_entity_id = pytube_media_player.entity_id
    if entity_id != current_entity_id:
        log.warning(f"[Pytube][pytube_next_song][{entity_id}] Cannot go next song. Reason: {entity_id} != {current_entity_id}")
        return

    is_playing = pytube_media_player.is_playing()
    if not is_playing:
        log.warning(f"[Pytube][pytube_next_song][{entity_id}] Cannot go next song. Reason: is_playing == False")
        return

    await hass.services.async_call(
            "media_player", 
            "media_pause",
            {
                "entity_id": entity_id
            }
        )

    await __pytube_next_song(entity_id=entity_id)

@service
async def pytube_pause(
    entity_id: str
):    
    log.info(f"[Pytube][pytube_pause][{entity_id}] Pausing...")

    pytube_media_player = __MediaPlayerManager.get_media_player(entity_id)

    try:
        is_playing = pytube_media_player.is_playing()
        playing_current_time = pytube_media_player.playing_current_time

        if not is_playing:
            log.warning(f"[Pytube][pytube_pause][{entity_id}] Cannot pause the song. Reason: The media player is not playing")
            return

        pytube_media_player.update_play_status(
            seek_position = playing_current_time - 5,
            playing_attempt = 0
        )

        await hass.services.async_call(
            "media_player", 
            "media_pause",
            {
                "entity_id": entity_id
            }
        )

        log.info(f"[Pytube][pytube_pause][{entity_id}] ########## Paused! Current time = {playing_current_time}")
    except Exception as e:
        log.error(f"❌ [Pytube][pytube_pause][{entity_id}] Exception occurred: {e}")
        pytube_media_player.update_play_status(
            status = __MediaPlayerStatus.OFF,
            playlist = []
        )
        await __MediaPlayerManager.remove_media_player(entity_id = entity_id)

@service
async def pytube_resume(
    entity_id: str
):
    log.info(f"[Pytube][pytube_resume][{entity_id}] Resumming...")

    pytube_media_player = __MediaPlayerManager.get_media_player(entity_id)

    current_entity_id = pytube_media_player.entity_id
    if entity_id != current_entity_id:
        log.warning(f"❌ [Pytube][pytube_resume][{entity_id}] Cannot resume the song. Reason: {entity_id} != {current_entity_id}")
        return

    playlist = pytube_media_player.playlist
    song_play_index = pytube_media_player.song_play_index
    seek_position = pytube_media_player.seek_position

    if playlist != [] and song_play_index >= 0:
        log.info(f"[Pytube][pytube_resume][{entity_id}] Seeking to: {seek_position}")
        
        if seek_position < 0:
            seek_position = 0

        pytube_media_player.update_play_status(
            status = __MediaPlayerStatus.BUFFERING,
            seek_position = seek_position,
            playing_attempt = 0
        )

        # Start listener if it's not running
        if not pytube_media_player.is_listening:
            pytube_media_player.start_listener()

        task.create(__pytube_goto_song_at_index(
            entity_id = entity_id,
            song_index = song_play_index
        ))
    else:
        log.warning(f"[Pytube][pytube_resume][{entity_id}] Cannot resume media player. song_play_index = {song_play_index}, playlist size = {len(playlist)}")

@service
async def pytube_stop(
    entity_id: str
):
    log.info(f"[Pytube][pytube_stop][{entity_id}] Stopping...")
    pytube_media_player = __MediaPlayerManager.get_media_player(entity_id)
    
    try:
        # Stop the media player
        await hass.services.async_call(
            "media_player", 
            "media_stop",
            {
                "entity_id": entity_id
            }
        )
        
        # Update status and clear playlist
        pytube_media_player.update_play_status(
            status = __MediaPlayerStatus.OFF,
            playlist = [],
            song_play_index = 0,
            playing_current_time = 0,
            playing_remaining_time = 0,
            seek_position = None
        )
        
        # Remove from manager (this will also stop the listener)
        __MediaPlayerManager.remove_media_player_sync(entity_id = entity_id)
        
        log.info(f"[Pytube][pytube_stop][{entity_id}] Stopped successfully")
        
    except Exception as e:
        log.error(f"❌ [Pytube][pytube_stop][{entity_id}] Exception occurred: {e}")

@service
async def pytube_stop_all():
    log.info(f"[Pytube][pytube_stop_all] Stopping all media players...")
    
    try:
        # Get a copy of the entity IDs to avoid modifying dict during iteration
        entity_ids = list(__pytube_media_player_list.keys())
        
        for entity_id in entity_ids:
            await pytube_stop(entity_id)
            
        log.info(f"[Pytube][pytube_stop_all] All media players stopped")
        
    except Exception as e:
        log.error(f"❌ [Pytube][pytube_stop_all] Exception occurred: {e}")

@service 
async def pytube_get_status(
    entity_id: str = None
):
    if entity_id:
        # Get status for specific media player
        if entity_id in __pytube_media_player_list:
            media_player = __pytube_media_player_list[entity_id]
            status = {
                "entity_id": media_player.entity_id,
                "status": media_player.status,
                "is_listening": media_player.is_listening,
                "song_play_index": media_player.song_play_index,
                "playlist_size": len(media_player.playlist),
                "playing_current_time": media_player.playing_current_time,
                "playing_remaining_time": media_player.playing_remaining_time,
                "shuffle": media_player.shuffle,
                "playlist_url": media_player.playlist_url
            }
            log.info(f"[Pytube][pytube_get_status][{entity_id}] Status: {status}")
            return status
        else:
            log.warning(f"[Pytube][pytube_get_status][{entity_id}] Media player not found")
            return None
    else:
        # Get status for all media players
        all_status = {}
        for entity_id, media_player in __pytube_media_player_list.items():
            all_status[entity_id] = {
                "entity_id": media_player.entity_id,
                "status": media_player.status,
                "is_listening": media_player.is_listening,
                "song_play_index": media_player.song_play_index,
                "playlist_size": len(media_player.playlist),
                "playing_current_time": media_player.playing_current_time,
                "playing_remaining_time": media_player.playing_remaining_time,
                "shuffle": media_player.shuffle,
                "playlist_url": media_player.playlist_url
            }
        log.info(f"[Pytube][pytube_get_status] All Status: {all_status}")
        return all_status

@service
async def pytube_play_playlist_test():
    await pytube_play_playlist(
        entity_id = "media_player.family_room_speaker",
        playlist_url = "https://music.youtube.com/playlist?list=PLM8mlc5hM62hfq9WsRCfkiCyFFSHVdLbp&si=0s6Fw9Kp2O_-LXj_"
    )