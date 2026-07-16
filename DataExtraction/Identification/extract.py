from playwright.sync_api import sync_playwright, TimeoutError
import pandas as pd

BASE_URL = "https://www.medicinalplants.in/sanskritauthentication"

all_rows = []
seen = set()

with sync_playwright() as p:

    browser = p.chromium.launch(headless=False)

    page = browser.new_page()

    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    page_no = 1

    while True:

        iframe = page.frame(
            url=lambda url: "sanskritauthenticationdetails" in url
        )

        if iframe is None:
            print("Iframe not found.")
            break

        print(f"\n========== PAGE {page_no} ==========")
        print("URL:", iframe.url)

        # ----------------------------
        # Extract data directly from DOM
        # ----------------------------
        records = iframe.evaluate("""
        () => {

            const rows = [];

            document.querySelectorAll("table").forEach(table => {

                const headers = [...table.querySelectorAll("th")]
                    .map(x => x.innerText.trim());

                [...table.querySelectorAll("tr")]
                    .slice(1)
                    .forEach(r => {

                        const cols = [...r.querySelectorAll("td")]
                            .map(td => td.innerText.trim());

                        if(cols.length !== headers.length)
                            return;

                        let obj = {};

                        headers.forEach((h,i)=>{
                            obj[h] = cols[i];
                        });

                        rows.push(obj);

                    });

            });

            return rows;

        }
        """)

        print("Rows on page:", len(records))

        for record in records:

            key = (
                record.get("Ref. Drug Name", ""),
                record.get("Botanical correlations", ""),
                record.get("Status of correlation", ""),
                record.get(
                    "Discussions on its identity by experts with reference",
                    ""
                ),
                record.get("References", "")
            )

            if key not in seen:
                seen.add(key)
                all_rows.append(record)

        print("Total extracted:", len(all_rows))

        # ----------------------------
        # Save progress after every page
        # ----------------------------
        pd.DataFrame(all_rows).to_csv(
            "identity.csv",
            index=False,
            encoding="utf-8-sig"
        )

        # ----------------------------
        # Find Next button
        # ----------------------------
        next_button = iframe.locator("#srinipaginationNext")

        if next_button.count() == 0:
            print("\nNo Next button found.")
            break

        try:
            next_button.click(timeout=5000)

            # Give the iframe time to reload
            page.wait_for_timeout(1200)

            page_no += 1

        except TimeoutError:
            print("No more pages.")
            break

# ----------------------------------------
# Save final CSV
# ----------------------------------------

df = pd.DataFrame(all_rows)

df.to_csv(
    "identity.csv",
    index=False,
    encoding="utf-8-sig"
)

print("\n===================================")
print("Finished")
print("Total records:", len(df))
print("===================================")