"""
Run this FIRST to find the exact "See More" button selector.
It opens a visible browser so you can see what's happening.
"""
import asyncio
from playwright.async_api import async_playwright

async def find_see_more_button():
    async with async_playwright() as p:
        # headless=False so you can SEE the browser
        browser = await p.chromium.launch(headless=False)
        page    = await browser.new_page()

        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        })

        print("🌐 Loading page...")
        await page.goto(
            "https://www.kapruka.com/online/cakes",
            timeout=60000,
            wait_until="domcontentloaded"
        )
        await asyncio.sleep(5)

        # ── Scroll to bottom ──────────────────────────
        print("📜 Scrolling to bottom...")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(3)

        # ── Try to dump ALL anchor tags near bottom ───
        print("\n🔍 All <a> tags found on page:")
        print("─" * 60)
        links = await page.evaluate("""
            () => {
                const allLinks = Array.from(document.querySelectorAll('a'));
                return allLinks.map(a => ({
                    text    : a.textContent.trim(),
                    class   : a.className,
                    href    : a.href,
                    id      : a.id
                })).filter(a =>
                    a.text.toLowerCase().includes('more') ||
                    a.text.toLowerCase().includes('load') ||
                    a.text.toLowerCase().includes('show') ||
                    a.class.toLowerCase().includes('more') ||
                    a.class.toLowerCase().includes('load')
                );
            }
        """)
        for link in links:
            print(f"  TEXT  : {link['text']}")
            print(f"  CLASS : {link['class']}")
            print(f"  HREF  : {link['href']}")
            print(f"  ID    : {link['id']}")
            print("  ─────")

        # ── Also check for buttons ────────────────────
        print("\n🔍 All <button> tags found on page:")
        print("─" * 60)
        buttons = await page.evaluate("""
            () => {
                const allBtns = Array.from(document.querySelectorAll('button'));
                return allBtns.map(b => ({
                    text  : b.textContent.trim(),
                    class : b.className,
                    id    : b.id
                })).filter(b =>
                    b.text.toLowerCase().includes('more') ||
                    b.text.toLowerCase().includes('load') ||
                    b.text.toLowerCase().includes('show') ||
                    b.class.toLowerCase().includes('more') ||
                    b.class.toLowerCase().includes('load')
                );
            }
        """)
        for btn in buttons:
            print(f"  TEXT  : {btn['text']}")
            print(f"  CLASS : {btn['class']}")
            print(f"  ID    : {btn['id']}")
            print("  ─────")

        # ── Check divs too ────────────────────────────
        print("\n🔍 All <div> tags that might be the button:")
        print("─" * 60)
        divs = await page.evaluate("""
            () => {
                const allDivs = Array.from(document.querySelectorAll('div'));
                return allDivs.map(d => ({
                    text  : d.textContent.trim().substring(0, 50),
                    class : d.className,
                    id    : d.id
                })).filter(d =>
                    d.text.toLowerCase().includes('see more') ||
                    d.class.toLowerCase().includes('loadmore') ||
                    d.class.toLowerCase().includes('load-more') ||
                    d.class.toLowerCase().includes('seemore')
                );
            }
        """)
        for div in divs:
            print(f"  TEXT  : {div['text']}")
            print(f"  CLASS : {div['class']}")
            print(f"  ID    : {div['id']}")
            print("  ─────")

        print("\n✅ Done! Check the output above for the button selector.")
        print("Browser staying open for 15 seconds so you can inspect manually...")
        await asyncio.sleep(15)
        await browser.close()

asyncio.run(find_see_more_button())