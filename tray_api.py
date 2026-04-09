import os
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def fetch_tray_report(username, password, store_number, period="Today", debug_visible=True):
    """
    Automates logging into Tray, navigating to the Checks report, and downloading the CSV.
    period can be "Today" or "Yesterday".
    Returns the path to the downloaded CSV.
    """
    # By default, debug_visible=True runs in headed mode so you can watch it click.
    # In production on Streamlit, we will set this to False.
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not debug_visible)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        
        try:
            print("[1] Navigating to login page...")
            page.goto("https://hq.dine.tray.com", wait_until="networkidle")
            
            print("[2] Logging in...")
            # We use loose text/placeholder matchers for resilience
            page.fill("input[type='email'], input[placeholder*='Email'], input#username", username)
            page.fill("input[type='password'], input[placeholder*='Password']", password)
            page.click("button[type='submit'], input[type='submit'], button:has-text('Log In'), button:has-text('Sign In'), button:has-text('Login')")
            
            # Wait for dashboard to load
            print("[3] Waiting for Dashboard...")
            page.wait_for_selector("text=Logout", timeout=15000)
            
            print("[4] Navigating directly to Checks Report via URL...")
            page.goto("https://hq.dine.tray.com/tray/admin/reports?page=closeTabs", wait_until="networkidle")
            
            # Wait for the report page to fully load
            page.wait_for_selector("text='Run Report'", timeout=10000)
            
            print(f"[5] Setting Period to {period}...")
            # Wait a moment for dynamic dropdowns to initialize
            page.wait_for_timeout(2000) 
            
            # This handles both standard <select> and custom div dropdowns
            try:
                page.select_option("select[name*='period']", label=period)
            except:
                # If it's a custom dropdown
                page.click("div:has-text('Period :') + div, span:has-text('Period') + div")
                page.click(f"text='{period}'")
            
            print(f"[6] Selecting Site: {store_number}...")
            # Click the Sites dropdown wrapper
            page.click("text=Sites :") # Click the label to focus the area
            page.click("div:has-text('Sites :') + div, button:has-text('Sites'), .sites-dropdown-selector")
            page.wait_for_timeout(1000)
            
            # The search input is tricky. To avoid typing in 'Start Date', we target the dropdown search specifically
            # or simply look for an input that isn't for dates or check IDs.
            try:
                # Try clicking it if it's already visible in the tree menu
                page.click(f"text=IHOP #{store_number}", timeout=2000)
            except:
                # Otherwise, type it into the visible search box (excluding the date/check id fields)
                search_boxes = page.locator("input[type='text']:visible:not([id*='Date']):not([name*='date']):not([id*='ate']):not([id*='Check'])")
                if search_boxes.count() > 0:
                    search_boxes.first.fill(store_number)
                page.wait_for_timeout(1500) # Wait for search results
                page.click(f"text=IHOP #{store_number}")
                
            page.keyboard.press("Escape") # Close dropdown
            
            print(f"[7] Selecting Tender Type: Card...")
            page.click("text=Tender Type :")
            page.click("div:has-text('Tender Type :') + div, span:has-text('Tender Type') + div")
            page.wait_for_timeout(1000)
            
            # 'Card' is usually immediately visible. We use exact match 'Card'
            # to avoid accidentally targeting the "Gift Card" navigation button.
            # We filter for visible=True because there's a hidden <option> tag for Card!
            page.locator("text='Card'").filter(visible=True).click()
            page.keyboard.press("Escape") # Close dropdown
            
            print("[8] Running Report & Waiting for data to load...")
            page.click("text='Run Report'")
            
            # Wait for the CSV link to appear (meaning the table loaded)
            with page.expect_download(timeout=60000) as download_info:
                # Based on the screenshot, it's just the word CSV next to a little icon
                page.locator("text=CSV").filter(visible=True).first.click()
            
            download = download_info.value
            
            # Save it temporarily to the current folder
            file_name = f"Tray_Checks_Report_{store_number}_{period}.csv"
            save_path = os.path.join(os.getcwd(), file_name)
            download.save_as(save_path)
            
            print(f"[SUCCESS] Downloaded report to: {save_path}")
            return save_path

        except Exception as e:
            print(f"[ERROR] Script failed: {e}")
            # Take a screenshot if it fails so we can see what selector it got stuck on
            error_img = "debug_tray_error.png"
            page.screenshot(path=error_img)
            print(f"Saved {error_img} so we can diagnose the UI.")
            return None
        finally:
            browser.close()

if __name__ == "__main__":
    # --- Instructions to test locally ---
    # 1. Update your email and password below
    # 2. Run: pip install playwright
    # 3. Run: playwright install
    # 4. Run: python tray_scraper.py
    
    USERNAME = "chad.g@prpone.com"
    PASSWORD = "IhOp8314638!"
    STORE = "4463"
    PERIOD = "Today" # Or "Yesterday"
    
    if USERNAME == "your_email@prpone.com":
        print("Please update the USERNAME and PASSWORD at the bottom of the script before running!")
    else:
        fetch_tray_report(USERNAME, PASSWORD, STORE, period=PERIOD, debug_visible=True)
