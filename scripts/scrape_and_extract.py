import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import PyPDF2
import os

# Function to convert short month format to full month format
def convert_date_format(date_string):
    # Dictionary mapping short month names to full month names
    month_map = {
        "jan": "janúar",
        "feb": "febrúar",
        "mar": "mars",
        "apr": "apríl",
        "maí": "maí",
        "jún": "júní",
        "júl": "júlí",
        "ágú": "ágúst",
        "sep": "september",
        "okt": "október",
        "nóv": "nóvember",
        "des": "desember"
    }

    # Split the date string into day and month
    day, short_month = date_string.split('.')
    
    # Get the full month name from the dictionary
    full_month = month_map.get(short_month.strip(), short_month)

    # Return the modified date string
    return f"{day.strip()}. {full_month}"

# Step 1: Scrape the webpage for the PDF links
webpage_url = "https://www.mulakaffi.is/is/veitingastadurinn/matarbakkar"
# Set headers to mimic a browser
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36'
}

# Make the request with the headers
response = requests.get(webpage_url, headers=headers)

# Check if the request was successful
if response.status_code == 200:
    pass
    #print("Request successful!")
else:
    print(f"Failed to retrieve the page. Status code: {response.status_code}")
    exit()

# Parse the HTML content
soup = BeautifulSoup(response.content, 'html.parser')

# Step 2: Define a dictionary for Icelandic month names
months_in_icelandic = {
    "January": "janúar",
    "February": "febrúar",
    "March": "mars",
    "April": "apríl",
    "May": "maí",
    "June": "júní",
    "July": "júlí",
    "August": "ágúst",
    "September": "september",
    "October": "október",
    "November": "nóvember",
    "December": "desember"
}

# Step 3: Define the current week's date range based on the current day
today = datetime.today()

# Find the Monday and Sunday of the current week
start_of_week = today - timedelta(days=today.weekday())  # Monday of the current week
end_of_week = start_of_week + timedelta(days=6)  # Sunday of the current week

# Get the Icelandic name for the current month
icelandic_month = months_in_icelandic[start_of_week.strftime('%B')]

# Example: 'Matseðill vikunnar 21 - 27 September'
text = f"Matseðill vikunnar {start_of_week.day} - {end_of_week.day} {icelandic_month}"

# Step 4: Loop through all <p> tags to find the right PDF link
for a_tag in soup.find_all('a'):  # Look for all <a> tags
    link_text = a_tag.get_text(strip=True).replace(u'\xa0', ' ')  # Handle &nbsp; (non-breaking spaces)
    
    # Check if the link text matches the pattern "Matseðill vikunnar X - Y"
    if re.search(text, link_text, re.IGNORECASE):
        pdf_url = a_tag['href']  # Get the href attribute (PDF link)
        break

# Step 5: Check if a PDF was found, if not, exit
try:
    if pdf_url:
        pdf_url = f'https://www.mulakaffi.is/{pdf_url}'
        pass
        #print(f'pdf url: {pdf_url}')
except:
    print(f"Enginn matseðill fannst þegar leitað var að \'{text}\'")
    exit(1)


# Step 6: Download the PDF from the extracted link
pdf_response = requests.get(pdf_url, headers=headers)  # Use headers to mimic browser

if pdf_response.status_code == 200:
    #pass
    #print("PDF downloaded successfully!")
    pdf_file = 'menu_week.pdf'
    
    # Step 6: Save the PDF to a file
    with open(pdf_file, 'wb') as f:
        f.write(pdf_response.content)
else:
    print(f"Failed to download PDF. Status code: {pdf_response.status_code}")
    exit()

with open(pdf_file, 'wb') as f:
    f.write(pdf_response.content)

# Step 6: Check if the PDF file was created and has content
if os.path.exists(pdf_file) and os.path.getsize(pdf_file) > 0:
    pass
    #print(f"PDF file saved: {pdf_file} (size: {os.path.getsize(pdf_file)} bytes)")
else:
    print("PDF file not created or is empty.")
    exit()

# Step 7: Extract text from the PDF
pdf_text = ""
try:
    with open(pdf_file, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        num_pages = len(reader.pages)
        
        for i in range(num_pages):
            page = reader.pages[i]
            text = page.extract_text()
            if text:  # Ensure that text extraction was successful
                pdf_text += text
    
    pass
    #print("PDF text extracted successfully.")

except Exception as e:
    print(f"Error reading PDF: {e}")

# Step 8: Identify the current day and extract its menu
weekdays = [
    "Mánudagur",   # Monday
    "Þriðjudagur",  # Tuesday
    "Miðvikudagur", # Wednesday
    "Fimmtudagur",  # Thursday
    "Föstudagur",   # Friday
    "Laugardagur",  # Saturday
    "Sunnudagur"    # Sunday
]

# Get the current day of the week in Icelandic
current_day_index = today.weekday()  # Monday is 0, Sunday is 6
current_day = weekdays[current_day_index]

# Prepare a regex pattern to find the weekdays
weekday_pattern = r'(' + '|'.join(weekdays) + r')'

# Find all occurrences of weekdays in the text
matches = re.split(weekday_pattern, pdf_text)

# Construct a dictionary to hold the menus for each weekday
menu_dict = {}
for i in range(1, len(matches), 2):
    day_name = matches[i].strip()  # Get the day name
    if i + 1 < len(matches):
        menu_text = matches[i + 1].strip()  # Get the text after the day name
        menu_dict[day_name] = menu_text

# Step 9: Output the menu found for today
if current_day in menu_dict:
    # Extract the menu text for today
    menu_text = menu_dict[current_day]

    # Extract the date part and convert it
    date_part = menu_text.split(' ', 1)[0]  # Get the first part (date)
    converted_date = convert_date_format(date_part)  # Convert the date format
    
    # Split the rest of the menu text into individual lines/items
    menu_items = [item.strip() for item in menu_text[len(date_part):].strip().split('\n') if item.strip()]

    # Check if we have enough menu items and assign them based on the known order
    vegan = "Vegan: " + menu_items[0] if len(menu_items) > 0 else ""
    soup = "Súpa: " + menu_items[1] if len(menu_items) > 1 else ""
    main_course = menu_items[2] if len(menu_items) > 2 else ""

    # Construct the output message
    output_message = f"Matseðill fyrir {current_day[:-2] + 'inn'} {converted_date}:\n\n"
    
    if main_course:
        output_message += " " + main_course + "\n"
    if soup:
        output_message += " " + soup + "\n"
    if vegan:
        output_message += " " + vegan + "\n"

    print(output_message.strip())  # Print the final formatted menu
else:
    print(f"No menu found for today: {current_day}.")
