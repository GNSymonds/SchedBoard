import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os
from pathlib import Path

# Page config
st.set_page_config(
    page_title="Camp Tracker",
    page_icon="🏕️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database setup
DB_PATH = "camp_tracker.db"

def init_db():
    """Initialize database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Personnel manifest table
    c.execute('''
        CREATE TABLE IF NOT EXISTS personnel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            phone TEXT,
            supervisor TEXT,
            supervisor_phone TEXT,
            company TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Departures table
    c.execute('''
        CREATE TABLE IF NOT EXISTS departures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_name TEXT NOT NULL,
            destination TEXT NOT NULL,
            departed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expected_return TIMESTAMP NOT NULL,
            actual_return TIMESTAMP,
            phone TEXT,
            supervisor TEXT,
            company TEXT,
            extensions_count INTEGER DEFAULT 0,
            is_overdue BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Extensions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS extensions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            departure_id INTEGER,
            hours_extended INTEGER,
            extended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (departure_id) REFERENCES departures (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_personnel():
    """Get all personnel from manifest"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM personnel ORDER BY name", conn)
    conn.close()
    return df

def add_personnel(name, phone=None, supervisor=None, supervisor_phone=None, company=None):
    """Add or update a person in the manifest"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        INSERT OR REPLACE INTO personnel (name, phone, supervisor, supervisor_phone, company, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (name, phone, supervisor, supervisor_phone, company))
    
    conn.commit()
    conn.close()

def get_active_departures():
    """Get all active (not returned) departures"""
    conn = sqlite3.connect(DB_PATH)
    query = '''
        SELECT *, 
               CASE 
                   WHEN datetime(expected_return) < datetime('now') THEN 1 
                   ELSE 0 
               END as is_overdue
        FROM departures 
        WHERE actual_return IS NULL 
        ORDER BY expected_return
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def add_departure(person_name, destination, expected_return, phone=None, supervisor=None, company=None):
    """Log a new departure"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO departures (person_name, destination, expected_return, phone, supervisor, company)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (person_name, destination, expected_return, phone, supervisor, company))
    
    conn.commit()
    conn.close()

def mark_returned(departure_id):
    """Mark a departure as returned"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        UPDATE departures 
        SET actual_return = CURRENT_TIMESTAMP 
        WHERE id = ?
    ''', (departure_id,))
    
    conn.commit()
    conn.close()

def extend_departure(departure_id, hours):
    """Extend a departure's expected return time"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Add extension record
    c.execute('''
        INSERT INTO extensions (departure_id, hours_extended)
        VALUES (?, ?)
    ''', (departure_id, hours))
    
    # Update expected return and extension count
    c.execute('''
        UPDATE departures 
        SET expected_return = datetime(expected_return, '+' || ? || ' hours'),
            extensions_count = extensions_count + 1
        WHERE id = ?
    ''', (hours, departure_id))
    
    conn.commit()
    conn.close()

def upload_manifest(df):
    """Upload personnel manifest from dataframe"""
    conn = sqlite3.connect(DB_PATH)
    
    # Standardize column names
    column_mapping = {
        'full name': 'name',
        'fullname': 'name',
        'employee name': 'name',
        'mobile': 'phone',
        'cell': 'phone',
        'phone number': 'phone',
        'manager': 'supervisor',
        'supervisor name': 'supervisor',
        'manager phone': 'supervisor_phone',
        'supervisor phone': 'supervisor_phone',
        'organization': 'company',
        'employer': 'company'
    }
    
    # Rename columns based on mapping
    df.columns = [column_mapping.get(col.lower(), col.lower()) for col in df.columns]
    
    # Ensure required columns exist
    required_cols = ['name', 'phone', 'supervisor', 'supervisor_phone', 'company']
    for col in required_cols:
        if col not in df.columns:
            df[col] = None
    
    # Upload to database (upsert)
    for _, row in df.iterrows():
        if pd.notna(row['name']):
            add_personnel(
                row['name'],
                row.get('phone'),
                row.get('supervisor'),
                row.get('supervisor_phone'),
                row.get('company')
            )
    
    conn.close()

# Initialize database
init_db()

# Sidebar navigation
page = st.sidebar.radio("Navigation", ["📝 Departure Form", "📊 Tracker & Management"])

if page == "📝 Departure Form":
    st.title("🏕️ Camp Departure Form")
    
    # Get personnel list
    personnel_df = get_personnel()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Create form
        with st.form("departure_form", clear_on_submit=True):
            # Name selection
            if not personnel_df.empty:
                name_options = ["-- Add New Person --"] + personnel_df['name'].tolist()
                selected_name = st.selectbox("Name", name_options)
                
                if selected_name == "-- Add New Person --":
                    new_name = st.text_input("Enter Name", key="new_name")
                    new_phone = st.text_input("Phone Number (optional)", key="new_phone")
                    new_supervisor = st.text_input("Supervisor (optional)", key="new_supervisor")
                    new_company = st.text_input("Company (optional)", key="new_company")
                else:
                    # Get person's details from manifest
                    person = personnel_df[personnel_df['name'] == selected_name].iloc[0]
                    new_name = None
            else:
                st.info("No personnel in manifest. Add new person below.")
                selected_name = None
                new_name = st.text_input("Name", key="new_name")
                new_phone = st.text_input("Phone Number (optional)", key="new_phone")
                new_supervisor = st.text_input("Supervisor (optional)", key="new_supervisor")
                new_company = st.text_input("Company (optional)", key="new_company")
            
            # Destination
            destination = st.text_input("Destination", key="destination")
            
            # Expected duration
            col_date, col_time = st.columns(2)
            with col_date:
                duration_hours = st.selectbox(
                    "Expected Duration",
                    options=[1, 2, 3, 4, 5, 6, 8, 12, 24],
                    index=2,  # Default to 3 hours
                    format_func=lambda x: f"{x} hour{'s' if x > 1 else ''}"
                )
            
            with col_time:
                departure_time = st.time_input("Departure Time", value=datetime.now().time())
            
            # Calculate expected return
            departure_datetime = datetime.combine(datetime.now().date(), departure_time)
            expected_return = departure_datetime + timedelta(hours=duration_hours)
            
            st.info(f"Expected return: {expected_return.strftime('%I:%M %p')}")
            
            # Submit button
            submitted = st.form_submit_button("Log Departure", use_container_width=True, type="primary")
            
            if submitted:
                if new_name:  # New person
                    if new_name.strip():
                        add_personnel(new_name, new_phone, new_supervisor, None, new_company)
                        add_departure(new_name, destination, expected_return, new_phone, new_supervisor, new_company)
                        st.success(f"✅ {new_name} logged as departed to {destination}")
                    else:
                        st.error("Please enter a name")
                elif selected_name and selected_name != "-- Add New Person --":  # Existing person
                    person = personnel_df[personnel_df['name'] == selected_name].iloc[0]
                    add_departure(
                        selected_name, 
                        destination, 
                        expected_return,
                        person.get('phone'),
                        person.get('supervisor'),
                        person.get('company')
                    )
                    st.success(f"✅ {selected_name} logged as departed to {destination}")
                else:
                    st.error("Please select or enter a name")
    
    with col2:
        # Quick stats
        st.markdown("### 📊 Current Status")
        active_departures = get_active_departures()
        
        metric_col1, metric_col2 = st.columns(2)
        with metric_col1:
            st.metric("Currently Out", len(active_departures))
        with metric_col2:
            overdue_count = len(active_departures[active_departures['is_overdue'] == 1])
            st.metric("Overdue", overdue_count, delta_color="inverse")
        
        if overdue_count > 0:
            st.error(f"⚠️ {overdue_count} people are overdue!")

elif page == "📊 Tracker & Management":
    st.title("🏕️ Camp Tracker & Management")
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📍 Active Departures", "📋 Personnel Manifest", "📈 Statistics"])
    
    with tab1:
        active_departures = get_active_departures()
        
        if active_departures.empty:
            st.success("✅ Everyone is in camp!")
        else:
            # Display active departures
            for _, dep in active_departures.iterrows():
                # Calculate time remaining
                expected_return = pd.to_datetime(dep['expected_return'])
                time_remaining = expected_return - datetime.now()
                hours_remaining = time_remaining.total_seconds() / 3600
                
                # Determine status
                if dep['is_overdue']:
                    status_color = "🔴"
                    status_text = f"OVERDUE by {abs(int(hours_remaining))}h {abs(int((hours_remaining % 1) * 60))}m"
                elif hours_remaining < 0.5:
                    status_color = "🟡"
                    status_text = f"{int(hours_remaining * 60)}m remaining"
                else:
                    status_color = "🟢"
                    status_text = f"{int(hours_remaining)}h {int((hours_remaining % 1) * 60)}m remaining"
                
                # Create card
                with st.container():
                    col1, col2, col3 = st.columns([3, 2, 2])
                    
                    with col1:
                        st.markdown(f"### {status_color} {dep['person_name']}")
                        st.caption(f"📍 {dep['destination']} • 🏢 {dep['company'] or 'N/A'}")
                        st.caption(f"🕐 Departed: {pd.to_datetime(dep['departed_at']).strftime('%I:%M %p')}")
                        if dep['extensions_count'] > 0:
                            st.caption(f"🔄 Extended {dep['extensions_count']} time(s)")
                    
                    with col2:
                        st.markdown(f"**{status_text}**")
                        
                        # Quick extend buttons
                        col_ext1, col_ext2, col_ext3 = st.columns(3)
                        with col_ext1:
                            if st.button("+1h", key=f"ext1_{dep['id']}"):
                                extend_departure(dep['id'], 1)
                                st.rerun()
                        with col_ext2:
                            if st.button("+2h", key=f"ext2_{dep['id']}"):
                                extend_departure(dep['id'], 2)
                                st.rerun()
                        with col_ext3:
                            if st.button("+3h", key=f"ext3_{dep['id']}"):
                                extend_departure(dep['id'], 3)
                                st.rerun()
                    
                    with col3:
                        if st.button("✅ Mark Returned", key=f"return_{dep['id']}", type="primary"):
                            mark_returned(dep['id'])
                            st.success(f"{dep['person_name']} marked as returned")
                            st.rerun()
                    
                    st.divider()
    
    with tab2:
        st.subheader("Personnel Manifest Upload")
        
        # File uploader
        uploaded_file = st.file_uploader(
            "Upload CSV file", 
            type=['csv'],
            help="CSV should contain: Name, Phone, Supervisor, SupervisorPhone, Company"
        )
        
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                st.write("Preview of uploaded data:")
                st.dataframe(df.head())
                
                if st.button("Upload to Manifest", type="primary"):
                    upload_manifest(df)
                    st.success(f"✅ Uploaded {len(df)} records to manifest")
                    st.rerun()
            except Exception as e:
                st.error(f"Error reading CSV: {str(e)}")
        
        # Display current manifest
        st.subheader("Current Personnel Manifest")
        personnel_df = get_personnel()
        
        if not personnel_df.empty:
            # Add search/filter
            search = st.text_input("Search personnel", placeholder="Type to search...")
            if search:
                mask = personnel_df['name'].str.contains(search, case=False, na=False)
                filtered_df = personnel_df[mask]
            else:
                filtered_df = personnel_df
            
            st.dataframe(
                filtered_df[['name', 'phone', 'supervisor', 'company']], 
                use_container_width=True,
                hide_index=True
            )
            
            # Download manifest
            csv = personnel_df.to_csv(index=False)
            st.download_button(
                label="Download Manifest as CSV",
                data=csv,
                file_name=f"personnel_manifest_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No personnel in manifest yet. Upload a CSV to get started.")
    
    with tab3:
        st.subheader("Statistics")
        
        # Get all departures
        conn = sqlite3.connect(DB_PATH)
        all_departures = pd.read_sql_query("SELECT * FROM departures", conn)
        conn.close()
        
        if not all_departures.empty:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_out = len(get_active_departures())
                st.metric("Currently Out", total_out)
            
            with col2:
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                today_returns = len(all_departures[
                    (pd.to_datetime(all_departures['actual_return']) >= today_start) & 
                    (all_departures['actual_return'].notna())
                ])
                st.metric("Returned Today", today_returns)
            
            with col3:
                total_departures_today = len(all_departures[
                    pd.to_datetime(all_departures['departed_at']) >= today_start
                ])
                st.metric("Departures Today", total_departures_today)
            
            with col4:
                avg_duration = all_departures[all_departures['actual_return'].notna()].apply(
                    lambda x: (pd.to_datetime(x['actual_return']) - pd.to_datetime(x['departed_at'])).total_seconds() / 3600,
                    axis=1
                ).mean()
                st.metric("Avg Duration", f"{avg_duration:.1f}h" if pd.notna(avg_duration) else "N/A")
            
            # Most frequent destinations
            st.subheader("Top Destinations")
            top_destinations = all_departures['destination'].value_counts().head(10)
            st.bar_chart(top_destinations)
        else:
            st.info("No departure data available yet.")

# Custom CSS
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        padding-left: 20px;
        padding-right: 20px;
    }
</style>
""", unsafe_allow_html=True)