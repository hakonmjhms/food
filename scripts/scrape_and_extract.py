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

# Normalize text by handling different types of spaces and removing extra whitespace
def normalize_text(text):
    return re.sub(r'\s+', ' ', text.replace('\xa0', ' ').replace('&nbsp;', ' ')).strip()

# Create different possible search patterns for the menu link
def create_search_patterns(start_date, end_date, month_name):
    patterns = []
    patterns.append(f"Matseðill vikunnar {start_date.day} - {end_date.day} {month_name}")
    patterns.append(f"Matseðill vikunnar {start_date.day} {month_name} - {end_date.day} {month_name}")
    
    if start_date.month != end_date.month:
        start_month = start_date.strftime('%B').replace('January', 'janúar').replace('February', 'febrúar').replace('March', 'mars').replace('April', 'apríl').replace('May', 'maí').replace('June', 'júní').replace('July', 'júlí').replace('August', 'ágúst').replace('September', 'september').replace('October', 'október').replace('November', 'nóvember').replace('December', 'desember')
        end_month = end_date.strftime('%B').replace('January', 'janúar').replace('February', 'febrúar').replace('March', 'mars').replace('April', 'apríl').replace('May', 'maí').replace('June', 'júní').replace('July', 'júlí').replace('August', 'ágúst').replace('September', 'september').replace('October', 'október').replace('November', 'nóvember').replace('December', 'desember')
        patterns.append(f"Matseðill vikunnar {start_date.day} {start_month} - {end_date.day} {end_month}")
    
    return patterns

# Try to find the PDF URL by searching the webpage for matching menu links
def find_pdf_url_from_webpage(response, start_of_week, end_of_week, icelandic_month):
    soup = BeautifulSoup(response.content, 'html.parser')
    search_patterns = create_search_patterns(start_of_week, end_of_week, icelandic_month)
    
    # Find all menu links
    menu_links = []
    for a in soup.find_all('a'):
        if a.get('href') and 'matsedill' in a.get('href', '').lower():
            link_text = normalize_text(a.get_text(strip=True))
            menu_links.append((a.get('href'), link_text))
    
    # Try to match against search patterns
    for pattern in search_patterns:
        normalized_pattern = normalize_text(pattern)
        for href, link_text in menu_links:
            if normalized_pattern.lower() == link_text.lower():
                return f'https://www.mulakaffi.is{href}' if not href.startswith('http') else href
            
            # Try partial match
            pattern_no_spaces = re.sub(r'\s+', '', normalized_pattern.lower())
            link_no_spaces = re.sub(r'\s+', '', link_text.lower())
            if pattern_no_spaces in link_no_spaces or link_no_spaces in pattern_no_spaces:
                return f'https://www.mulakaffi.is{href}' if not href.startswith('http') else href
    
    return None

# Step 1: Scrape for PDF link
webpage_url = "https://www.mulakaffi.is/is/veitingastadurinn/matarbakkar"
headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get(webpage_url, headers=headers)
if response.status_code != 200:
    exit()

# Step 2: Generate list of possible PDF URLs
today = datetime.today() #-timedelta(days=7) #Used for error checking by looking at the last week
start_of_week = today - timedelta(days=today.weekday())
end_of_week = start_of_week + timedelta(days=6)
icelandic_month = start_of_week.strftime('%B').replace('January', 'janúar').replace('February', 'febrúar').replace('March', 'mars').replace('April', 'apríl').replace('May', 'maí').replace('June', 'júní').replace('July', 'júlí').replace('August', 'ágúst').replace('September', 'september').replace('October', 'október').replace('November', 'nóvember').replace('December', 'desember')

possible_urls = []

# First priority: URL found from webpage search
webpage_url = find_pdf_url_from_webpage(response, start_of_week, end_of_week, icelandic_month)
if webpage_url:
    possible_urls.append(webpage_url)

# Fallback URLs based on calculated week number
week_num = calculate_menu_week()
fallback_urls = [
    f'https://www.mulakaffi.is/static/files/matsedlar/matsedill-vikunnar/matsedillvikunnar/vikumatsedill-{week_num}.pdf',
    f'https://www.mulakaffi.is/static/files/matsedlar/matsedill-vikunnar/innihaldslysingar/vikumatsedill-{week_num}.pdf',
    f'https://www.mulakaffi.is/static/files/matsedlar/matsedill-vikunnar/vikumatsedill-{week_num}.pdf'
]
possible_urls.extend(fallback_urls)

# Step 3: Try downloading PDF from each URL until one works
pdf_content = None
for url in possible_urls:
    try:
        pdf_response = requests.get(url, headers=headers)
        if pdf_response.status_code == 200:
            pdf_content = pdf_response.content
            break
    except:
        continue

if not pdf_content:
    exit()

# Step 4: Save PDF file and extract text
pdf_file = 'menu_week.pdf'
with open(pdf_file, 'wb') as f:
    f.write(pdf_content)

try:
    pdf_text = extract_text(pdf_file)
except:
    exit()

# Step 5: Extract and output today's menu
weekdays = ["Mánudagur", "Þriðjudagur", "Miðvikudagur", "Fimmtudagur", "Föstudagur", "Laugardagur", "Sunnudagur"]
current_day = weekdays[today.weekday() % 7]
matches = re.split(r'(' + '|'.join(weekdays) + r')', pdf_text)

menu_dict = {matches[i].strip(): matches[i + 1].strip() for i in range(1, len(matches), 2) if i + 1 < len(matches)}
menu_text = menu_dict.get(current_day, None)

if menu_text:
    date_part = menu_text.split(' ', 1)[0]
    converted_date = convert_date_format(date_part)
    menu_items = [item.strip() for item in menu_text[len(date_part):].strip().split('\n') if item.strip()]

    if len(menu_items) == 4:
        holiday, vegan, soup, main_course = menu_items
        output_message = f"Matur í mötuneyti {current_day.lower()[:-2] + 'inn'} {converted_date}:\n\n"
        if holiday: output_message += " " + holiday + "!\n"
        if main_course: output_message += " " + main_course + "\n"
        if soup: output_message += " Súpa: " + soup + "\n"
        if vegan: output_message += " Vegan: " + vegan + "\n"
    else:
        vegan, soup, main_course = menu_items
        output_message = f"Matur í mötuneyti {current_day.lower()[:-2] + 'inn'} {converted_date}:\n\n"
        if main_course: output_message += " " + main_course + "\n"
        if soup: output_message += " Súpa: " + soup + "\n"
        if vegan: output_message += " Vegan: " + vegan + "\n"
    
    print(output_message.strip())
else:
    print(f"No menu found for today: {current_day}.")
