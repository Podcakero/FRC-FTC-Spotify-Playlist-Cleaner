import os
import streamlit as st
import toml

from spotipy import Spotify
from spotipy.cache_handler import CacheHandler
from spotipy.exceptions import SpotifyOauthError
from spotipy.oauth2 import SpotifyOAuth

config = toml.load("./config.toml")

class StreamlitCacheHandler(CacheHandler):
    def __init__(self):
        self.session_id = st.session_state.get("session_id")

    def get_cached_token(self):
        return st.session_state.get("spotipy_token")

    def save_token_to_cache(self, token_info):
        st.session_state["spotipy_token"] = token_info

def get_auth_manager():
    """
    Returns a spotipy.oauth2.SpotifyOAuth object.
    """
    return SpotifyOAuth(
                        client_id=os.getenv('SPOTIPY_CLIENT_ID', config['spotipy'].get('client_id', "")), 
                        client_secret=os.getenv('SPOTIPY_CLIENT_SECRET', config['spotipy'].get('client_secret', "")), 
                        redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI', config['spotipy'].get('redirect_uri', "http://127.0.0.1:8501")),
                        scope=os.getenv('SPOTIFY_SCOPE', config['spotipy'].get('scope', "playlist-modify-public, playlist-modify-private, user-read-email")),
                        cache_handler=StreamlitCacheHandler())

def main():
    st.title("FRC/FTC Spotify Playlist Cleaner", anchor=None)

    sp = Spotify(auth_manager=get_auth_manager())

    if "spotipy_token" in st.session_state:
        pass
    else:
        if st.button("Log in to Spotify"):
            # prevents a new tab from being opened
            st.markdown(f'<meta http-equiv="refresh" content="0; '
                        f'url={sp.auth_manager.get_authorize_url()}"/>',
                        unsafe_allow_html=True)

def callback():
    code = st.query_params.get("code")
    if code:
        try:
            token_info = get_auth_manager().get_access_token(code)
        except SpotifyOauthError:
            pass
    del st.query_params["code"]
    main()

#account_page = st.Page("pages/account.py", title="Spotify Account")
cleaner_page = st.Page("pages/cleaner.py", title="Playlist Cleaner")

pg = st.navigation([cleaner_page])
pg.run()