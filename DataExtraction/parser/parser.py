import requests
from bs4 import BeautifulSoup, Tag

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    )
}


def clean(text):

    if text is None:
        return ""

    return " ".join(text.replace("\n", " ").split())


#############################################################
# Generic Heading Extractor
#############################################################

def extract_heading_values(box):

    data = {}

    headings = box.find_all("h4", class_="box1-title")

    for h in headings:

        heading = clean(
            h.get_text().replace("-", "")
        )

        value = ""

        node = h.next_sibling

        while node:

            if isinstance(node, Tag):

                if node.name == "h4":
                    break

                if node.name == "br":
                    node = node.next_sibling
                    continue

                txt = clean(node.get_text(" ", strip=True))

            else:

                txt = clean(str(node))

            if txt:

                value += txt + " "

            node = node.next_sibling

        data[heading] = value.strip()

    return data


#############################################################
# Botanical Synonyms
#############################################################

def extract_synonyms(soup):

    synonyms = []

    ul = soup.find("ul", id="mysynonyms")

    if ul is None:
        return synonyms

    for li in ul.find_all("li"):

        a = li.find("a")

        if a:

            synonyms.append(clean(a.get_text()))

        else:

            txt = clean(li.get_text())

            if txt:
                synonyms.append(txt)

    return synonyms


#############################################################
# Vernacular Names
#############################################################

def extract_vernacular(soup):

    names = {}

    for div in soup.find_all("div", class_="ver_name"):

        title = div.find("span", class_="ver_title")

        if title is None:
            continue

        language = clean(title.get_text())

        title.extract()

        text = clean(div.get_text())

        names[language] = text

    return names


#############################################################
# Bibliography
#############################################################

def extract_bibliography(soup):

    books = []

    sidebar = soup.find("td", id="sidebar")

    if sidebar is None:
        return books

    for li in sidebar.find_all("li"):

        title = li.find("div", class_="booktitle")

        author = li.find("div", class_="bookauthor")

        if title:

            books.append({

                "title":
                    clean(title.get_text()),

                "author":
                    clean(author.get_text())
                    if author else ""

            })

    return books


#############################################################
# Distribution
#############################################################

def extract_distribution(soup):

    dist = []

    for div in soup.find_all("div", class_="hiddendistrititle"):

        content = div.find_all("div")

        if len(content) < 2:
            continue

        distribution = clean(content[1].get_text())

        title = div.find("div", class_="booktitle")

        author = div.find("div", class_="bookauthor")

        dist.append({

            "distribution": distribution,

            "title":
                clean(title.get_text())
                if title else "",

            "author":
                clean(author.get_text())
                if author else ""

        })

    return dist


#############################################################
# Images
#############################################################

def extract_images(soup):

    images = []

    for img in soup.find_all("img"):

        src = img.get("src")

        if not src:
            continue

        if src.startswith("/"):

            src = "https://www.medicinalplants.in" + src

        elif src.startswith("images"):

            src = "https://www.medicinalplants.in/" + src

        images.append(src)

    return list(set(images))


#############################################################
# Main Parser
#############################################################

def parse_detail_page(url):

    html = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    html.raise_for_status()

    soup = BeautifulSoup(
        html.text,
        "html.parser"
    )

    result = {}

    #########################################################

    box = soup.find("div", class_="box1-left")

    if box:

        result.update(
            extract_heading_values(box)
        )

    #########################################################

    result["Botanical Synonyms"] = \
        extract_synonyms(soup)

    result["Vernacular Names"] = \
        extract_vernacular(soup)

    result["Bibliography"] = \
        extract_bibliography(soup)

    result["Distribution"] = \
        extract_distribution(soup)

    result["Images"] = \
        extract_images(soup)

    result["URL"] = url

    return result


#############################################################
# Main Process
#############################################################

if __name__ == "__main__":

    import pandas as pd
    import json
    from tqdm import tqdm

    INPUT_CSV = "../links/links.csv"
    OUTPUT_CSV = "../parser/plant_details.csv"
    OUTPUT_JSON = "../parser/plant_details.json"

    # Read links from CSV
    df = pd.read_csv(INPUT_CSV)
    df.columns = df.columns.str.strip()

    if "Detail URL" not in df.columns:
        print(f"Error: 'Detail URL' column not found.")
        print(f"Available columns: {df.columns.tolist()}")
        exit(1)

    # Filter valid URLs
    urls = df[df["Detail URL"].notna()]["Detail URL"].unique().tolist()

    print(f"\nProcessing {len(urls)} plant links...\n")

    all_plants = []

    for url in tqdm(urls):

        try:
            plant_data = parse_detail_page(url)
            all_plants.append(plant_data)
        except Exception as e:
            print(f"\nError parsing {url}: {e}")
            all_plants.append({
                "URL": url,
                "Error": str(e)
            })

    # Save to JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_plants, f, indent=2, ensure_ascii=False)

    # Convert to DataFrame for CSV export
    # Flatten nested structures
    csv_data = []

    for plant in all_plants:

        row = {}

        for key, value in plant.items():

            if isinstance(value, dict):
                # Convert dict to JSON string
                row[key] = json.dumps(value, ensure_ascii=False)

            elif isinstance(value, list):
                # Convert list to comma-separated string
                if value and isinstance(value[0], dict):
                    row[key] = json.dumps(value, ensure_ascii=False)
                else:
                    row[key] = "; ".join(str(v) for v in value)

            else:
                row[key] = value

        csv_data.append(row)

    output_df = pd.DataFrame(csv_data)
    output_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"\n===================================")
    print("Finished Successfully!")
    print(f"Extracted {len(all_plants)} plants")
    print(f"Saved CSV: {OUTPUT_CSV}")
    print(f"Saved JSON: {OUTPUT_JSON}")
    print("===================================\n")