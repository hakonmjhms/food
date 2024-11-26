import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from pdfminer.high_level import extract_text

# Convert short month format to Icelandic full month format
def convert_date_format(date_string):
    month_map = {
        "jan": "janúar", "feb": "febrúar", "mar": "mars", "apr": "apríl",
        "maí": "maí", "jún": "júní", "júl": "júlí", "ágú": "ágúst",
        "sep": "september", "okt": "október", "nóv": "nóvember", "des": "desember"
    }
    day, short_month = date_string.split('.')
    return f"{day.strip()}. {month_map.get(short_month.strip(), short_month)}"

# Calculate the menu week number based on the current date
def calculate_menu_week():
    base_date = datetime(2024, 10, 14)
    return 423 + (datetime.today() - base_date).days // 7

# Step 1: Scrape for PDF link
webpage_url = "https://www.mulakaffi.is/is/veitingastadurinn/matarbakkar"
headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get(webpage_url, headers=headers)
if response.status_code != 200:
    print(f"Failed to retrieve page. Status code: {response.status_code}")
    exit()

# Step 2: Define the search text for the current week in Icelandic format
today = datetime.today() #-timedelta(days=7) #Used for error checking by looking at the last week
start_of_week = today - timedelta(days=today.weekday())
icelandic_month = start_of_week.strftime('%B').replace('January', 'janúar').replace('February', 'febrúar').replace('March', 'mars').replace('April', 'apríl').replace('May', 'maí').replace('June', 'júní').replace('July', 'júlí').replace('August', 'ágúst').replace('September', 'september').replace('October', 'október').replace('November', 'nóvember').replace('December', 'desember')
text = f"Matseðill vikunnar {start_of_week.day} - {(start_of_week + timedelta(days=6)).day} {icelandic_month}"

# Step 3: Find PDF link or construct URL based on week number
soup = BeautifulSoup(response.content, 'html.parser')
pdf_url = next(
    (f'https://www.mulakaffi.is/{a["href"]}' for a in soup.find_all('a')
     if re.search(text, re.sub(r'\s+', ' ', a.get_text(strip=True).replace('\xa0', ' ')), re.IGNORECASE)), 
    None
)
if not pdf_url:
    pdf_url = f'https://www.mulakaffi.is/static/files/matsedlar/matsedill-vikunnar/matsedillvikunnar/vikumatsedill-{calculate_menu_week()}.pdf'

# Step 4: Download and save the PDF
pdf_response = requests.get(pdf_url, headers=headers)
if pdf_response.status_code != 200:
    print(f"Failed to download PDF from {pdf_url}")
    exit()

pdf_file = 'menu_week.pdf'
with open(pdf_file, 'wb') as f:
    f.write(pdf_response.content)

# Step 5: Extract text from the PDF
try:
    pdf_text = extract_text(pdf_file)
except Exception as e:
    print(f"Error extracting text from PDF: {e}")
    exit()

# Step 6: Extract today's menu based on weekday
weekdays = ["Mánudagur", "Þriðjudagur", "Miðvikudagur", "Fimmtudagur", "Föstudagur", "Laugardagur", "Sunnudagur"]
current_day = weekdays[(today.weekday())%7]
matches = re.split(r'(' + '|'.join(weekdays) + r')', pdf_text)

# Construct menu dictionary and find today’s menu
menu_dict = {matches[i].strip(): matches[i + 1].strip() for i in range(1, len(matches), 2) if i + 1 < len(matches)}
menu_text = menu_dict.get(current_day, None)

# Step 7: Output today's menu if found
if menu_text:
    date_part = menu_text.split(' ', 1)[0]
    converted_date = convert_date_format(date_part)
    menu_items = [item.strip() for item in menu_text[len(date_part):].strip().split('\n') if item.strip()]

    if len(menu_items) == 4:
        holiday = menu_items[0]
        soup = menu_items[2]
        main_course = menu_items[3]
        vegan = menu_items[1]

        output_message = f"Matur í mötuneyti {current_day.lower()[:-2] + 'inn'} {converted_date}:\n\n"
        if holiday: output_message += " " + holiday + "\n"
        if main_course: output_message += " " + main_course + "\n"
        if soup: output_message += " Súpa: " + soup + "\n"
        if vegan: output_message += " Vegan: " + vegan + "\n"
    else:
        soup = menu_items[1]
        main_course = menu_items[2]
        vegan = menu_items[0]
        output_message = f"Matur í mötuneyti {current_day.lower()[:-2] + 'inn'} {converted_date}:\n\n"
        if main_course: output_message += " " + main_course + "\n"
        if soup: output_message += " Súpa: " + soup + "\n"
        if vegan: output_message += " Vegan: " + vegan + "\n"
    
    print(output_message.strip())
else:
    print(f"No menu found for today: {current_day}.")
