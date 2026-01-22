import pandas
import secrets
import streamlit as st
import time
import toml

from streamlit.components.v1 import iframe
from spotipy import Spotify
from spotipy.cache_handler import CacheHandler
from spotipy.exceptions import SpotifyOauthError
from spotipy.oauth2 import SpotifyOAuth

# Load the configuration from the TOML file
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
    return SpotifyOAuth(**config["spotipy"], cache_handler=StreamlitCacheHandler())

def _chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def _track_info(track_name, track_artist) -> str:
    return '\"' + track_name + '\" by \"' + track_artist + '\"'

def _search_for_track(track_name, track_artist, tracks) -> bool:
    return tracks.get(track_name) == track_artist

def get_tracks_from_playlist(playlist_id = None, playlist_total = 0) -> list:
    sp = Spotify(auth_manager=get_auth_manager())
    offset = 0
    items = []
    while True:
        response = sp.playlist_items(playlist_id,
                                     fields = 'items.track(artists,explicit,external_urls.spotify,id,name,uri),total',
                                     limit = 100,
                                     offset = offset,
                                     additional_types = ['track'])

        # If no items are returned, we have exhausted the playlist
        if len(response['items']) == 0:
            break

        # Append the Track to the List.
        items.extend(item['track'] for item in response['items'])

        # Update the offset
        offset = offset + len(response['items'])

        if offset >= playlist_total:
            break

    return items

def get_clean_tracks_from_playlist(tracks = None, dnp_tracks = None, remove_explicit = True, remove_optional = False, optional_tracks = None) -> list:
    items = []
    for track in tracks:
        track_name = track['name']
        track_artist = track['artists'][0]['name']

        if track['explicit'] and remove_explicit:
            continue

        skip = _search_for_track(track_name = track_name, track_artist = track_artist, tracks = dnp_tracks)
        if remove_optional and not skip:
            skip = _search_for_track(track_name = track_name, track_artist = track_artist, tracks = optional_tracks)

        if skip:
            continue

        items.append(track)

    return items

def create_cleaned_playlist(playlist = None, tracks = None) -> dict:
    sp = Spotify(auth_manager=get_auth_manager())
    track_ids = [track['id'] for track in tracks]
    counter = 0
    for chunk in _chunks(track_ids, 100):
        sp.playlist_add_items(playlist_id = playlist['id'], items = chunk)
        counter += len(chunk)
    return playlist

@st.cache_data
def download_do_not_play_list(url):
    dnp= pandas.read_excel(url, sheet_name = None, index_col=2)
    return dnp

def main():
    st.title("FRC/FTC Spotify Playlist Cleaner", anchor=None)

    sp = Spotify(auth_manager=get_auth_manager())

    if "spotipy_token" in st.session_state:
        with st.popover('Settings'):
            dnp_url = st.text_input("Do Not Play List", value="https://www.firstinspires.org/hubfs/events/FIRST-Do-Not-Play-List-2025.xlsx?hsLang=en", key="dnp_url", help="Like to an Excel Spreadsheet formatted the same as the FIRST Do Not Play List")
            remove_explicit = st.toggle("Remove Explicit Tracks", value=True, key="remove_explicit", help="These are tracks marked as Explicit for Profanity or Content")
            remove_optional = st.toggle("Remove Optional Tracks", value=False, key="remove_optional", help="These are tracks that are sad/downer songs, or otherwise slow tempo")
            make_public = st.toggle("Create Public Playlist", value=True, key="create_public", help="Should the generate playlist be Public")

        user = sp.me()

        with st.container():
            # Playlist URL Text Box
            with st.form("playlist_form", enter_to_submit=True):
                unclean_playlist_url = st.text_input("Spotify Playlist URL", value="", key="unclean_playlist_url", help="URL to Spotify Playlist you wish to Clean")
                submitted = st.form_submit_button("Clean")

            if submitted:
                # Needs to be hidden until user enters Playlist URL
                col1, col2, col3 = st.columns(3)
                with col1:
                    # Unclean Playlist
                    iframe("https://open.spotify.com/embed/playlist/" + unclean_playlist_url.rsplit('/', 1)[-1], height="100%")
                with col2:
                    # Load DNP Tracks
                    with st.status("Loading Do Not Play Tracks...", expanded=True) as status:
                        st.write("Downloading Spreadsheet...")
                        dnp = download_do_not_play_list(dnp_url)
                        st.write("Spreadsheet Successfully Downloaded!")
                        st.write("Extracting Do Not Play Tracks...")
                        dnp_tracks = dnp['DO NOT PLAY LIST']
                        st.write(str(len(dnp_tracks)) + " Do Not Play Tracks Loaded!")
                        if remove_optional:
                            st.write("Extracting Optional Do Not Play Tracks")
                            optional_tracks = dnp['Optional']
                            st.write(str(len(optional_tracks)) + " Optional Do Not Play Tracks Loaded!")
                        else:
                            optional_tracks = []
                        status.update(
                            label="" + str(len(dnp_tracks) + len(optional_tracks)) + " Do Not Play Tracks Loaded.", state="complete", expanded=False
                        )

                    # Load Playlist Tracks
                    with st.status("Loading Playlist Tracks...", expanded=True) as status:
                        st.write("Grabbing Playlist...")
                        unclean_playlist = sp.playlist(unclean_playlist_url)
                        st.write("Playlist with " + str(unclean_playlist['tracks']['total']) + " Tracks Grabbed!")
                        st.write("Grabbing Tracks...")
                        playlist_items = get_tracks_from_playlist(unclean_playlist_url, unclean_playlist['tracks']['total'])
                        st.write("Grabbed " + str(len(playlist_items)) + " Tracks!")
                        status.update(
                            label="" + str(len(playlist_items)) + " Tracks Loaded from Playlist.", state="complete", expanded=False
                        )

                    # Clean Tracks
                    with st.status("Cleaning Playlist Tracks...", expanded=True) as status:
                        st.write("Searching DNP List(s) for Tracks...")
                        clean_tracks = get_clean_tracks_from_playlist(playlist_items, dnp_tracks, remove_explicit, remove_optional, optional_tracks)
                        st.write("Found " + str(len(playlist_items) - len(clean_tracks)) + " Unclean Tracks!")
                        status.update(
                            label="" + str(len(clean_tracks)) + " Clean Tracks identified.", state="complete", expanded=False
                        )

                    # Create Playlist
                    with st.status("Generating Cleaned Playlist...", expanded=True) as status:
                        st.write("Creating Cleaned Playlist...")
                        name = unclean_playlist['name'] + " Cleaned"
                        description = "Playlist cleaned for use in FRC/FTC Events by the FRC-FTC Spotify Playlist Cleaner. " + unclean_playlist['description']
                        clean_playlist_empty = sp.user_playlist_create(user = user['id'], name = name, public = make_public, description = description)
                        st.write("Filling Playlist")
                        clean_playlist = create_cleaned_playlist(clean_playlist_empty, clean_tracks)
                        status.update(
                            label="Cleaned Playlist Created", state="complete", expanded=False
                        )

                with col3:
                    # Clean Playlist
                    iframe("https://open.spotify.com/embed/playlist/" + clean_playlist['id'])
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


if __name__ == "__main__":
    if st.query_params.get("code"):
        callback()
    else:
        main()