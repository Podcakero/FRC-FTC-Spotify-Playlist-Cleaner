import os
import random
import streamlit as st
import string
import toml

def generate_password():
    characters = string.ascii_letters + string.digits + string.punctuation
    password = "".join(random.choice(characters) for i in range(12))
    return password

def get_config():
    if not os.path.exists("./config.toml"):
        generated_password = generate_password()
        print("Generated Admin Password: " + generated_password)

        config_string = f"""
        [general]
        admin_password = \"{ generated_password }\"
        dnp_file = \"FIRST-Do-Not-Play-List-2025.xlsx\"
        remove_optional = false
        remove_explicit = true
        
        [spotify]
        client_id = \"\"
        client_secret = \"\"
        redirect_url = \"http://127.0.0.1:8501/spotify\"
        scope = \"playlist-modify-public, playlist-modify-private, user-read-email\"

        [youtube]
        client_id = \"\"
        client_secret = \"\"
        """

        with open("./config.toml", "w") as file:
            config = toml.dump(toml.loads(config_string), file)
    else:
        config = toml.load("./config.toml")
    return config

# Generate config if not existing
get_config()

admin_page = st.Page("pages/admin.py", title="Admin")
cleaner_page = st.Page("pages/cleaner.py", title="Playlist Cleaner")

pg = st.navigation([cleaner_page, admin_page], position="top")
pg.run()