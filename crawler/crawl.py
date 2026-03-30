import asyncio
import json
from playwright.async_api import async_playwright

async def scrape_kapruka_cakes():
    all_products = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page    = await browser.new_page()

        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        })

        # ── Step 1: Load page ──────────────────────────
        print("Loading kapruka cakes page...")
        await page.goto(
            "https://www.kapruka.com/online/cakes",
            timeout=60000,
            wait_until="domcontentloaded"
        )

        print("⏳ Waiting for products to render...")
        await asyncio.sleep(5)

        # ── Step 2: Confirm products exist ─────────────
        try:
            await page.wait_for_selector("div.catalogueV2Repeater", timeout=20000)
            count = len(await page.query_selector_all("div.catalogueV2Repeater"))
            print(f"Products found! Initial count: {count}")
        except Exception as e:
            print(f"Could not find products: {e}")
            await browser.close()
            return []

        # ── Step 3: Click "See More Products" ──────────
        # Confirmed selectors from debug:
        #   <a id="viewMoreButton">See More Products</a>
        #   <div id="pagination_btn" class="common_button">

        click_count = 0
        max_clicks  = 40  # 975 products / 30 per click = ~33 clicks

        while click_count < max_clicks:
            try:
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                # Count before
                before = len(await page.query_selector_all("div.catalogueV2Repeater"))

                # Confirmed ID from debug output
                see_more = await page.query_selector("a#viewMoreButton")

                # Fallback 1: div wrapper
                if not see_more:
                    see_more = await page.query_selector("div#pagination_btn")

                # Fallback 2: class name
                if not see_more:
                    see_more = await page.query_selector(".common_button")

                if not see_more:
                    print("'See More' button gone. All products loaded!")
                    break

                # Check visibility
                is_visible = await see_more.is_visible()
                if not is_visible:
                    print("Button hidden. All products loaded!")
                    break

                # Click
                await see_more.click()
                await asyncio.sleep(3)

                # Count after
                after = len(await page.query_selector_all("div.catalogueV2Repeater"))

                click_count += 1
                print(f"  Click #{click_count} — total products: {after}")

                # Stop if nothing new loaded
                if after <= before:
                    print("No new products added. Done!")
                    break

            except Exception as e:
                print(f" Stopped: {e}")
                break

        print(f"\n Finished loading. Total clicks: {click_count}")

        # ── Step 4: Extract all products ───────────────
        print("Extracting product data...")
        cards = await page.query_selector_all("div.catalogueV2Repeater")
        print(f"Total cards: {len(cards)}")

        for i, card in enumerate(cards):
            try:
                name_el  = await card.query_selector("div.catalogueV2heading")
                name     = (await name_el.text_content()).strip() if name_el else "N/A"

                price_el = await card.query_selector("span.catalogueV2converted")
                price    = (await price_el.text_content()).strip() if price_el else "N/A"

                link_el  = await card.query_selector("a")
                link     = await link_el.get_attribute("href") if link_el else ""

                img_el   = await card.query_selector("img")
                image    = await img_el.get_attribute("src") if img_el else "N/A"

                badge_el = await card.query_selector("div.ribbon-drop span")
                badge    = (await badge_el.text_content()).strip() if badge_el else ""

                weight_el = await card.query_selector("div.thumb-text span")
                weight    = (await weight_el.text_content()).strip() if weight_el else ""

                product = {
                    "name"        : name,
                    "price"       : price,
                    "weight"      : weight,
                    "badge"       : badge,
                    "category"    : "cakes",
                    "availability": "In Stock",
                    "image_url"   : image,
                    "product_url" : f"https://www.kapruka.com{link}" if link else "N/A"
                }

                all_products.append(product)

                if (i + 1) % 50 == 0:
                    print(f" Extracted {i + 1} products...")

            except Exception as e:
                print(f" Error on product {i}: {e}")
                continue

        await browser.close()

    return all_products


async def main():
    print("🕷️  Kapruka Cake Scraper")
    print("=" * 40)

    products = await scrape_kapruka_cakes()

    if not products:
        print("No products scraped.")
        return

    with open("data/cakes.json", "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    print(f"💾 Saved to data/cakes.json") #950 products



asyncio.run(main())