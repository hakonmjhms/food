import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from pdfminer.high_level import extract_text

# Function to convert short month format to full month format
def convert_date_format(date_string):
    month_map = {
        "jan": "janúar", "feb": "febrúar", "mar": "mars", "apr": "apríl",
        "maí": "maí", "jún": "júní", "júl": "júlí", "ágú": "ágúst",
        "sep": "september", "okt": "október", "nóv": "nóvember", "des": "desember"
    }
    day, short_month = date_string.split('.')
    full_month = month_map.get(short_month.strip(), short_month)
    return f"{day.strip()}. {full_month}"

# Function to calculate the menu week number based on the current date
def calculate_menu_week():
    base_date = datetime(2024, 10, 14)
    current_week_number = 423 + (datetime.today() - base_date).days // 7
    return current_week_number

# Step 1: Scrape the webpage for the PDF links
webpage_url = "https://www.mulakaffi.is/is/veitingastadurinn/matarbakkar"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36'}
response = requests.get(webpage_url, headers=headers)

if response.status_code != 200:
    print(f"Failed to retrieve the page. Status code: {response.status_code}")
    exit()

# Parse the HTML content
soup = BeautifulSoup(response.content, 'html.parser')

# Step 3: Define the current week's date range
today = datetime.today()
start_of_week = today - timedelta(days=today.weekday())
end_of_week = start_of_week + timedelta(days=6)
icelandic_month = start_of_week.strftime('%B').replace('January', 'janúar').replace('February', 'febrúar').replace('March', 'mars').replace('April', 'apríl').replace('May', 'maí').replace('June', 'júní').replace('July', 'júlí').replace('August', 'ágúst').replace('September', 'september').replace('October', 'október').replace('November', 'nóvember').replace('December', 'desember')

text = f"Matseðill vikunnar {start_of_week.day} - {end_of_week.day} {icelandic_month}"

# Step 4: Look for the PDF link
pdf_url = None
for a_tag in soup.find_all('a'):
    link_text = a_tag.get_text(strip=True).replace(u'\xa0', ' ')
    if re.search(text, link_text, re.IGNORECASE):
        pdf_url = f'https://www.mulakaffi.is/{a_tag["href"]}'
        break

# Step 5: If no PDF link is found, calculate based on the week number
if not pdf_url:
    current_week_number = calculate_menu_week()
    pdf_url = f'https://www.mulakaffi.is/static/files/matsedlar/matsedill-vikunnar/matsedillvikunnar/vikumatsedill-{current_week_number}.pdf'

# Step 6: Download the PDF
pdf_response = requests.get(pdf_url, headers=headers)
if pdf_response.status_code != 200:
    print(f"Failed to download PDF from {pdf_url}")
    exit()

# Save the PDF
pdf_file = 'menu_week.pdf'
with open(pdf_file, 'wb') as f:
    f.write(pdf_response.content)

# Step 7: Extract text from the PDF
try:
    pdf_text = extract_text(pdf_file)
except Exception as e:
    print(f"Error extracting text from PDF: {e}")
    exit()

# Step 8: Identify the current day and extract its menu
weekdays = ["Mánudagur", "Þriðjudagur", "Miðvikudagur", "Fimmtudagur", "Föstudagur", "Laugardagur", "Sunnudagur"]
current_day = weekdays[today.weekday()]

# Find all occurrences of weekdays in the text
matches = re.split(r'(' + '|'.join(weekdays) + r')', pdf_text)

# Construct a dictionary for the menus
menu_dict = {matches[i].strip(): matches[i + 1].strip() for i in range(1, len(matches), 2) if i + 1 < len(matches)}

# Step 9: Output the menu found for today
if current_day in menu_dict:
    menu_text = menu_dict[current_day]
    
    # Extract the date part and convert it
    date_part = menu_text.split(' ', 1)[0]
    converted_date = convert_date_format(date_part)

    # Split the rest of the menu text into individual lines/items
    menu_items = [item.strip() for item in menu_text[len(date_part):].strip().split('\n') if item.strip()]

    # Initialize menu components
    vegan = soup = main_course = ""

    # Assign items based on the known order
    if len(menu_items) > 0: vegan = "Vegan: " + menu_items[0]
    if len(menu_items) > 1: soup = "Súpa: " + menu_items[1]
    if len(menu_items) > 2: main_course = menu_items[2]

    # Construct the output message
    output_message = f"Matur í mötuneyti {current_day.lower()[:-2] + 'inn'} {converted_date}:\n\n"
    
    if main_course: output_message += " " + main_course + "\n"
    if soup: output_message += " " + soup + "\n"
    if vegan: output_message += " " + vegan + "\n"

    print(output_message.strip())  # Print the final formatted menu
else:
    print(f"No menu found for today: {current_day}.")
