import streamlit as st
import streamlit.components.v1 as components
import random
from datetime import datetime, timedelta
import json
import os
import mysql.connector
from mysql.connector import Error
import base64
from PIL import Image
import io

# Must be the first Streamlit command
st.set_page_config(page_title="Song Randomizer", layout="centered")

# Database configuration for XAMPP (LOCAL ONLY)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'song_randomizer',
    'port': 3306
}

# File paths
LOCKOUT_FILE = "lockout_data.json"

# Database functions
def create_database_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        st.error(f"Database connection failed: {e}")
        st.error("Make sure XAMPP MySQL is running!")
        return None

def init_database():
    """Initialize all tables"""
    connection = create_database_connection()
    if connection:
        try:
            cursor = connection.cursor()
            
            # Songs table
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
            
            # Admin table with profile - using LONGBLOB for large images (500MB)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    full_name VARCHAR(255),
                    email VARCHAR(255),
                    phone VARCHAR(50),
                    bio TEXT,
                    profile_pic LONGBLOB,
                    profile_pic_type VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            
            connection.commit()
            
            # Create default admin if none exists
            cursor.execute("SELECT COUNT(*) FROM admin")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO admin (username, password, full_name, email)
                    VALUES (%s, %s, %s, %s)
                """, ('admin', 'admin123', 'Administrator', 'admin@example.com'))
                connection.commit()
                
        except Error as e:
            st.error(f"Database init failed: {e}")
        finally:
            cursor.close()
            connection.close()

def load_songs_from_db():
    connection = create_database_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT person_name, song_title, artist FROM songs ORDER BY created_at")
            return cursor.fetchall()
        except Error as e:
            st.error(f"Failed to load songs: {e}")
            return []
        finally:
            cursor.close()
            connection.close()
    return []

def add_song_to_db(person_name, song_title, artist):
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

# Admin functions
def verify_admin(username, password):
    """Verify admin credentials"""
    connection = create_database_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM admin WHERE username = %s AND password = %s",
                (username, password)
            )
            admin = cursor.fetchone()
            return admin
        except Error as e:
            st.error(f"Login error: {e}")
            return None
        finally:
            cursor.close()
            connection.close()
    return None

def get_admin_by_id(admin_id):
    """Get admin by ID"""
    connection = create_database_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM admin WHERE id = %s", (admin_id,))
            return cursor.fetchone()
        except Error as e:
            st.error(f"Error fetching admin: {e}")
            return None
        finally:
            cursor.close()
            connection.close()
    return None

def update_admin_profile(admin_id, full_name, email, phone, bio):
    """Update admin profile (without picture)"""
    connection = create_database_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE admin 
                SET full_name = %s, email = %s, phone = %s, bio = %s
                WHERE id = %s
            """, (full_name, email, phone, bio, admin_id))
            connection.commit()
            return True
        except Error as e:
            st.error(f"Failed to update profile: {e}")
            return False
        finally:
            cursor.close()
            connection.close()
    return False

def update_admin_password(admin_id, new_password):
    """Update admin password"""
    connection = create_database_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE admin SET password = %s WHERE id = %s",
                (new_password, admin_id)
            )
            connection.commit()
            return True
        except Error as e:
            st.error(f"Failed to update password: {e}")
            return False
        finally:
            cursor.close()
            connection.close()
    return False

def update_admin_username(admin_id, new_username):
    """Update admin username"""
    connection = create_database_connection()
    if connection:
        try:
            cursor = connection.cursor()
            # Check if username already exists
            cursor.execute("SELECT id FROM admin WHERE username = %s AND id != %s", (new_username, admin_id))
            if cursor.fetchone():
                return False, "Username already taken"
            
            cursor.execute(
                "UPDATE admin SET username = %s WHERE id = %s",
                (new_username, admin_id)
            )
            connection.commit()
            return True, "Username updated successfully"
        except Error as e:
            return False, f"Failed to update username: {e}"
        finally:
            cursor.close()
            connection.close()
    return False, "Database connection failed"

def update_profile_picture(admin_id, image_bytes, image_type):
    """Update profile picture in database"""
    connection = create_database_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE admin 
                SET profile_pic = %s, profile_pic_type = %s
                WHERE id = %s
            """, (image_bytes, image_type, admin_id))
            connection.commit()
            return True
        except Error as e:
            st.error(f"Failed to upload picture: {e}")
            return False
        finally:
            cursor.close()
            connection.close()
    return False

def get_profile_picture(admin_id):
    """Get profile picture from database"""
    connection = create_database_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT profile_pic, profile_pic_type FROM admin WHERE id = %s",
                (admin_id,)
            )
            result = cursor.fetchone()
            if result and result[0]:
                return result[0], result[1]
            return None, None
        except Error as e:
            st.error(f"Error fetching picture: {e}")
            return None, None
        finally:
            cursor.close()
            connection.close()
    return None, None

# Initialize database
init_database()

# Lockout functions
def load_lockout_data():
    if os.path.exists(LOCKOUT_FILE):
        try:
            with open(LOCKOUT_FILE, 'r') as f:
                data = json.load(f)
                if data.get('lockout_until'):
                    data['lockout_until'] = datetime.fromisoformat(data['lockout_until'])
                return data
        except:
            pass
    return {'attempts': 0, 'lockout_until': None}

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

lockout_data = load_lockout_data()

# Session state initialization
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'admin_id' not in st.session_state:
    st.session_state.admin_id = None
if 'admin_username' not in st.session_state:
    st.session_state.admin_username = None
if 'admin_full_name' not in st.session_state:
    st.session_state.admin_full_name = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'login'
if 'songs' not in st.session_state:
    st.session_state.songs = []
if 'selected_song' not in st.session_state:
    st.session_state.selected_song = None
if 'show_modal' not in st.session_state:
    st.session_state.show_modal = False
if 'modal_song' not in st.session_state:
    st.session_state.modal_song = None
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
if 'login_username' not in st.session_state:
    st.session_state.login_username = ''
if 'login_password' not in st.session_state:
    st.session_state.login_password = ''
if 'reset_login' not in st.session_state:
    st.session_state.reset_login = False

def get_profile_image_html(admin_id, size=50):
    """Generate circular profile image HTML"""
    img_data, img_type = get_profile_picture(admin_id)
    
    if img_data:
        b64_encoded = base64.b64encode(img_data).decode()
        mime_type = img_type if img_type else "image/png"
        img_src = f"data:{mime_type};base64,{b64_encoded}"
    else:
        # Default avatar
        img_src = "https://via.placeholder.com/50"
    
    html = f"""
    <div style="
        width: {size}px;
        height: {size}px;
        border-radius: 50%;
        overflow: hidden;
        display: inline-block;
        border: 3px solid #fff;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    ">
        <img src="{img_src}" style="
            width: 100%;
            height: 100%;
            object-fit: cover;
        ">
    </div>
    """
    return html

def show_header_with_logout():
    """Display circular profile, name in top left and logout button in top right"""
    if st.session_state.authenticated and st.session_state.admin_id:
        admin_data = get_admin_by_id(st.session_state.admin_id)
        display_name = admin_data.get('full_name') or st.session_state.admin_username
        
        # Create two columns - left for profile, right for logout
        col_left, col_right = st.columns([6, 1])
        
        with col_left:
            # Profile section
            profile_col1, profile_col2 = st.columns([1, 10])
            with profile_col1:
                st.markdown(get_profile_image_html(st.session_state.admin_id, 50), unsafe_allow_html=True)
            with profile_col2:
                st.markdown(f"""
                    <div style="
                        display: flex;
                        align-items: center;
                        height: 50px;
                        font-weight: 600;
                        font-size: 16px;
                        color: #333;
                    ">
                        {display_name}
                    </div>
                """, unsafe_allow_html=True)
        
        with col_right:
            # Logout button in top right
            if st.button("🚪 Logout", use_container_width=True, key="header_logout_btn"):
                st.session_state.authenticated = False
                st.session_state.admin_id = None
                st.session_state.admin_username = None
                st.session_state.admin_full_name = None
                st.session_state.current_page = 'login'
                st.rerun()

# LOGIN PAGE - Clean Design with Box Shadow
if not st.session_state.authenticated and st.session_state.current_page == 'login':
    
    # Add custom CSS for login page styling
    st.markdown("""
        <style>
        /* Center the login container */
        .login-container {
            max-width: 450px;
            margin: 0 auto;
            padding: 40px;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15), 0 8px 25px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.3);
        }
        
        /* Title styling */
        .login-title {
            text-align: center;
            font-size: 2.5em;
            font-weight: 700;
            color: #333;
            margin-bottom: 10px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        /* Subtitle styling */
        .login-subtitle {
            text-align: center;
            font-size: 1em;
            color: #666;
            margin-bottom: 30px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        /* Icon styling */
        .login-icon {
            text-align: center;
            font-size: 4em;
            margin-bottom: 20px;
        }
        
        /* Input field styling */
        .stTextInput > div > div > input {
            border-radius: 10px;
            border: 2px solid #e0e0e0;
            padding: 12px 15px;
            font-size: 16px;
            transition: all 0.3s ease;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        /* Button styling */
        .stButton > button {
            border-radius: 10px;
            padding: 12px 30px;
            font-size: 16px;
            font-weight: 600;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        }
        
        /* Error message styling */
        .stAlert {
            border-radius: 10px;
        }
        
        /* Lockout message styling */
        .lockout-message {
            text-align: center;
            padding: 20px;
            background: #ffebee;
            border-radius: 10px;
            color: #c62828;
            font-weight: 600;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Check lockout
    current_time = datetime.now()
    if lockout_data['lockout_until'] and current_time < lockout_data['lockout_until']:
        remaining = lockout_data['lockout_until'] - current_time
        mins = int(remaining.total_seconds() / 60)
        secs = int(remaining.total_seconds() % 60)
        
        st.markdown(f"""
            <div class="login-container">
                <div class="lockout-message">
                    <div style="font-size: 3em; margin-bottom: 10px;">⏰</div>
                    <div>Account Locked</div>
                    <div style="font-size: 0.9em; margin-top: 10px;">
                        Wait {mins}m {secs}s to try again
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        st.stop()
    
    # Reset login fields if needed
    if st.session_state.reset_login:
        st.session_state.login_username = ''
        st.session_state.login_password = ''
        st.session_state.reset_login = False
    
    
    
    # Icon
    st.markdown('<div class="login-icon">🔐</div>', unsafe_allow_html=True)
    
    # Title
    st.markdown('<div class="login-title">Welcome Back</div>', unsafe_allow_html=True)
    
    # Subtitle
    st.markdown('<div class="login-subtitle">Please sign in to continue</div>', unsafe_allow_html=True)
    
    # Input fields
    username = st.text_input("Username", key="login_username", placeholder="Enter your username")
    password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
    
    # Login button
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        login_clicked = st.button("Sign In", use_container_width=True, key="login_btn")
    
    # Close container
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Handle login logic
    if login_clicked:
        if username and password:
            admin = verify_admin(username, password)
            if admin:
                st.session_state.authenticated = True
                st.session_state.admin_id = admin['id']
                st.session_state.admin_username = admin['username']
                st.session_state.admin_full_name = admin.get('full_name', admin['username'])
                st.session_state.current_page = 'dashboard'
                save_lockout_data(0, None)
                st.success("✅ Login successful!")
                st.rerun()
            else:
                new_attempts = lockout_data['attempts'] + 1
                if new_attempts >= 3:
                    lockout_time = current_time + timedelta(minutes=3)
                    save_lockout_data(new_attempts, lockout_time)
                    st.error("⛔ Too many failed attempts. Locked for 3 minutes.")
                else:
                    save_lockout_data(new_attempts, None)
                    remaining = 3 - new_attempts
                    st.error(f"❌ Invalid credentials. {remaining} attempts left.")
                
                st.session_state.reset_login = True
                st.rerun()
        else:
            st.error("Please fill in both fields.")
    
    st.stop()

# ADMIN DASHBOARD
elif st.session_state.authenticated and st.session_state.current_page == 'dashboard':
    # Show profile in top left and logout in top right
    show_header_with_logout()
    
    st.title("⚙️ Admin Dashboard")
    
    admin_data = get_admin_by_id(st.session_state.admin_id)
    
    tab1, tab2, tab3 = st.tabs(["👤 Profile", "🔒 Security", "🎵 Go to App"])
    
    with tab1:
        st.subheader("Update Profile")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("### Profile Picture")
            # Show larger circular preview
            st.markdown(get_profile_image_html(st.session_state.admin_id, 150), unsafe_allow_html=True)
            
            st.markdown("---")
            st.info("💡 Max file size: **500MB** | All image formats accepted")
            
            # CSS to hide Streamlit's default file size limit text
            st.markdown("""
                <style>
                /* Hide the default Streamlit file uploader size text */
                .stFileUploader [data-testid="stFileUploader"] div div small,
                .stFileUploader [data-testid="stFileUploader"] small,
                .stFileUploader div small,
                .stFileUploader > div > div > div > small,
                .stFileUploader > div > div > small,
                .stFileUploader small {
                    display: none !important;
                    visibility: hidden !important;
                    opacity: 0 !important;
                }
                /* Hide any element containing MB text in file uploader */
                .stFileUploader [data-testid="stFileUploader"] * {
                    font-size: 0px !important;
                }
                .stFileUploader [data-testid="stFileUploader"] button,
                .stFileUploader [data-testid="stFileUploader"] input {
                    font-size: 14px !important;
                }
                </style>
            """, unsafe_allow_html=True)
            
            # Upload with no size limit and all types accepted
            uploaded_file = st.file_uploader(
                "Choose an image", 
                type=None,  # Accept all file types
                accept_multiple_files=False,
                help="Upload any image file (up to 500MB)"
            )
            
            if uploaded_file is not None:
                # Check file size (500MB = 524288000 bytes)
                file_size = len(uploaded_file.getvalue())
                max_size = 524288000  # 500MB in bytes
                
                if file_size > max_size:
                    st.error(f"❌ File too large! Size: {file_size / (1024*1024):.2f}MB | Max: 500MB")
                else:
                    st.success(f"✅ File selected: {uploaded_file.name} ({file_size / (1024*1024):.2f}MB)")
                    
                    # Preview before upload
                    try:
                        image = Image.open(uploaded_file)
                        st.image(image, caption="Preview", width=200)
                    except:
                        st.warning("⚠️ Cannot preview this file type, but it can still be uploaded")
                    
                    if st.button("💾 Save Picture", key="save_pic"):
                        # Reset file pointer
                        uploaded_file.seek(0)
                        image_bytes = uploaded_file.read()
                        image_type = uploaded_file.type if uploaded_file.type else "application/octet-stream"
                        
                        if update_profile_picture(st.session_state.admin_id, image_bytes, image_type):
                            st.success("✅ Picture uploaded successfully!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to upload picture")
        
        with col2:
            with st.form("profile_form"):
                full_name = st.text_input("Full Name", value=admin_data.get('full_name', '') if admin_data else '')
                email = st.text_input("Email", value=admin_data.get('email', '') if admin_data else '')
                phone = st.text_input("Phone", value=admin_data.get('phone', '') if admin_data else '')
                bio = st.text_area("Bio", value=admin_data.get('bio', '') if admin_data else '', height=100)
                
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.form_submit_button("💾 Save Profile", use_container_width=True):
                        if update_admin_profile(st.session_state.admin_id, full_name, email, phone, bio):
                            st.session_state.admin_full_name = full_name
                            st.success("✅ Profile updated!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to update profile")
                with col_cancel:
                    if st.form_submit_button("🔄 Reset", use_container_width=True):
                        st.rerun()
    
    with tab2:
        st.subheader("🔐 Change Username")
        st.markdown(f"Current username: **{st.session_state.admin_username}**")
        
        with st.form("username_form"):
            new_username = st.text_input("New Username", placeholder="Enter new username")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Enter current password to confirm")
            
            if st.form_submit_button("💾 Update Username", use_container_width=True):
                if not new_username or not confirm_password:
                    st.error("Please fill in all fields.")
                elif confirm_password != admin_data['password']:
                    st.error("❌ Password is incorrect.")
                elif len(new_username) < 3:
                    st.error("❌ Username must be at least 3 characters.")
                elif new_username == st.session_state.admin_username:
                    st.error("❌ New username cannot be the same as current username.")
                else:
                    success, message = update_admin_username(st.session_state.admin_id, new_username)
                    if success:
                        st.session_state.admin_username = new_username
                        st.success(f"✅ {message}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
        
        st.markdown("---")
        st.subheader("🔐 Change Password")
        with st.form("password_form"):
            current_pass = st.text_input("Current Password", type="password")
            new_pass = st.text_input("New Password", type="password")
            confirm_pass = st.text_input("Confirm New Password", type="password")
            
            if st.form_submit_button("🔐 Update Password", use_container_width=True):
                if not current_pass or not new_pass or not confirm_pass:
                    st.error("Please fill all fields.")
                elif current_pass != admin_data['password']:
                    st.error("❌ Current password is incorrect.")
                elif new_pass != confirm_pass:
                    st.error("❌ New passwords do not match.")
                elif len(new_pass) < 4:
                    st.error("❌ Password must be at least 4 characters.")
                else:
                    if update_admin_password(st.session_state.admin_id, new_pass):
                        st.success("✅ Password updated! Please login again.")
                        st.session_state.authenticated = False
                        st.session_state.current_page = 'login'
                        st.rerun()
                    else:
                        st.error("❌ Failed to update password.")
    
    with tab3:
        st.subheader("🎵 Song Randomizer App")
        st.markdown("Click below to access the main application.")
        if st.button("🚀 Launch App", use_container_width=True):
            st.session_state.current_page = 'home'
            st.rerun()

# MAIN APP (SONG RANDOMIZER)
elif st.session_state.authenticated and st.session_state.current_page in ['home', 'list']:
    
    # Show profile in top left and logout in top right
    show_header_with_logout()
    
    # Reset form if needed
    if st.session_state.reset_form:
        st.session_state.person_name = ''
        st.session_state.song_title = ''
        st.session_state.artist = ''
        st.session_state.reset_form = False
    
    st.session_state.songs = load_songs_from_db()
    
    st.title("🎵 Random Song Selector")
    
    # BACK BUTTON - Returns to Admin Dashboard
    if st.button("⬅️ Back to Dashboard", use_container_width=True, key="back_to_dashboard"):
        st.session_state.current_page = 'dashboard'
        st.rerun()
    
    st.markdown("---")
    
    # Right-click protection
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
    
    # MODAL POPUP - Display on top of current page if active
    if st.session_state.show_modal and st.session_state.modal_song:
        song = st.session_state.modal_song
        
        # Create full-screen modal overlay
        modal_html = f"""
        <div id="songModal" style="
            position: fixed;
            z-index: 99999;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.85);
            display: flex;
            justify-content: center;
            align-items: center;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        ">
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 60px;
                border-radius: 30px;
                text-align: center;
                max-width: 650px;
                width: 90%;
                box-shadow: 0 30px 100px rgba(0,0,0,0.5);
                position: relative;
                animation: popIn 0.5s ease-out;
                color: white;
                border: 3px solid rgba(255,255,255,0.3);
            ">
                <div style="font-size: 100px; margin-bottom: 30px; animation: bounce 1s infinite;">🎉</div>
                
                <h1 style="
                    font-size: 3em;
                    margin: 0 0 20px 0;
                    text-shadow: 4px 4px 8px rgba(0,0,0,0.4);
                    font-weight: bold;
                    line-height: 1.2;
                ">"{song['song_title']}"</h1>
                
                <p style="
                    font-size: 2em;
                    margin: 0 0 40px 0;
                    opacity: 0.95;
                    font-weight: 500;
                ">by {song['artist']}</p>
                
                <div style="
                    background: rgba(255,255,255,0.25);
                    padding: 25px;
                    border-radius: 20px;
                    font-size: 1.5em;
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255,255,255,0.3);
                ">
                    👤 Picked by: <strong style="font-size: 1.2em;">{song['person_name']}</strong>
                </div>
                
                <button onclick="closeModal()" style="
                    margin-top: 40px;
                    padding: 18px 50px;
                    font-size: 1.3em;
                    background: white;
                    color: #764ba2;
                    border: none;
                    border-radius: 50px;
                    cursor: pointer;
                    font-weight: bold;
                    transition: all 0.3s;
                    box-shadow: 0 6px 20px rgba(0,0,0,0.3);
                " onmouseover="this.style.transform='scale(1.08)'; this.style.boxShadow='0 8px 25px rgba(0,0,0,0.4)'" 
                onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 6px 20px rgba(0,0,0,0.3)'">
                    🎵 Awesome! Close
                </button>
            </div>
        </div>
        
        <style>
        @keyframes popIn {{
            0% {{ transform: scale(0.3); opacity: 0; }}
            70% {{ transform: scale(1.05); opacity: 1; }}
            100% {{ transform: scale(1); opacity: 1; }}
        }}
        @keyframes bounce {{
            0%, 100% {{ transform: translateY(0); }}
            50% {{ transform: translateY(-20px); }}
        }}
        </style>
        
        <script>
        function closeModal() {{
            document.getElementById('songModal').style.display = 'none';
        }}
        
        // Close on outside click
        document.getElementById('songModal').addEventListener('click', function(e) {{
            if (e.target === this) {{
                closeModal();
            }}
        }});
        
        // Close on Escape key
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') {{
                closeModal();
            }}
        }});
        </script>
        """
        
        components.html(modal_html, height=800)
        
        # Add a close button for Streamlit to reset state
        if st.button("❌ Close", key="close_modal_btn"):
            st.session_state.show_modal = False
            st.session_state.modal_song = None
            st.rerun()
    
    if st.session_state.current_page == 'home':
        st.markdown("Add songs to your list and randomly pick one!")
        
        if st.session_state.success_message:
            st.success("You added a song to the song list")
            if st.button("Song List", key="goto_song_list_msg"):
                st.session_state.current_page = 'list'
                st.session_state.success_message = ''
                st.rerun()
        
        st.subheader("Add New Song")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            person_name = st.text_input("Person Name", placeholder="e.g., John Doe", key="person_name")
        
        with col2:
            song_title = st.text_input("Song Title", placeholder="e.g., Bohemian Rhapsody", key="song_title")
        
        with col3:
            artist = st.text_input("Artist", placeholder="e.g., Queen", key="artist")
        
        btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2])
        
        with btn_col1:
            if st.button("➕ Add Song", use_container_width=True, key="add_song_btn"):
                if person_name and song_title and artist:
                    success, message = add_song_to_db(person_name, song_title, artist)
                    if success:
                        st.session_state.success_message = message
                        st.session_state.songs = load_songs_from_db()
                        st.session_state.reset_form = True
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Please fill in all fields!")
        
        with btn_col2:
            if st.button("📋 Song List", use_container_width=True, key="goto_list_btn"):
                st.session_state.current_page = 'list'
                st.rerun()
    
    elif st.session_state.current_page == 'list':
        st.subheader("Song List")
        
        if st.session_state.songs:
            for idx, song in enumerate(st.session_state.songs, 1):
                row_col1, row_col2 = st.columns([4, 1])
                with row_col1:
                    st.markdown(f"**{idx}. {song['person_name']}** - \"{song['song_title']}\" by {song['artist']}")
                with row_col2:
                    if st.button("🗑️ Delete", key=f"delete_{idx}", use_container_width=True):
                        if delete_song_from_db(song['person_name'], song['song_title']):
                            st.success(f"Deleted '{song['song_title']}'")
                            st.session_state.songs = load_songs_from_db()
                            if st.session_state.selected_song and st.session_state.selected_song['song_title'] == song['song_title']:
                                st.session_state.selected_song = None
                            st.rerun()
                        else:
                            st.error("Failed to delete")
        else:
            st.info("No songs added yet. Add some songs!")
        
        st.markdown("---")
        
        # Pick Random Song Button with Modal
        if st.button("🎲 Pick Random Song", key="pick_random", use_container_width=True):
            if st.session_state.songs:
                selected = random.choice(st.session_state.songs)
                st.session_state.modal_song = selected
                st.session_state.show_modal = True
                st.session_state.selected_song = selected
                # Stay on same page, just show modal
                st.rerun()
            else:
                st.warning("No songs available to pick.")
        
        st.markdown("---")
        if st.button("⬅️ Back to Add Song", key="back_home", use_container_width=True):
            st.session_state.current_page = 'home'
            st.rerun()