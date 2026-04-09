import streamlit as st
import streamlit.components.v1 as components
import random
from datetime import datetime, timedelta
import json
import os
import mysql.connector
from mysql.connector import Error

# Database configuration for XAMPP
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',  # Default XAMPP MySQL user
    'password': '',  # Default XAMPP MySQL password (empty)
    'database': 'song_randomizer'
}

# Password for authentication
APP_PASSWORD = "song123"  # Change this to your desired password

# File to store persistent lockout data
LOCKOUT_FILE = "lockout_data.json"

# Database functions
def create_database_connection():
    """Create and return database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        st.error(f"Database connection failed: {e}")
        return None

def create_songs_table():
    """Create songs table if it doesn't exist"""
    connection = create_database_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS songs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    person_name VARCHAR(255) NOT NULL,
                    song_title VARCHAR(255) NOT NULL,
                    artist VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_person (person_name),
                    UNIQUE KEY unique_song (song_title)
                )
            """)
            connection.commit()
        except Error as e:
            st.error(f"Failed to create table: {e}")
        finally:
            cursor.close()
            connection.close()

def load_songs_from_db():
    """Load all songs from database"""
    connection = create_database_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT person_name, song_title, artist FROM songs ORDER BY created_at")
            songs = cursor.fetchall()
            return songs
        except Error as e:
            st.error(f"Failed to load songs: {e}")
            return []
        finally:
            cursor.close()
            connection.close()
    return []

def add_song_to_db(person_name, song_title, artist):
    """Add a song to database, returns success and error message"""
    connection = create_database_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT person_name, song_title FROM songs WHERE person_name = %s OR song_title = %s",
                (person_name, song_title),
            )
            existing = cursor.fetchone()
            if existing:
                if existing['person_name'] == person_name:
                    return False, "name is already existed"
                if existing['song_title'] == song_title:
                    return False, "song is already existed"
                return False, "name or song is already existed"

            cursor.execute("""
                INSERT INTO songs (person_name, song_title, artist) 
                VALUES (%s, %s, %s)
            """, (person_name, song_title, artist))
            connection.commit()
            return True, f"Added '{song_title}' by {artist}"
        except Error as e:
            return False, f"Failed to add song: {e}"
        finally:
            cursor.close()
            connection.close()
    return False, "Database connection failed"

def delete_song_from_db(person_name, song_title):
    """Delete a single song from the database by person and song title"""
    connection = create_database_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM songs WHERE person_name = %s AND song_title = %s",
                (person_name, song_title),
            )
            connection.commit()
            return cursor.rowcount > 0
        except Error as e:
            st.error(f"Failed to delete song: {e}")
            return False
        finally:
            cursor.close()
            connection.close()
    return False

# Initialize database on startup
create_songs_table()

# Function to load lockout data from file
def load_lockout_data():
    if os.path.exists(LOCKOUT_FILE):
        try:
            with open(LOCKOUT_FILE, 'r') as f:
                data = json.load(f)
                # Convert string back to datetime
                if data.get('lockout_until'):
                    data['lockout_until'] = datetime.fromisoformat(data['lockout_until'])
                return data
        except:
            pass
    return {'attempts': 0, 'lockout_until': None}

# Function to save lockout data to file
def save_lockout_data(attempts, lockout_until):
    data = {
        'attempts': attempts,
        'lockout_until': lockout_until.isoformat() if lockout_until else None
    }
    try:
        with open(LOCKOUT_FILE, 'w') as f:
            json.dump(data, f)
    except:
        pass

# Load persistent lockout data
lockout_data = load_lockout_data()

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'songs' not in st.session_state:
    st.session_state.songs = load_songs_from_db()  # Load from database
if 'selected_song' not in st.session_state:
    st.session_state.selected_song = None
if 'person_name' not in st.session_state:
    st.session_state.person_name = ''
if 'song_title' not in st.session_state:
    st.session_state.song_title = ''
if 'artist' not in st.session_state:
    st.session_state.artist = ''
if 'reset_form' not in st.session_state:
    st.session_state.reset_form = False
if 'success_message' not in st.session_state:
    st.session_state.success_message = ''
if 'page' not in st.session_state:
    st.session_state.page = 'home'

# Authentication check
if not st.session_state.authenticated:
    st.title("🔐 Login Required")
    st.markdown("Please enter the password to access the Song Randomizer.")

    # Check if user is currently locked out (from persistent data)
    current_time = datetime.now()
    if lockout_data['lockout_until'] and current_time < lockout_data['lockout_until']:
        remaining_time = lockout_data['lockout_until'] - current_time
        minutes_left = int(remaining_time.total_seconds() / 60)
        seconds_left = int(remaining_time.total_seconds() % 60)
        st.error(f"Too many failed attempts. Wait {minutes_left} minutes and {seconds_left} seconds to try again.")
        st.stop()

    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login"):
        if password == APP_PASSWORD:
            st.session_state.authenticated = True
            # Clear persistent lockout data on successful login
            save_lockout_data(0, None)
            st.success("Login successful!")
            st.rerun()
        else:
            # Increment attempts in persistent storage
            new_attempts = lockout_data['attempts'] + 1
            if new_attempts >= 3:
                lockout_time = current_time + timedelta(minutes=3)
                save_lockout_data(new_attempts, lockout_time)
                st.error("Too many failed attempts. Wait 3 minutes to try again.")
            else:
                save_lockout_data(new_attempts, None)
                remaining_attempts = 3 - new_attempts
                st.error(f"Incorrect password. {remaining_attempts} attempts remaining.")

    st.stop()  # Stop execution if not authenticated

# If authenticated, show the main app
# If a successful add requested a reset, clear inputs before widget creation
if st.session_state.reset_form:
    st.session_state.person_name = ''
    st.session_state.song_title = ''
    st.session_state.artist = ''
    st.session_state.reset_form = False

# Refresh songs from database
st.session_state.songs = load_songs_from_db()

# App title and styling
st.title("🎵 Random Song Selector")

components.html(
    """
    <script>
    document.addEventListener('contextmenu', function(event) {
        event.preventDefault();
    });
    document.addEventListener('keydown', function(event) {
        if (event.keyCode === 123) event.preventDefault();
        if (event.ctrlKey && event.shiftKey && (event.keyCode === 73 || event.keyCode === 74)) event.preventDefault();
        if (event.ctrlKey && event.keyCode === 85) event.preventDefault();
        if (event.ctrlKey && event.keyCode === 83) event.preventDefault();
        if (event.ctrlKey && event.keyCode === 80) event.preventDefault();
    });
    </script>
    """,
    height=1,
    width=1,
)

if st.session_state.page == 'home':
    st.markdown("Add songs to your list and randomly pick one!")

    if st.session_state.success_message:
        st.success("You added a song to the song list")
        if st.button("Song List", key="goto_song_list"):
            st.session_state.page = 'list'
            st.session_state.success_message = ''
            st.rerun()

    # Input section
    st.subheader("Add New Song")
    col1, col2, col3 = st.columns(3)

    with col1:
        person_name = st.text_input("Person Name", placeholder="e.g., John Doe", key="person_name")

    with col2:
        song_title = st.text_input("Song Title", placeholder="e.g., Bohemian Rhapsody", key="song_title")

    with col3:
        artist = st.text_input("Artist", placeholder="e.g., Queen", key="artist")

    # Button row
    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2])

    with btn_col1:
        if st.button("➕ Add Song", use_container_width=True, key="add_song_btn"):
            if person_name and song_title and artist:
                success, message = add_song_to_db(person_name, song_title, artist)
                if success:
                    st.session_state.success_message = message
                    st.session_state.songs = load_songs_from_db()  # Reload from database
                    st.session_state.reset_form = True
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Please fill in all fields!")

    with btn_col2:
        if st.button("Song List", use_container_width=True, key="goto_song_list_bottom"):
            st.session_state.page = 'list'
            st.rerun()

elif st.session_state.page == 'list':
    st.subheader("Song List")
    if st.session_state.songs:
        for idx, song in enumerate(st.session_state.songs, 1):
            row_col1, row_col2 = st.columns([4, 1])
            with row_col1:
                st.markdown(f"**{idx}. {song['person_name']}** - \"{song['song_title']}\" by {song['artist']}")
            with row_col2:
                if st.button("Delete Song", key=f"delete_{idx}", use_container_width=True):
                    if delete_song_from_db(song['person_name'], song['song_title']):
                        st.success(f"Deleted '{song['song_title']}' from the database.")
                        st.session_state.songs = load_songs_from_db()
                        if st.session_state.selected_song and st.session_state.selected_song['song_title'] == song['song_title'] and st.session_state.selected_song['person_name'] == song['person_name']:
                            st.session_state.selected_song = None
                        st.rerun()
                    else:
                        st.error("Failed to delete the song.")
    else:
        st.info("No songs added yet. Add some songs on the home page.")

    if st.button("Picked Random Song", key="picked_random_btn"):
        if st.session_state.songs:
            st.session_state.selected_song = random.choice(st.session_state.songs)
            st.success("A random song has been selected!")
        else:
            st.warning("No songs available to pick.")

    if st.session_state.selected_song:
        song = st.session_state.selected_song
        st.markdown("---")
        st.markdown("### 🎉 Random Selection")
        st.info(f"**{song['person_name']}** chose **\"{song['song_title']}\"** by **{song['artist']}**")

    st.markdown("---")
    if st.button("Back to Add Song", key="back_to_add"):
        st.session_state.page = 'home'
        st.rerun()