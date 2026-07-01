import requests
from bs4 import BeautifulSoup
from datetime import datetime

weekdays = ["mánudagur", "þriðjudagur", "miðvikudagur", "fimmtudagur", "föstudagur", "laugardagur", "sunnudagur"]

today = datetime.today()
current_day = weekdays[today.weekday()]

headers = {'User-Agent': 'Mozilla/5.0'}
response = requests.get('https://www.mulakaffi.is/is/veitingastadurinn/matarbakkar', headers=headers)
if response.status_code != 200:
    exit()

soup = BeautifulSoup(response.content, 'html.parser')

for block in soup.find_all('div', class_='menuItem'):
    parts = [t.strip() for t in block.get_text(separator='|').split('|') if t.strip()]
    # parts: ['Matseðill dagsins', 'miðvikudagur', '1. júlí', item1, item2, item3, ...]
    if len(parts) >= 4 and parts[1].lower() == current_day:
        date = parts[2]
        items = parts[3:]
        day_dative = current_day[:-2] + 'inn'
        output = f"Matur í mötuneyti {day_dative} {date}:\n\n"
        if len(items) == 4:
            holiday, vegan, main_course, soup_item = items
            output += f" {holiday}!\n"
            if current_day == "fimmtudagur":
                output += " KAKA!\n"
            if main_course: output += f" {main_course}\n"
            if soup_item: output += f" Súpa: {soup_item}\n"
            if vegan: output += f" Vegan: {vegan}\n"
        else:
            vegan, main_course, soup_item = items
            if current_day == "fimmtudagur":
                output += " KAKA!\n"
            if main_course: output += f" {main_course}\n"
            if soup_item: output += f" Súpa: {soup_item}\n"
            if vegan: output += f" Vegan: {vegan}\n"
        print(output.strip())
        break
else:
    print(f"No menu found for today: {current_day}.")
