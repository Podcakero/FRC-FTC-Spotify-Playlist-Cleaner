import os
import pandas
import streamlit as st
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
    return SpotifyOAuth(
                        client_id=os.getenv('SPOTIPY_CLIENT_ID', config['spotipy'].get('client_id', "")), 
                        client_secret=os.getenv('SPOTIPY_CLIENT_SECRET', config['spotipy'].get('client_secret', "")), 
                        redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI', config['spotipy'].get('redirect_uri', "http://127.0.0.1:8501")),
                        scope=os.getenv('SPOTIFY_SCOPE', config['spotipy'].get('scope', "playlist-modify-public, playlist-modify-private, user-read-email")),
                        cache_handler=StreamlitCacheHandler())

def _chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def _track_info(track_name, track_artist) -> str:
    return '\"' + track_name + '\" by \"' + track_artist + '\"'

def _search_for_track(track_name, track_artist, tracks):
    dnp_artist = tracks[1].get(track_name)
    return str(dnp_artist) == track_artist

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
    clean_items = []
    unclean_items = []
    for track in tracks:
        track_name = track['name']
        track_artist = track['artists'][0]['name']

        if track['explicit'] and remove_explicit:
            continue

        skip = _search_for_track(track_name = track_name, track_artist = track_artist, tracks = dnp_tracks)
        if remove_optional and not skip:
            skip = _search_for_track(track_name = track_name, track_artist = track_artist, tracks = optional_tracks)

        if skip:
            unclean_items.append(track)
            continue

        clean_items.append(track)

    return (clean_items, unclean_items)

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
    dnp= pandas.read_excel(url, sheet_name = None, index_col=2, header=None, skiprows=1)
    return dnp

@st.dialog("Unclean Tracks", dismissible=False)
def playlist_diff(url, unclean_tracks):
    dnp_list = pandas.read_excel(url, sheet_name = "DO NOT PLAY LIST", index_col="Artist", names=["Year", "Artist", "Song Title", "Reason", "List"], usecols=["Artist", "Song Title", "Reason"])
    optional_list = pandas.read_excel(url, sheet_name = "Optional", index_col="Artist", names=["Year", "Artist", "Song Title", "Reason", "List", "Tempo"], usecols=["Artist", "Song Title", "Reason"])
    dnp = pandas.concat([dnp_list, optional_list])

    tracks = []
    for track in unclean_tracks:
        tracks.append({"Artist": track['artists'][0]['name'], "Song Title": track['name'], "Link": track['external_urls']['spotify']})

    unclean_list = pandas.DataFrame(
        tracks
    )

    result = pandas.merge(dnp, unclean_list, how="inner", on=["Artist", "Song Title"])

    st.table(result)

    if st.button("Go!"):
        st.session_state.submit = True
        st.rerun()

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

        if "submit" not in st.session_state or not st.session_state.submit:
            with st.container():
                # Playlist URL Text Box
                with st.form("playlist_form", enter_to_submit=True):
                    st.text_input("Spotify Playlist URL", value="", key="unclean_playlist_url", help="URL to Spotify Playlist you wish to Clean")
                    submitted = st.form_submit_button("Clean")

                if submitted:
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
                            optional_tracks = pandas.DataFrame()
                        status.update(
                            label="" + str(len(dnp_tracks) + len(optional_tracks)) + " Do Not Play Tracks Loaded.", state="complete", expanded=False
                        )

                    # Load Playlist Tracks
                    with st.status("Loading Playlist Tracks...", expanded=True) as status:
                        st.write("Grabbing Playlist...")
                        st.session_state.unclean_playlist = sp.playlist(st.session_state.unclean_playlist_url)
                        st.write("Playlist with " + str(st.session_state.unclean_playlist['tracks']['total']) + " Tracks Grabbed!")
                        st.write("Grabbing Tracks...")
                        playlist_items = get_tracks_from_playlist(st.session_state.unclean_playlist_url, st.session_state.unclean_playlist['tracks']['total'])
                        st.write("Grabbed " + str(len(playlist_items)) + " Tracks!")
                        status.update(
                            label="" + str(len(playlist_items)) + " Tracks Loaded from Playlist.", state="complete", expanded=False
                        )

                    # Clean Tracks
                    with st.status("Cleaning Playlist Tracks...", expanded=True) as status:
                        st.write("Searching DNP List(s) for Tracks...")
                        st.session_state.clean_tracks, st.session_state.unclean_tracks = get_clean_tracks_from_playlist(playlist_items, dnp_tracks, remove_explicit, remove_optional, optional_tracks)
                        st.write("Found " + str(len(playlist_items) - len(st.session_state.clean_tracks)) + " Unclean Tracks!")
                        status.update(
                            label="" + str(len(st.session_state.clean_tracks)) + " Clean Tracks identified.", state="complete", expanded=False
                        )

                    if "submit" not in st.session_state:
                        playlist_diff(dnp_url, st.session_state.unclean_tracks)
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                # Unclean Playlist
                iframe("https://open.spotify.com/embed/playlist/" + st.session_state.unclean_playlist_url.rsplit('/', 1)[-1], height="100%")
            with col2:
                # Create Playlist
                with st.status("Generating Cleaned Playlist...", expanded=True) as status:
                    st.write("Creating Cleaned Playlist...")
                    name = st.session_state.unclean_playlist['name'] + " Cleaned"
                    description = "Playlist cleaned for use in FRC/FTC Events by the FRC-FTC Spotify Playlist Cleaner. " + st.session_state.unclean_playlist['description']
                    clean_playlist_empty = sp.user_playlist_create(user = user['id'], name = name, public = make_public, description = description)
                    st.write("Filling Playlist")
                    clean_playlist = create_cleaned_playlist(clean_playlist_empty, st.session_state.clean_tracks)
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