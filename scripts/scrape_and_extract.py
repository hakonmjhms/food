import sys
import re
from io import BytesIO

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pdfminer.high_level import extract_text

WEEKDAYS = ["mánudagur", "þriðjudagur", "miðvikudagur", "fimmtudagur", "föstudagur", "laugardagur", "sunnudagur"]

BASE_URL = "https://www.mulakaffi.is"
PAGE_URL = f"{BASE_URL}/is/veitingastadurinn/matarbakkar"

headers = {'User-Agent': 'Mozilla/5.0'}

today = datetime.today()
current_day = WEEKDAYS[today.weekday()]

# 1. Find the link to this week's menu PDF on the Fyrirtækjaþjónusta page.
response = requests.get(PAGE_URL, headers=headers)
if response.status_code != 200:
    sys.exit(1)

soup = BeautifulSoup(response.content, 'html.parser')
pdf_link = next((a['href'] for a in soup.find_all('a', href=True) if a['href'].lower().endswith('.pdf')), None)
if not pdf_link:
    sys.exit(1)
if pdf_link.startswith('/'):
    pdf_link = BASE_URL + pdf_link

# 2. Download the PDF and extract its text.
pdf_response = requests.get(pdf_link, headers=headers)
if pdf_response.status_code != 200:
    sys.exit(1)

text = extract_text(BytesIO(pdf_response.content))

# The PDF has a weekly menu section followed by an "Innihaldslýsing" (ingredients)
# section that repeats the weekday names in a different format, so only look
# at the part before it.
menu_section = text.split('Innihaldslýsing')[0]

# 3. Split the menu section into per-weekday blocks.
day_pattern = r'(Mánudagur|Þriðjudagur|Miðvikudagur|Fimmtudagur|Föstudagur|Laugardagur|Sunnudagur)\s+([^\n]*)'
matches = list(re.finditer(day_pattern, menu_section))

day_block = None
day_header = None
for i, match in enumerate(matches):
    if match.group(1).lower() != current_day:
        continue
    start = match.end()
    end = matches[i + 1].start() if i + 1 < len(matches) else len(menu_section)
    day_block = menu_section[start:end]
    day_header = match.group(2).strip()
    break

if day_block is None:
    sys.exit(1)

# The header is like "3. ágúst" or "3. ágúst Frídagur verslunarmanna": split
# off the date from any trailing holiday note.
header_match = re.match(r'^(\d{1,2}\.\s*\S+)\s*(.*)$', day_header)
if header_match:
    date_str, holiday = header_match.group(1), header_match.group(2).strip()
else:
    date_str, holiday = day_header, ''

dishes = [line.strip(' .') for line in day_block.split('\n') if line.strip()]
if not dishes:
    sys.exit(1)

# The main course is the last dish listed in the PDF; put it first.
dishes = list(reversed(dishes))

day_dative = current_day[:-2] + 'inn'
output = f"Matur í mötuneyti {day_dative} {date_str}:\n\n"
if holiday:
    output += f" {holiday}!\n"
if current_day == "fimmtudagur":
    output += " KAKA!\n"
for dish in dishes:
    output += f" {dish}\n"

print(output.strip())
