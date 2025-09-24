()
        
        for index, item in enumerate(booking_items):
            try:
                # Update progress
                progress = (index + 1) / len(booking_items)
                progress_bar.progress(progress)
                status_text.text(f"Processing {booking_type} booking {index + 1} of {len(booking_items)}...")
                
                # Extract customer name
                customer_name_elem = item.find('div', class_='customer-name')
                full_name = customer_name_elem.find('strong').get_text(strip=True) if customer_name_elem else "Not found"
                
                # Extract package name
                listing_title_elem = item.find('div', class_='listing-title')
                package_name = listing_title_elem.find('p').get_text(strip=True) if listing_title_elem else "Not found"
                
                # Extract price and dates
                inquiry_meta = item.find('div', class_='inquiry-meta')
                if inquiry_meta:
                    strong_elements = inquiry_meta.find_all('strong')
                    price = strong_elements[0].get_text(strip=True) if len(strong_elements) > 0 else "Not found"
                    arrival_date = strong_elements[1].get_text(strip=True) if len(strong_elements) > 1 else "Not found"
                    departure_date = strong_elements[2].get_text(strip=True) if len(strong_elements) > 2 else "Not found"
                else:
                    price = arrival_date = departure_date = "Not found"
                
                # Calculate number of nights
                nights = self.calculate_nights(arrival_date, departure_date) if arrival_date != "Not found" and departure_date != "Not found" else 0
                
                # Determine hostel
                hostel = self.determine_hostel(package_name)
                
                # Extract conversation link
                conversation_link = None
                link_elem = item.find('a', class_='btn btn-info')
                if link_elem and link_elem.get('href'):
                    conversation_link = f"{self.base_url}{link_elem['href']}"
                else:
                    # Try mobile link as fallback
                    mobile_link = item.find('a', class_='mobile-link')
                    if mobile_link and mobile_link.get('href'):
                        conversation_link = f"{self.base_url}{mobile_link['href']}"
                
                # Extract guest count and room type
                guests = "Not available"
                room_type = "Not available"
                
                if conversation_link:
                    guests, room_type = self.extract_guest_and_room_info(conversation_link)
                
                # Create booking dictionary
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
            
            # Find all booking lists with class 'recent-inquiries--new'
            booking_lists = soup.find_all('ul', class_='recent-inquiries--new')
            
            all_bookings = []
            
            # Process first list (Currently with you - current bookings)
            if len(booking_lists) > 0:
                with st.spinner("Extracting current bookings..."):
                    current_bookings = self.extract_bookings_from_list(booking_lists[0], "current")
                    all_bookings.extend(current_bookings)
            else:
                st.info("No current bookings list found")
            
            # Process second list (Upcoming bookings)
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

def display_booking_stats(bookings: List[Dict]):
    """Display booking statistics"""
    if not bookings:
        return
    
    st.subheader("📊 Booking Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_bookings = len(bookings)
    current_bookings = sum(1 for b in bookings if b['booking_type'] == 'Current')
    upcoming_bookings = sum(1 for b in bookings if b['booking_type'] == 'Upcoming')
    
    # Calculate total guests (convert to int where possible)
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
    
    # Convert to DataFrame for better display
    df_data = []
    for booking in bookings:
        df_data.append({
            'Type': booking['booking_type'],
            'Name': booking['full_name'],
            'Hostel': booking['hostel'],
            'Arrival': booking['arrival_date'],
            'Departure': booking['departure_date'],
            'Nights': booking['number_of_nights'],
            'Guests': booking['number_of_guests'],
            'Room Type': booking['room_type'],
            'Price': booking['price']
        })
    
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True)

def display_detailed_view(bookings: List[Dict]):
    """Display detailed view of bookings"""
    if not bookings:
        return
    
    st.subheader("📋 Detailed Booking Information")
    
    for i, booking in enumerate(bookings, 1):
        with st.expander(f"{i}. {booking['full_name']} - {booking['booking_type']}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Package:** {booking['package_name']}")
                st.write(f"**Hostel:** {booking['hostel']}")
                st.write(f"**Price:** {booking['price']}")
                st.write(f"**Nights:** {booking['number_of_nights']}")
            
            with col2:
                st.write(f"**Arrival:** {booking['arrival_date']}")
                st.write(f"**Departure:** {booking['departure_date']}")
                st.write(f"**Guests:** {booking['number_of_guests']}")
                st.write(f"**Room Type:** {booking['room_type']}")
            
            if booking['conversation_link']:
                st.write(f"**Conversation Link:** [View Details]({booking['conversation_link']})")

def main():
    st.set_page_config(
        page_title="Tripaneer Booking Manager",
        page_icon="🏨",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🏨 Tripaneer Booking Manager")
    st.markdown("---")
    
    # Initialize scraper in session state
    if 'scraper' not in st.session_state:
        st.session_state.scraper = TripaneerScraper()
    if 'bookings' not in st.session_state:
        st.session_state.bookings = []
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    # Sidebar for login
    with st.sidebar:
        st.header("🔐 Login")
        
        username = st.text_input("Email", value="surfgazmmorocco@gmail.com")
        password = st.text_input("Password", type="password", value="Haidar2024")
        
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
        st.header("📊 Actions")
        
        if st.session_state.logged_in:
            if st.button("🔄 Refresh Bookings", use_container_width=True):
                with st.spinner("Fetching latest bookings..."):
                    st.session_state.bookings = st.session_state.scraper.extract_booking_data()
            
            if st.button("💾 Export to JSON", use_container_width=True) and st.session_state.bookings:
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
        st.info("💡 Use the refresh button to get the latest bookings after logging in.")
    
    # Main content area
    if st.session_state.logged_in:
        if st.session_state.bookings:
            display_booking_stats(st.session_state.bookings)
            st.markdown("---")
            
            tab1, tab2 = st.tabs(["📋 Table View", "🔍 Detailed View"])
            
            with tab1:
                display_bookings_table(st.session_state.bookings)
            
            with tab2:
                display_detailed_view(st.session_state.bookings)
        else:
            st.info("👆 Click 'Refresh Bookings' in the sidebar to load your bookings.")
    else:
        st.warning("🔐 Please login using the sidebar to access your bookings.")
        
        # Display sample data or instructions
        st.info("""
        ### How to use:
        1. Enter your Tripaneer credentials in the sidebar
        2. Click 'Login' to authenticate
        3. Click 'Refresh Bookings' to load your current and upcoming bookings
        4. View bookings in table or detailed format
        5. Export data as JSON if needed
        """)

if __name__ == "__main__":
    main()