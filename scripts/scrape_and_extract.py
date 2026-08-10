import sys
import re
from io import BytesIO

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pdfminer.high_level import extract_text

WEEKDAYS = ["mánudagur", "þriðjudagur", "miðvikudagur", "fimmtudagur", "föstudagur", "laugardagur", "sunnudagur"]
MONTHS = {
    "janúar": 1, "febrúar": 2, "mars": 3, "apríl": 4, "maí": 5, "júní": 6,
    "júlí": 7, "ágúst": 8, "september": 9, "október": 10, "nóvember": 11, "desember": 12,
}

BASE_URL = "https://www.mulakaffi.is"
PAGE_URL = f"{BASE_URL}/is/veitingastadurinn/matarbakkar"

headers = {'User-Agent': 'Mozilla/5.0'}

today = datetime.today()
current_day = WEEKDAYS[today.weekday()]

# 1. Find all menu PDF links on the Fyrirtækjaþjónusta page. The page can list
# more than one week's PDF at once (e.g. while last week's is still linked
# alongside the new one), so we can't just take the first link.
response = requests.get(PAGE_URL, headers=headers)
if response.status_code != 200:
    sys.exit(1)

soup = BeautifulSoup(response.content, 'html.parser')
pdf_links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].lower().endswith('.pdf')]
if not pdf_links:
    sys.exit(1)
pdf_links = [BASE_URL + link if link.startswith('/') else link for link in pdf_links]

# Try the links newest-first (later links on the page tend to be the newer
# week) and use the first one whose menu date actually matches today.
result = None
for pdf_link in reversed(pdf_links):
    pdf_response = requests.get(pdf_link, headers=headers)
    if pdf_response.status_code != 200:
        continue

    text = extract_text(BytesIO(pdf_response.content))

    # The PDF has a weekly menu section followed by an "Innihaldslýsing"
    # (ingredients) section that repeats the weekday names in a different
    # format, so only look at the part before it.
    menu_section = text.split('Innihaldslýsing')[0]

    # Split the menu section into per-weekday blocks.
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
        continue

    # The header is like "3. ágúst" or "3. ágúst Frídagur verslunarmanna":
    # split off the date from any trailing holiday note.
    header_match = re.match(r'^(\d{1,2}\.\s*\S+)\s*(.*)$', day_header)
    if header_match:
        date_str, holiday = header_match.group(1), header_match.group(2).strip()
    else:
        date_str, holiday = day_header, ''

    # Verify the menu's date actually matches today, so a stale (last week's)
    # PDF doesn't get reported as current.
    date_match = re.match(r'^(\d{1,2})\.\s*(\S+)$', date_str)
    if not date_match:
        continue

    menu_day = int(date_match.group(1))
    menu_month = MONTHS.get(date_match.group(2).lower().rstrip('.'))
    if menu_month is None:
        continue

    if (menu_day, menu_month) != (today.day, today.month):
        continue

    result = (day_block, date_str, holiday)
    break

if result is None:
    print(f"No menu PDF found with today's date ({today.day:02d}.{today.month:02d}).", file=sys.stderr)
    sys.exit(1)

day_block, date_str, holiday = result

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
