from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
import json
from datetime import datetime

# ChromeDriver setup
driver_path = "C:/Users/hamza ghazal/Downloads/chromedriver/chromedriver/chromedriver.exe"
service = Service(driver_path)
driver = webdriver.Chrome(service=service)

def calculate_nights(arrival_date, departure_date):
    """Calculate number of nights based on arrival and departure dates"""
    try:
        arrival = datetime.strptime(arrival_date, "%Y-%b-%d")
        departure = datetime.strptime(departure_date, "%Y-%b-%d")
        nights = (departure - arrival).days
        return max(nights, 1)  # Ensure at least 1 night
    except ValueError:
        return 0

def determine_hostel(package_name):
    """Determine hostel based on package name"""
    package_name_lower = package_name.lower()
    if "7 day" in package_name_lower and "taghazout" in package_name_lower:
        return "Taghazout"
    else:
        return "Tamraght"

def extract_guest_and_room_info(conversation_link):
    """Extract guest count and room type from conversation page"""
    guests = "Not found"
    room_type = "Not found"
    
    try:
        # Open the conversation link in a new tab
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.get(conversation_link)
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "col-xs-6"))
        )
        
        # Look for guest information
        try:
            # Find all col-xs-6 elements and check their content
            col_elements = driver.find_elements(By.CLASS_NAME, "col-xs-6")
            for element in col_elements:
                text = element.text
                if "Guests" in text:
                    # Extract the number of guests
                    guests_text = element.find_element(By.TAG_NAME, "dd").text
                    guests = guests_text.replace("persons", "").replace("person", "").strip()
                    break
        except NoSuchElementException:
            pass
        
        # Look for room type information
        try:
            # Try different selectors for room type
            room_selectors = [
                "//div[contains(@class, 'col-xs-6')]//dt[contains(text(), 'Room')]/following-sibling::dd",
                "//div[contains(@class, 'col-lg-8')]//dt[contains(text(), 'Room')]/following-sibling::dd"
            ]
            
            for selector in room_selectors:
                try:
                    room_elements = driver.find_elements(By.XPATH, selector)
                    if room_elements:
                        room_text = room_elements[0].text
                        # Clean up the room type text (remove extra details if needed)
                        room_type = room_text.split('\n')[0].strip() if '\n' in room_text else room_text.strip()
                        break
                except NoSuchElementException:
                    continue
                    
        except NoSuchElementException:
            pass
        
        # Close the tab and switch back to main window
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        
    except Exception as e:
        print(f"Error extracting guest/room info: {e}")
        # Ensure we switch back to main window even if there's an error
        try:
            if len(driver.window_handles) > 1:
                driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except:
            pass
    
    return guests, room_type

def extract_booking_data():
    """Extract booking data from the current with you section"""
    bookings = []
    
    try:
        # Wait for the bookings to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "recent-inquiries--new"))
        )
        
        # Find the ul element with class "recent-inquiries--new"
        booking_list = driver.find_element(By.CLASS_NAME, "recent-inquiries--new")
        
        # Find all li items within the ul
        booking_items = booking_list.find_elements(By.TAG_NAME, "li")
        
        print(f"Found {len(booking_items)} bookings in 'Currently with you' section")
        
        for index, item in enumerate(booking_items):
            try:
                # Extract customer name
                customer_name_elem = item.find_element(By.CLASS_NAME, "customer-name")
                full_name = customer_name_elem.find_element(By.TAG_NAME, "strong").text.strip()
                
                # Extract package name
                listing_title_elem = item.find_element(By.CLASS_NAME, "listing-title")
                package_name = listing_title_elem.find_element(By.TAG_NAME, "p").text.strip()
                
                # Extract price
                inquiry_meta = item.find_element(By.CLASS_NAME, "inquiry-meta")
                price_elem = inquiry_meta.find_elements(By.TAG_NAME, "strong")[0]
                price = price_elem.text.strip()
                
                # Extract arrival and departure dates
                meta_text = inquiry_meta.text
                arrival_date = None
                departure_date = None
                
                # Alternative method: find all strong elements in inquiry-meta
                strong_elements = inquiry_meta.find_elements(By.TAG_NAME, "strong")
                if len(strong_elements) >= 3:
                    price = strong_elements[0].text.strip()
                    arrival_date = strong_elements[1].text.strip()
                    departure_date = strong_elements[2].text.strip()
                
                # Calculate number of nights
                nights = calculate_nights(arrival_date, departure_date) if arrival_date and departure_date else 0
                
                # Determine hostel
                hostel = determine_hostel(package_name)
                
                # Extract conversation link
                conversation_link = None
                try:
                    link_elem = item.find_element(By.CSS_SELECTOR, "a.btn.btn-info")
                    conversation_link = link_elem.get_attribute("href")
                except NoSuchElementException:
                    try:
                        # Try mobile link as fallback
                        link_elem = item.find_element(By.CLASS_NAME, "mobile-link")
                        conversation_link = link_elem.get_attribute("href")
                    except NoSuchElementException:
                        conversation_link = None
                
                # Extract guest count and room type if conversation link exists
                guests = "Not available"
                room_type = "Not available"
                
                if conversation_link and conversation_link != "Link not found":
                    print(f"Extracting guest/room info for {full_name}...")
                    guests, room_type = extract_guest_and_room_info(conversation_link)
                
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
                    "conversation_link": conversation_link
                }
                
                bookings.append(booking_data)
                print(f"Extracted booking {index + 1}: {full_name} - {guests} guests - {room_type}")
                
            except Exception as e:
                print(f"Error extracting booking {index + 1}: {e}")
                continue
                
    except Exception as e:
        print(f"Error finding booking list: {e}")
    
    return bookings

def main():
    try:
        print("Opening browser...")
        # Open the login page
        driver.get("https://office.tripaneer.com/4/login/")
        print("Page loaded successfully")
        time.sleep(3)
        
        # Login process
        print("Looking for email field...")
        email_field = driver.find_element(By.XPATH, "/html/body/div[2]/form/div[2]/input")
        print("Email field found!")
        
        print("Looking for password field...")
        password_field = driver.find_element(By.XPATH, "/html/body/div[2]/form/div[3]/input")
        print("Password field found!")
        
        print("Looking for login button...")
        login_button = driver.find_element(By.XPATH, "/html/body/div[2]/form/div[4]/button")
        print("Login button found!")
        
        # Enter credentials
        print("Entering credentials...")
        email_field.send_keys("surfgazmmorocco@gmail.com")
        password_field.send_keys("Haidar2024")
        
        # Click login
        print("Clicking login button...")
        login_button.click()
        
        print("Waiting for login to complete...")
        time.sleep(5)
        
        # Navigate to bookings overview page
        print("Redirecting to bookings overview page...")
        driver.get("https://office.tripaneer.com/4/organizers/65639/bookings-overview/")
        
        # Wait for page to load
        print("Waiting for bookings page to load...")
        time.sleep(5)
        
        # Extract booking data
        print("Extracting booking data...")
        bookings_data = extract_booking_data()
        
        # Save to JSON file
        if bookings_data:
            output_file = "current_bookings.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(bookings_data, f, indent=2, ensure_ascii=False)
            
            print(f"\nSuccessfully extracted {len(bookings_data)} bookings!")
            print(f"Data saved to {output_file}")
            
            # Print summary
            print("\n=== EXTRACTION SUMMARY ===")
            for i, booking in enumerate(bookings_data, 1):
                print(f"{i}. {booking['full_name']} - {booking['hostel']} - {booking['arrival_date']} to {booking['departure_date']}")
                print(f"   Guests: {booking['number_of_guests']} - Room: {booking['room_type']}")
        else:
            print("No bookings found to extract")
        
    except NoSuchElementException as e:
        print(f"Element not found: {e}")
        print("Current page URL:", driver.current_url)
        print("Page title:", driver.title)
        driver.save_screenshot("debug_screenshot.png")
        print("Screenshot saved as debug_screenshot.png")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Current page URL:", driver.current_url)
        
    finally:
        print("Script completed. Browser will close in 10 seconds...")
        time.sleep(10)
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    main()