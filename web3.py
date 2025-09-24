import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
import re
import pandas as pd
import time
from typing import List, Dict, Optional
from collections import defaultdict
import os

# --- Helper Functions for JSON File Operations ---
def save_bookings_to_json(bookings: List[Dict], filename: str = 'bookings.json'):
    """Save bookings data to a local JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(bookings, f, indent=2, ensure_ascii=False)
        st.success(f"Bookings saved to '{filename}'!")
    except IOError as e:
        st.error(f"Error saving file: {e}")

def load_bookings_from_json(filename: str = 'bookings.json') -> List[Dict]:
    """Load bookings data from a local JSON file."""
    if not os.path.exists(filename):
        st.warning(f"File '{filename}' not found. Please refresh bookings first.")
        return []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            bookings = json.load(f)
        st.success(f"Bookings loaded from '{filename}'!")
        return bookings
    except (IOError, json.JSONDecodeError) as e:
        st.error(f"Error loading file: {e}")
        return []

# --- TripaneerScraper Class (No major changes) ---
class TripaneerScraper:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://office.tripaneer.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session.headers.update(self.headers)
        self.logged_in = False

    def login(self, username: str, password: str) -> bool:
        """Login to Tripaneer"""
        login_url = f"{self.base_url}/4/login/"
        
        try:
            response = self.session.get(login_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            csrf_token = None
            csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
            if csrf_input:
                csrf_token = csrf_input.get('value')
            
            login_data = {
                'username': username,
                'password': password,
            }
            
            if csrf_token:
                login_data['csrfmiddlewaretoken'] = csrf_token
            
            response = self.session.post(login_url, data=login_data, allow_redirects=True)
            
            if response.status_code == 200:
                self.logged_in = True
                return True
            else:
                return False
                
        except Exception as e:
            st.error(f"Login error: {e}")
            return False

    def calculate_nights(self, arrival_date: str, departure_date: str) -> int:
        """Calculate number of nights based on arrival and departure dates"""
        try:
            arrival = datetime.strptime(arrival_date, "%Y-%b-%d")
            departure = datetime.strptime(departure_date, "%Y-%b-%d")
            nights = (departure - arrival).days
            return max(nights, 1)
        except ValueError:
            return 0

    def determine_hostel(self, package_name: str) -> str:
        """Determine hostel based on package name"""
        package_name_lower = package_name.lower()
        if "7 day" in package_name_lower and "taghazout" in package_name_lower:
            return "Taghazout"
        else:
            return "Tamraght"

    def extract_guest_and_room_info(self, conversation_link: str) -> tuple:
        """Extract guest count and room type from conversation page"""
        guests = "Not found"
        room_type = "Not found"
        
        try:
            response = self.session.get(conversation_link)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                guest_elements = soup.find_all(['div'], class_=re.compile(r'col-xs-6|col-md-4'))
                for element in guest_elements:
                    dt_element = element.find('dt')
                    if dt_element and 'Guests' in dt_element.text:
                        dd_element = element.find('dd')
                        if dd_element:
                            guests_text = dd_element.get_text(strip=True)
                            numbers = re.findall(r'\d+', guests_text)
                            guests = numbers[0] if numbers else guests_text
                            break
                
                room_elements = soup.find_all(['div'], class_=re.compile(r'col-xs-6|col-lg-8'))
                for element in room_elements:
                    dt_element = element.find('dt')
                    if dt_element and 'Room' in dt_element.text:
                        dd_element = element.find('dd')
                        if dd_element:
                            room_text = dd_element.get_text(strip=True)
                            room_type = room_text.split('\n')[0] if '\n' in room_text else room_text
                            break
                
        except Exception as e:
            st.warning(f"Error extracting guest/room info: {e}")
        
        return guests, room_type

    def extract_bookings_from_list(self, booking_list, booking_type: str = "current") -> List[Dict]:
        """Extract bookings from a specific list (current or upcoming)"""
        if not booking_list:
            return []
            
        booking_items = booking_list.find_all('li')
        
        bookings = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for index, item in enumerate(booking_items):
            try:
                progress = (index + 1) / len(booking_items)
                progress_bar.progress(progress)
                status_text.text(f"Processing {booking_type} booking {index + 1} of {len(booking_items)}...")
                
                customer_name_elem = item.find('div', class_='customer-name')
                full_name = customer_name_elem.find('strong').get_text(strip=True) if customer_name_elem else "Not found"
                
                listing_title_elem = item.find('div', class_='listing-title')
                package_name = listing_title_elem.find('p').get_text(strip=True) if listing_title_elem else "Not found"
                
                inquiry_meta = item.find('div', class_='inquiry-meta')
                if inquiry_meta:
                    strong_elements = inquiry_meta.find_all('strong')
                    price = strong_elements[0].get_text(strip=True) if len(strong_elements) > 0 else "Not found"
                    arrival_date = strong_elements[1].get_text(strip=True) if len(strong_elements) > 1 else "Not found"
                    departure_date = strong_elements[2].get_text(strip=True) if len(strong_elements) > 2 else "Not found"
                else:
                    price = arrival_date = departure_date = "Not found"
                
                nights = self.calculate_nights(arrival_date, departure_date) if arrival_date != "Not found" and departure_date != "Not found" else 0
                
                hostel = self.determine_hostel(package_name)
                
                conversation_link = None
                link_elem = item.find('a', class_='btn btn-info')
                if link_elem and link_elem.get('href'):
                    conversation_link = f"{self.base_url}{link_elem['href']}"
                else:
                    mobile_link = item.find('a', class_='mobile-link')
                    if mobile_link and mobile_link.get('href'):
                        conversation_link = f"{self.base_url}{mobile_link['href']}"
                
                guests = "Not available"
                room_type = "Not available"
                
                if conversation_link:
                    guests, room_type = self.extract_guest_and_room_info(conversation_link)
                
                booking_data = {
                    "full_name": full_name,
                    "package_name": package_name,
                    "hostel": hostel,
                    "price": price,
                    "arrival_date": arrival_date,
                    "departure_date": departure_date,
                    "number_of_nights": nights,
                    "number_of_guests": guests,
                    "room_type": room_type,
                    "conversation_link": conversation_link,
                    "booking_type": booking_type.capitalize()
                }
                
                bookings.append(booking_data)
                
            except Exception as e:
                st.warning(f"Error extracting {booking_type} booking {index + 1}: {e}")
                continue
        
        progress_bar.empty()
        status_text.empty()
        return bookings

    def extract_booking_data(self) -> List[Dict]:
        """Extract booking data from the bookings overview page including both current and upcoming"""
        if not self.logged_in:
            st.error("Please login first")
            return []
            
        bookings_url = f"{self.base_url}/4/organizers/65639/bookings-overview/"
        
        try:
            with st.spinner("Fetching bookings page..."):
                response = self.session.get(bookings_url)
                if response.status_code != 200:
                    st.error(f"Failed to fetch bookings page: {response.status_code}")
                    return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            booking_lists = soup.find_all('ul', class_='recent-inquiries--new')
            
            all_bookings = []
            
            if len(booking_lists) > 0:
                with st.spinner("Extracting current bookings..."):
                    current_bookings = self.extract_bookings_from_list(booking_lists[0], "current")
                    all_bookings.extend(current_bookings)
            else:
                st.info("No current bookings list found")
            
            if len(booking_lists) > 1:
                with st.spinner("Extracting upcoming bookings..."):
                    upcoming_bookings = self.extract_bookings_from_list(booking_lists[1], "upcoming")
                    all_bookings.extend(upcoming_bookings)
            else:
                st.info("No upcoming bookings list found")
            
            return all_bookings
            
        except Exception as e:
            st.error(f"Error fetching bookings page: {e}")
            return []

# --- Display Functions ---
def display_booking_stats(bookings: List[Dict]):
    """Display booking statistics"""
    if not bookings:
        return
    
    st.subheader("📊 Booking Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_bookings = len(bookings)
    current_bookings = sum(1 for b in bookings if b['booking_type'] == 'Current')
    upcoming_bookings = sum(1 for b in bookings if b['booking_type'] == 'Upcoming')
    
    total_guests = 0
    for booking in bookings:
        try:
            if booking['number_of_guests'] != "Not found" and booking['number_of_guests'] != "Not available":
                total_guests += int(booking['number_of_guests'])
        except (ValueError, TypeError):
            pass
    
    with col1:
        st.metric("Total Bookings", total_bookings)
    with col2:
        st.metric("Current Bookings", current_bookings)
    with col3:
        st.metric("Upcoming Bookings", upcoming_bookings)
    with col4:
        st.metric("Total Guests", total_guests)

def display_bookings_table(bookings: List[Dict]):
    """Display bookings in a table format"""
    if not bookings:
        st.info("No bookings found")
        return
    
    df_data = []
    for booking in bookings:
        df_data.append({
            'Type': booking['booking_type'],
            'Source': booking.get('source', 'tripaneer').capitalize(),
            'Name': booking['full_name'],
            'Hostel': booking['hostel'],
            'Arrival': booking['arrival_date'],
            'Departure': booking['departure_date'],
            'Nights': booking['number_of_nights'],
            'Guests': booking['number_of_guests'],
            'Room Type': booking['room_type'],
            'Price': booking['price'],
            'Conversation': booking['conversation_link']
        })
    
    df = pd.DataFrame(df_data)
    
    manual_booking_style = """
        <style>
            .st-row-manual {
                background-color: #ffcccc; /* Light red */
            }
        </style>
    """
    st.markdown(manual_booking_style, unsafe_allow_html=True)
    
    def make_clickable(row):
        url = row['Conversation']
        source = row['Source']
        html_class = "st-row-manual" if source == 'Manual' else ""
        
        if url and url != "Not found":
            link_html = f'<a href="{url}" target="_blank">View Conversation</a>'
        else:
            link_html = "No link"
        
        return f'<tr class="{html_class}"><td>{row["Type"]}</td><td>{row["Source"]}</td><td>{row["Name"]}</td><td>{row["Hostel"]}</td><td>{row["Arrival"]}</td><td>{row["Departure"]}</td><td>{row["Nights"]}</td><td>{row["Guests"]}</td><td>{row["Room Type"]}</td><td>{row["Price"]}</td><td>{link_html}</td></tr>'

    df_html = df.to_html(escape=False, index=False)
    
    header = df_html.split('</thead>')[0] + '</thead>'
    rows = "".join(make_clickable(df.iloc[i]) for i in range(len(df)))
    
    custom_html_table = header + '<tbody>' + rows + '</tbody></table>'
    
    st.markdown(custom_html_table, unsafe_allow_html=True)

def display_current_guests_by_hostel(bookings: List[Dict]):
    """Display current guests grouped by hostel with room information"""
    st.subheader("🏨 Current Guests by Hostel")
    
    current_bookings = [b for b in bookings if b['booking_type'] == 'Current']
    
    if not current_bookings:
        st.info("No current guests found")
        return
    
    hostel_groups = defaultdict(list)
    for booking in current_bookings:
        hostel_groups[booking['hostel']].append(booking)
    
    for hostel, bookings_list in hostel_groups.items():
        st.markdown(f"### {hostel} Hostel")
        
        room_groups = defaultdict(list)
        for booking in bookings_list:
            room_type = booking['room_type'] if booking['room_type'] != "Not found" else "Unknown Room"
            room_groups[room_type].append(booking)
        
        for room_type, room_bookings in room_groups.items():
            with st.expander(f"{room_type} ({len(room_bookings)} guests)"):
                for booking in room_bookings:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{booking['full_name']}** - {booking['number_of_guests']} guest(s)")
                        st.write(f"Departure: {booking['departure_date']}")
                        if 'source' in booking and booking['source'] == 'manual':
                            st.markdown("_(Manual Booking)_")
                    with col2:
                        if booking['conversation_link'] and booking['conversation_link'] != "Not found":
                            st.markdown(f"[View]({booking['conversation_link']})")

def display_todays_movements(bookings: List[Dict]):
    """Display today's and tomorrow's arrivals and departures"""
    st.subheader("📅 Today's & Tomorrow's Movements")
    
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    
    def parse_date(date_str):
        try:
            return datetime.strptime(date_str, "%Y-%b-%d").date()
        except (ValueError, TypeError):
            return None
    
    today_arrivals = []
    today_departures = []
    tomorrow_arrivals = []
    tomorrow_departures = []
    
    for booking in bookings:
        arrival_date = parse_date(booking['arrival_date'])
        departure_date = parse_date(booking['departure_date'])
        
        if arrival_date == today:
            today_arrivals.append(booking)
        elif arrival_date == tomorrow:
            tomorrow_arrivals.append(booking)
        
        if departure_date == today:
            today_departures.append(booking)
        elif departure_date == tomorrow:
            tomorrow_departures.append(booking)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Today")
        
        st.markdown("##### 🚀 Arrivals")
        if today_arrivals:
            for booking in today_arrivals:
                st.write(f"**{booking['full_name']}** - {booking['hostel']} - {booking['room_type']}")
                if 'source' in booking and booking['source'] == 'manual':
                    st.markdown("_(Manual Booking)_")
                if booking['conversation_link'] and booking['conversation_link'] != "Not found":
                    st.markdown(f"[Conversation]({booking['conversation_link']})")
        else:
            st.info("No arrivals today")
        
        st.markdown("##### 🏁 Departures")
        if today_departures:
            for booking in today_departures:
                st.write(f"**{booking['full_name']}** - {booking['hostel']} - {booking['room_type']}")
                if 'source' in booking and booking['source'] == 'manual':
                    st.markdown("_(Manual Booking)_")
                if booking['conversation_link'] and booking['conversation_link'] != "Not found":
                    st.markdown(f"[Conversation]({booking['conversation_link']})")
        else:
            st.info("No departures today")
    
    with col2:
        st.markdown("#### Tomorrow")
        
        st.markdown("##### 🚀 Arrivals")
        if tomorrow_arrivals:
            for booking in tomorrow_arrivals:
                st.write(f"**{booking['full_name']}** - {booking['hostel']} - {booking['room_type']}")
                if 'source' in booking and booking['source'] == 'manual':
                    st.markdown("_(Manual Booking)_")
                if booking['conversation_link'] and booking['conversation_link'] != "Not found":
                    st.markdown(f"[Conversation]({booking['conversation_link']})")
        else:
            st.info("No arrivals tomorrow")
        
        st.markdown("##### 🏁 Departures")
        if tomorrow_departures:
            for booking in tomorrow_departures:
                st.write(f"**{booking['full_name']}** - {booking['hostel']} - {booking['room_type']}")
                if 'source' in booking and booking['source'] == 'manual':
                    st.markdown("_(Manual Booking)_")
                if booking['conversation_link'] and booking['conversation_link'] != "Not found":
                    st.markdown(f"[Conversation]({booking['conversation_link']})")
        else:
            st.info("No departures tomorrow")

def display_specific_day_movements(bookings: List[Dict]):
    """Tool to know specific day arrivals and departures"""
    st.subheader("🗓️ Specific Day Movements")
    
    selected_date = st.date_input("Select a date")
    
    def parse_date(date_str):
        try:
            return datetime.strptime(date_str, "%Y-%b-%d").date()
        except (ValueError, TypeError):
            return None
    
    arrivals = []
    departures = []
    
    for booking in bookings:
        arrival_date = parse_date(booking['arrival_date'])
        departure_date = parse_date(booking['departure_date'])
        
        if arrival_date == selected_date:
            arrivals.append(booking)
        if departure_date == selected_date:
            departures.append(booking)
            
    st.markdown(f"#### Movements on {selected_date.strftime('%A, %B %d, %Y')}")
    
    st.markdown("##### 🚀 Arrivals")
    if arrivals:
        for booking in arrivals:
            st.write(f"**{booking['full_name']}** - {booking['hostel']} - {booking['room_type']}")
            if 'source' in booking and booking['source'] == 'manual':
                st.markdown("_(Manual Booking)_")
            if booking['conversation_link'] and booking['conversation_link'] != "Not found":
                st.markdown(f"[Conversation]({booking['conversation_link']})")
    else:
        st.info("No arrivals on this day")
    
    st.markdown("##### 🏁 Departures")
    if departures:
        for booking in departures:
            st.write(f"**{booking['full_name']}** - {booking['hostel']} - {booking['room_type']}")
            if 'source' in booking and booking['source'] == 'manual':
                st.markdown("_(Manual Booking)_")
            if booking['conversation_link'] and booking['conversation_link'] != "Not found":
                st.markdown(f"[Conversation]({booking['conversation_link']})")
    else:
        st.info("No departures on this day")

def add_manual_booking_form():
    """Form to add a manual booking and save it to the JSON file"""
    st.subheader("✍️ Add Manual Booking")

    # The fix: create a unique key using the session state's run counter.
    # This ensures a new, unique key is generated on each rerun.
    form_key = f"manual_booking_form_{st.session_state.get('form_counter', 0)}"

    with st.form(form_key):
        full_name = st.text_input("Full Name *", help="Full name of the guest.")
        package_name = st.text_input("Package Name", help="e.g., 7 Day Yoga & Surf Holiday in Taghazout")
        
        col1, col2 = st.columns(2)
        with col1:
            arrival_date = st.date_input("Arrival Date *")
        with col2:
            departure_date = st.date_input("Departure Date *")
            
        hostel = st.selectbox("Hostel *", ["Taghazout", "Tamraght"])
        room_type = st.text_input("Room Type *", help="e.g., Private Room, Shared Dorm, etc.")
        number_of_guests = st.number_input("Number of Guests *", min_value=1, value=1)
        price = st.text_input("Price", value="N/A")
        conversation_link = st.text_input("Conversation Link", help="Optional link for reference.")
        
        submitted = st.form_submit_button("Add Booking")
        
        if submitted:
            if not all([full_name, arrival_date, departure_date, room_type]):
                st.error("Please fill in all required fields marked with *")
            else:
                current_bookings = load_bookings_from_json()
                
                nights = (departure_date - arrival_date).days
                
                today = datetime.now().date()
                if arrival_date <= today and departure_date >= today:
                    booking_type = "Current"
                else:
                    booking_type = "Upcoming"
                
                booking_data = {
                    "full_name": full_name,
                    "package_name": package_name if package_name else f"{nights}-day surf trip",
                    "hostel": hostel,
                    "price": price,
                    "arrival_date": arrival_date.strftime("%Y-%b-%d"),
                    "departure_date": departure_date.strftime("%Y-%b-%d"),
                    "number_of_nights": nights,
                    "number_of_guests": str(number_of_guests),
                    "room_type": room_type,
                    "conversation_link": conversation_link if conversation_link else "Not found",
                    "source": "manual",
                    "booking_type": booking_type
                }
                
                current_bookings.append(booking_data)
                save_bookings_to_json(current_bookings)
                
                # Increment the counter to ensure the next form has a new key
                st.session_state['form_counter'] = st.session_state.get('form_counter', 0) + 1

                st.session_state.bookings = current_bookings
                st.rerun()

def display_occupancy_by_hostel(bookings: List[Dict]):
    """Tool to know how many people are in each hostel for a specific date range."""
    st.subheader("👥 Occupancy & Departures by Hostel")
    
    col1, col2 = st.columns(2)
    
    with col1:
        selected_hostel = st.selectbox("Select Hostel", ["All", "Tamraght", "Taghazout"])
    with col2:
        selected_start_date = st.date_input("Start Date")
        selected_end_date = st.date_input("End Date")
    
    if selected_start_date > selected_end_date:
        st.error("Error: The end date must be after the start date.")
        return
        
    st.markdown("---")
    
    # Filter bookings based on selected hostel and date range
    filtered_bookings = []
    
    def parse_date(date_str):
        try:
            return datetime.strptime(date_str, "%Y-%b-%d").date()
        except (ValueError, TypeError):
            return None
    
    for booking in bookings:
        hostel = booking.get('hostel')
        arrival_date = parse_date(booking.get('arrival_date'))
        departure_date = parse_date(booking.get('departure_date'))
        number_of_guests = booking.get('number_of_guests')
        
        # Skip if essential data is missing
        if not all([hostel, arrival_date, departure_date, number_of_guests]) or number_of_guests in ["Not found", "Not available"]:
            continue
            
        try:
            num_guests = int(number_of_guests)
        except (ValueError, TypeError):
            continue
            
        # Check for date overlap and hostel match
        if (arrival_date <= selected_end_date and departure_date >= selected_start_date):
            if selected_hostel == "All" or hostel == selected_hostel:
                filtered_bookings.append(booking)
    
    if not filtered_bookings:
        st.info("No guests found for the selected criteria.")
        return
        
    # Group by hostel
    hostel_occupancy = defaultdict(lambda: {"guests": 0, "departures": defaultdict(list)})
    
    for booking in filtered_bookings:
        hostel = booking['hostel']
        num_guests = int(booking['number_of_guests'])
        departure_date_str = booking['departure_date']
        
        hostel_occupancy[hostel]['guests'] += num_guests
        hostel_occupancy[hostel]['departures'][departure_date_str].append(booking)
        
    for hostel, data in hostel_occupancy.items():
        st.markdown(f"### {hostel} Hostel")
        st.metric(f"Total Guests in period", data['guests'])
        
        st.markdown("#### Departures")
        if data['departures']:
            for date_str, departures_list in sorted(data['departures'].items()):
                st.write(f"**Departing on {date_str}:**")
                for booking in departures_list:
                    st.write(f"- {booking['full_name']} ({booking['number_of_guests']} guest(s))")
        else:
            st.info("No departures for this hostel in the selected period.")

def main():
    st.set_page_config(
        page_title="Tripaneer Booking Manager",
        page_icon="🏨",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🏨 Tripaneer Booking Manager")
    st.markdown("---")
    
    if 'scraper' not in st.session_state:
        st.session_state.scraper = TripaneerScraper()
    if 'bookings' not in st.session_state:
        st.session_state.bookings = []
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    # Sidebar for login and file actions
    with st.sidebar:
        st.header("🔐 Login")
        
        username = st.text_input("Tripaneer Email", value="surfgazmmorocco@gmail.com")
        password = st.text_input("Tripaneer Password", type="password", value="Haidar2024")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Login", use_container_width=True):
                with st.spinner("Logging in..."):
                    if st.session_state.scraper.login(username, password):
                        st.session_state.logged_in = True
                        st.success("Login successful!")
                    else:
                        st.error("Login failed!")
        
        with col2:
            if st.button("Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.bookings = []
                st.session_state.scraper.logged_in = False
                st.rerun()
                
        st.markdown("---")
        
        st.header("💾 Booking Data Actions")
        
        if st.button("⬇️ Load from File", use_container_width=True):
            st.session_state.bookings = load_bookings_from_json()
        
        if st.session_state.logged_in:
            if st.button("🔄 Refresh & Save to File", use_container_width=True):
                with st.spinner("Fetching latest bookings from Tripaneer..."):
                    tripaneer_bookings = st.session_state.scraper.extract_booking_data()
                    
                    # Merge with existing manual bookings
                    existing_data = load_bookings_from_json()
                    manual_bookings = [b for b in existing_data if b.get('source') == 'manual']
                    
                    all_bookings = tripaneer_bookings + manual_bookings
                    save_bookings_to_json(all_bookings)
                    st.session_state.bookings = all_bookings
        
        if st.session_state.bookings:
            if st.button("💾 Export to JSON", use_container_width=True):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"bookings_{timestamp}.json"
                json_data = json.dumps(st.session_state.bookings, indent=2, ensure_ascii=False)
                st.download_button(
                    label="Download JSON",
                    data=json_data,
                    file_name=filename,
                    mime="application/json",
                    use_container_width=True
                )
        
        st.markdown("---")
        st.info("💡 Use 'Load from File' for a quick view or 'Refresh & Save' to get the latest bookings.")
    
    # Main content area
    if st.session_state.bookings:
        display_booking_stats(st.session_state.bookings)
        st.markdown("---")
        
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "🏨 Current Guests", 
            "📅 Today/Tomorrow", 
            "🗓️ Specific Day",
            "📋 Table View", 
            "✍️ Add Manual Booking",
            "👥 Occupancy Report"
        ])
        
        with tab1:
            display_current_guests_by_hostel(st.session_state.bookings)
        
        with tab2:
            display_todays_movements(st.session_state.bookings)
        
        with tab3:
            display_specific_day_movements(st.session_state.bookings)
        
        with tab4:
            display_bookings_table(st.session_state.bookings)
        
        with tab5:
            add_manual_booking_form()
            
        with tab6:
            display_occupancy_by_hostel(st.session_state.bookings)
            
    else:
        st.warning("👆 Please load bookings from the sidebar to get started.")
        st.info("""
        ### How to use:
        1.  Enter your Tripaneer credentials in the sidebar and click **Login**.
        2.  Click **Refresh & Save to File** to fetch and store new bookings from Tripaneer.
        3.  Click **Load from File** for a quick load of existing data.
        4.  Use the **Add Manual Booking** tab to add your own bookings, which will be saved to the file.
        """)

if __name__ == "__main__":
    main()
