import streamlit as st
import toml

config = toml.load("./config.toml")
general_config = config['general']
spotify_config = config['spotify']
youtube_config = config['youtube']

@st.dialog("Admin Login", dismissible=False)
def admin_login():
    password = st.text_input("Password", type="password")

    with st.container(horizontal=True):
        submit = st.button("Submit")
        go_back = st.button("Go Back")

    if go_back:
        st.switch_page("pages/cleaner.py")

    if submit:
        if password == general_config['admin_password']:
            st.session_state.login_state = True
            st.rerun()
        else:
            st.error("Incorrect Password")

# Set Page Title
st.set_page_config("Playlist Cleaner Settings")

# Check if user is authenticated
if not st.session_state.get("login_state"):
    admin_login()
else:
    with st.form("admin_settings"):
        st.write("General Settings")
        admin_password = st.text_input("Admin Password", general_config['admin_password'], type="password")
        enable_spotify = st.toggle("Enable Spotify API", value=True)
        enable_youtube = st.toggle("Enable Youtube API", value=True)
        st.write()

        st.write("Spotify API Settings")
        spotify_client_id = st.text_input("Client ID", spotify_config['client_id'], placeholder="Spotify API Client ID")
        spotify_client_secret = st.text_input("Client Secret", spotify_config['client_secret'], placeholder="Spotify API Client Secret", type="password")
        spotify_redirect_url = st.text_input("Redirect URL", spotify_config['redirect_url'], placeholder="Spotify API Redirect URL")
        spotify_scope = st.text_input("Scope", spotify_config['scope'], placeholder="Spotify API Scope")

        st.write("Youtube Music API Settings")
        youtube_client_id = st.text_input("Client ID", youtube_config['client_id'], placeholder="Youtube API Client ID")
        youtube_client_secret = st.text_input("Client Secret", youtube_config['client_secret'], placeholder="Youtube API Client Secret", type="password")

        submit = st.form_submit_button("Save")

    if submit:
        config['general']['admin_password'] = admin_password
        config['general']['enable_spotify'] = enable_spotify
        config['general']['enable_youtube'] = enable_youtube
        config['spotify']['client_id'] = spotify_client_id
        config['spotify']['client_secret'] = spotify_client_secret
        config['spotify']['redirect_url'] = spotify_redirect_url
        config['spotify']['scope'] = spotify_scope
        config['youtube']['client_id'] = youtube_client_id
        config['youtube']['client_secret'] = youtube_client_secret

        with open("./config.toml", "w") as file:
            toml.dump(config, file)
            st.success("Successfully Saved Settings")

        st.rerun()