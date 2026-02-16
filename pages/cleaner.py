import os
import pandas
import streamlit as st
import toml

from streamlit.components.v1 import iframe

from spotipy import Spotify
from spotipy.cache_handler import CacheHandler
from spotipy.exceptions import SpotifyOauthError
from spotipy.oauth2 import SpotifyOAuth

from ytmusicapi import YTMusic, OAuthCredentials

# Load the configuration from the TOML file
config = toml.load("./config.toml")
general_config = config['general']
spotify_config = config['spotify']
youtube_config = config['youtube']

# Set Page Title
st.set_page_config("Playlist Cleaner Settings")

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
                        client_id=os.getenv('SPOTIPY_CLIENT_ID', spotify_config.get('client_id', "")), 
                        client_secret=os.getenv('SPOTIPY_CLIENT_SECRET', spotify_config.get('client_secret', "")), 
                        redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI', spotify_config.get('redirect_uri', "http://127.0.0.1:8501")),
                        scope=os.getenv('SPOTIFY_SCOPE', spotify_config.get('scope', "playlist-modify-public, playlist-modify-private, user-read-email")),
                        cache_handler=StreamlitCacheHandler())

def _chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def _search_for_track(track_name, track_artist, tracks):
    return str(tracks[1].get(track_name)) == track_artist

def get_tracks_from_playlist(playlist_id = None, playlist_total = 0) -> list:
    # Intialize Spotify API
    sp = Spotify(auth_manager=get_auth_manager())

    # Track how many Tracks we have already grabbed
    offset = 0

    # List of Tracks
    items = []

    # Run through the Playlist until all tracks are exhausted
    while True:
        # Get Playlist items 100 at a time
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

        # If the offset is greater than or equal to the Total number of tracks in the playlist, then we have reached the end of the Playlist
        if offset >= playlist_total:
            break

    # Return the List of Playlist items
    return items

def get_clean_tracks_from_playlist(tracks = None, dnp_tracks = None, remove_explicit = True, remove_optional = False, optional_tracks = None) -> list:

    # List of Clean Tracks
    clean_items = []

    # List of Unclean Tracks
    unclean_items = []

    # Dict of Explicit Tracks
    explicit_items = []

    # Run through the Tracks and determine their Cleanliness
    for track in tracks:
        # Grab the Track Name
        track_name = track['name']

        # Grab the name of the first listed Artist
        track_artist = track['artists'][0]['name']

        # If the track is marked Explicit and remove_explicit is True, mark the Track as Unclean
        if track['explicit'] and remove_explicit:
            # Append track to list of Unclean Tracks
            unclean_items.append(track)
            explicit_items.append({"Artist": track_artist, "Song Title": track_name, "Reason": "Explicit"})
            continue

        # Search the DNP List for the track
        skip = _search_for_track(track_name = track_name, track_artist = track_artist, tracks = dnp_tracks)

        # Search the Optional DNP List for the track
        if remove_optional and not skip:
            skip = _search_for_track(track_name = track_name, track_artist = track_artist, tracks = optional_tracks)

        # If Track is in DNP or Optional DNP List, mark the Track as Unclean
        if skip:
            unclean_items.append(track)
            continue

        # Track was not Explicit, nor found the DNP or Optional DNP List, mark the Track as Clean
        clean_items.append(track)

    # Return the Clean and Unclean tracks
    return (clean_items, unclean_items, explicit_items)

def create_cleaned_playlist(playlist = None, tracks = None) -> dict:
    # Initialize Spotify API
    sp = Spotify(auth_manager=get_auth_manager())

    # Get list of Track IDs
    track_ids = [track['id'] for track in tracks]

    # Split Tracks into chunks of 100 and add them to the Playlist
    for chunk in _chunks(track_ids, 100):
        # Add Tracks to Playlist
        sp.playlist_add_items(playlist_id = playlist['id'], items = chunk)

    return playlist

@st.cache_data
def download_do_not_play_list(url):
    # Download Do Not Play List from URL
    dnp= pandas.read_excel(url, sheet_name = None, index_col=2, header=None, skiprows=1)
    return dnp

@st.dialog("Unclean Tracks", on_dismiss="rerun")
def playlist_diff(url, unclean_tracks, explicit_tracks):
    # Fetch DNP portion of Do Not Play List
    dnp_list = pandas.read_excel(url, sheet_name = "DO NOT PLAY LIST", index_col="Artist", names=["Year", "Artist", "Song Title", "Reason", "List"], usecols=["Artist", "Song Title", "Reason"])

    # Fetch Optional portion of Do Not Play List
    optional_list = pandas.read_excel(url, sheet_name = "Optional", index_col="Artist", names=["Year", "Artist", "Song Title", "Reason", "List", "Tempo"], usecols=["Artist", "Song Title", "Reason"])

    # Create DataFrame from Explicit Tracks List
    explicit_list = pandas.DataFrame(
        explicit_tracks
    )

    # Combine DNP and Optional into one Dataframe
    dnp = pandas.concat([dnp_list, optional_list, explicit_list])

    # Convert Unclean Tracks into a List containing only the data we need
    tracks = []
    for track in unclean_tracks:
        tracks.append({"Artist": track['artists'][0]['name'], "Song Title": track['name'], "Link": track['external_urls']['spotify']})

    result = pandas.DataFrame()
    if len(tracks) > 0:
        # Create DataFrame from Unclean Tracks List
        unclean_list = pandas.DataFrame(
            tracks
        )

        # Merge Unclean Tracks List with DNP DataFrame to get the Reason for why the Track was removed
        result = pandas.merge(dnp, unclean_list, how="inner", on=["Artist", "Song Title"])

        # Show Tracks that were marked as Unclean
        st.table(result)
    else:
        st.write("No unclean tracks found!")

    st.session_state.situational_playlists = st.toggle("Create situation-based Playlists")

    # Wait for User to approve of changes
    if st.button("Go!"):
        st.session_state.submit = True
        st.rerun()

def generate_track_dataframe(unconverted_tracks):
    tracks = []
    for track in unconverted_tracks:
        tracks.append({"Artist": track['artists'][0]['name'], "Song Title": track['name'], "Link": track['external_urls']['spotify'], "Explicit": track['explicit'], "URI": track['uri'], "ID": track['id']})

    df = pandas.DataFrame(
        tracks
    )

    return df

def main():
    st.title("Playlist Cleaner", anchor=None)

    # Initialize Spotify API
    if os.getenv("ENABLE_SPOTIFY") or general_config['enable_spotify']:
        sp = Spotify(auth_manager=get_auth_manager())

    # Initialize Youtube API
    if os.getenv("ENABLE_YOUTUBE") or general_config['enable_youtube']:
        ytmusic = YTMusic('oauth.json', oauth_credentials=OAuthCredentials(client_id=os.getenv("YOUTUBE_CLIENT_ID", youtube_config['client_id']), client_secret=os.getenv("YOUTUBE_CLIENT_SECRET", youtube_config['client_secret'])))

    # Check if User has logged into Spotify API or Youtube API
    if "spotipy_token" in st.session_state:
        # Allow user to change settings
        with st.popover('Settings'):
            dnp_url = st.text_input("Do Not Play List", value="https://www.firstinspires.org/hubfs/events/FIRST-Do-Not-Play-List-2025.xlsx?hsLang=en", key="dnp_url", help="Like to an Excel Spreadsheet formatted the same as the FIRST Do Not Play List")
            remove_explicit = st.toggle("Remove Explicit Tracks", value=True, key="remove_explicit", help="These are tracks marked as Explicit for Profanity or Content")
            remove_optional = st.toggle("Remove Optional Tracks", value=False, key="remove_optional", help="These are tracks that are sad/downer songs, or otherwise slow tempo")

        # Get Spotify User
        user = sp.me()

        # User has not approved of changes
        if "submit" not in st.session_state or not st.session_state.submit:
            with st.container():
                # Playlist URL Text Box
                with st.form("playlist_form", enter_to_submit=True):
                    st.session_state.unclean_playlist_url = st.text_input("Spotify Playlist URL", value="", help="URL to Spotify Playlist you wish to Clean")
                    submitted = st.form_submit_button("Clean")

                # Wait for user to submit Playlist URL
                if submitted:
                    # Load DNP Tracks
                    with st.status("Loading Do Not Play Tracks...", expanded=True) as status:
                        st.write("Downloading Spreadsheet...")
                        dnp = download_do_not_play_list(dnp_url)
                        st.write("Spreadsheet Successfully Downloaded!")

                        st.write("Extracting Do Not Play Tracks...")
                        dnp_tracks = dnp['DO NOT PLAY LIST']
                        st.write(str(len(dnp_tracks)) + " Do Not Play Tracks Loaded!")

                        # Load Optional DNP Tracks if enabled
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
                        st.session_state.clean_tracks, st.session_state.unclean_tracks, st.session_state.explicit_tracks = get_clean_tracks_from_playlist(playlist_items, dnp_tracks, remove_explicit, remove_optional, optional_tracks)
                        st.write("Found " + str(len(playlist_items) - len(st.session_state.clean_tracks)) + " Unclean Tracks!")

                        status.update(
                            label="" + str(len(st.session_state.clean_tracks)) + " Clean Tracks identified.", state="complete", expanded=False
                        )

                    # Do not show the Playlist Diff until it has been generated
                    if "submit" not in st.session_state:
                        playlist_diff(dnp_url, st.session_state.unclean_tracks, st.session_state.explicit_tracks)
        # User has requests Situation-based Playlists
        elif st.session_state.situational_playlists and ("submit_situation" not in st.session_state or not st.session_state.submit_situation):
            st.session_state.situations = st.text_input("Enter the different Situations, separated by a comma").split(',')
            
            st.session_state.df = generate_track_dataframe(st.session_state.clean_tracks)

            for situation in st.session_state.situations:
                st.session_state.df[situation] = False

            columns = ["Artist", "Song Title", "Link"]
            columns.extend(st.session_state.situations)

            st.data_editor(
                st.session_state.df, 
                column_order=columns,
                column_config={
                    "Artist": st.column_config.TextColumn(
                        disabled = True
                    ),
                    "Song Title": st.column_config.TextColumn(
                        disabled = True
                    ),
                    'Link': st.column_config.LinkColumn(
                        disabled = True,
                        display_text = "Open in Spotify"
                    )
                }
            )

            # Wait for User to approve of changes
            if st.button("Done!"):
                st.session_state.submit_situation = True
                st.rerun()
            
        # User has approved changes with Situational Playlists
        elif "submit_situation" in st.session_state and st.session_state.submit_situation:
            col1, col2, col3 = st.columns(3)
            with col1:
                # Unclean Playlist
                iframe("https://open.spotify.com/embed/playlist/" + st.session_state.unclean_playlist_url.rsplit('/', 1)[-1], height="100%")
            with col2:
                # Create Full Clean Playlist
                with st.status("Generating Cleaned Playlist...", expanded=True) as status:
                    st.write("Creating Cleaned Playlist...")
                    name = st.session_state.unclean_playlist['name'] + " Cleaned"
                    description = "Playlist cleaned for use in FRC/FTC Events by the FRC-FTC Spotify Playlist Cleaner. " + st.session_state.unclean_playlist['description']
                    clean_playlist_empty = sp.user_playlist_create(user = user['id'], name = name, public = True, description = description)

                    st.write("Filling Playlist")
                    clean_playlist = create_cleaned_playlist(clean_playlist_empty, st.session_state.clean_tracks)
                    status.update(
                        label="Cleaned Playlist Created", state="complete", expanded=False
                    )
                with st.status("Separating Situations...", expanded=True) as status:
                     for situation in st.session_state.situations:
                        situation_df = st.session_state.df.loc[st.session_state.df[situation] == True]
                        with st.status("Creating Playlist for " + str(situation) + "..." , expanded=True) as status:
                            st.write("Creating Cleaned Playlist...")
                            name = st.session_state.unclean_playlist['name'] + " Cleaned " + str(situation)
                            description = "Playlist cleaned for use in FRC/FTC Events by the FRC-FTC Spotify Playlist Cleaner. " + st.session_state.unclean_playlist['description']
                            clean_playlist_empty = sp.user_playlist_create(user = user['id'], name = name, public = True, description = description)

                            st.write("Filling Playlist")
                            clean_playlist = create_cleaned_playlist(clean_playlist_empty, situation_df.to_dict('records'))
                            status.update(
                                label="Cleaned Playlist Created", state="complete", expanded=False
                            )
            with col3:
                # Clean Playlist
                iframe("https://open.spotify.com/embed/playlist/" + clean_playlist['id'])
        # User has approved changes
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
                    clean_playlist_empty = sp.user_playlist_create(user = user['id'], name = name, public = True, description = description)

                    st.write("Filling Playlist")
                    clean_playlist = create_cleaned_playlist(clean_playlist_empty, st.session_state.clean_tracks)
                    status.update(
                        label="Cleaned Playlist Created", state="complete", expanded=False
                    )
            with col3:
                # Clean Playlist
                iframe("https://open.spotify.com/embed/playlist/" + clean_playlist['id'])
    # User is not logged into Spotify
    else:
        if st.button("Log in to Spotify"):
            # prevents a new tab from being opened
            st.markdown(f'<meta http-equiv="refresh" content="0; '
                        f'url={sp.auth_manager.get_authorize_url()}"/>',
                        unsafe_allow_html=True)

def spotify_callback():
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
        spotify_callback()
    else:
        main()