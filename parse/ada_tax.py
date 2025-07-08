# PROCESSES A SINGLE RECORD AT A TIME... 

#THIS IS LIKELY A NEW IMPORT - I DON'T THINK I USED IT IN THE INITIAL SCRIPT,
# BUT IT'S COMMON SO I SUSPECT WE'LL USE IT IN THE FUTURE

from bs4 import BeautifulSoup 
import re

def extract_full_property_summary(html: str):
    soup = BeautifulSoup(html, "html.parser")
    results = {
        "parcel": None,
        "parcel_status": None,
    }

    # BASICS 
    for div in soup.find_all("div", class_="col-xxl-2"):
        if "Parcel:" in div.text:
            strong = div.find("strong")
            if strong:
                results["parcel"] = strong.get_text(strip=True)
        elif "Parcel Status:" in div.text:
            span = div.find("span")
            if span:
                results["parcel_status"] = span.get_text(strip=True)

    # SECTIONS
    for item in soup.select(".accordion-item"):
        header_btn = item.select_one(".accordion-button")
        section_title = header_btn.get_text(strip=True) if header_btn else "Untitled Section"

        body = item.select_one(".accordion-body")
        if not body:
            continue
        section = {
            section_title: {}
        }

        # INDIVIDUAL FIELDS FOR THE SECTION
        for b_tag in body.find_all("b"):
            label = b_tag.get_text(strip=True).rstrip(":")
            next_sibling = b_tag.next_sibling

            if next_sibling and isinstance(next_sibling, str):
                value = next_sibling.strip()
                if value and label != 'Note':
                    section[section_title].update({label: value})
        
        # TABLES IN EACH SECTION
        for table in body.find_all("table"):
            tbl = {}
            headers = [th.get_text(strip=True) for th in table.select("thead th")]
            #print(headers)
            rows = []
            for tr in table.select("tbody tr"):
                cells = [td.get_text(strip=True) for td in tr.select("td")]
                #print(cells)
                if len(cells) == len(headers):
                    rows.append(dict(zip(headers, cells)))
            tbl.update({table.get("id"):rows})
            #print(tbl)
        
            section[section_title].update(tbl)
        #print(section)
            
    
        results.update(section)
        

    return results

def clean_name(strvalue):
    if bool(re.match(r'^[a-z]+[A-Z]', strvalue)):
        s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', strvalue)
            
        clean = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    else:
        clean = strvalue.lower().replace(' ','_').replace('/','_')
    return clean

def clean_keys(obj, clean_func):
    if isinstance(obj, dict):
        return {clean_func(k): clean_keys(v, clean_func) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_keys(item, clean_func) for item in obj]
    else:
        return obj

#THIS IS THE MAIN EXECUTION STARTS
if __name__ == "__main__":
    with open("/Users/paigegiese/Downloads/flying_m_ex.html", "r", encoding="utf-8") as f:
        text = f.read()

    # FIRST PASS EXTRACTION - FORMATTING
    prep = extract_full_property_summary(text)

    # Reformatting the characteristics section because it looked janky...
    new_characteristics = []
    for k,v in prep['Characteristics'].items():
        new_format={}
        for trait in v:
            new_format.update({trait['Characteristic']: trait['Value']})
        
        #print(new_format)
        replacement = {k:new_format}
        new_characteristics.append(replacement)

    #print(v)
    prep.pop('Characteristics')
    prep.update({'characteristics': new_characteristics})

 
    
    final = clean_keys(prep, clean_name)


# PREVIEW
import pprint
pprint.pprint(final)



