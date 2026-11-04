import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

file_lock = threading.Lock()
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "bb_cookie_pool.txt")

def capture_hyderabad_cookie_worker(worker_id):
    chrome_options = Options()
    chrome_options.add_argument("--incognito")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=800,600")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    
    driver = webdriver.Chrome(options=chrome_options)
    cookie_string = None
    
    try:
        driver.get("https://www.bigbasket.com/")
        time.sleep(2.5)
        
        # Inject Hyderabad Coordinates + BB NOW (Quick Commerce) Context
        driver.add_cookie({"name": "_bb_cid", "value": "3", "domain": ".bigbasket.com", "path": "/"})
        driver.add_cookie({"name": "_bb_pin_code", "value": "500006", "domain": ".bigbasket.com", "path": "/"})
        driver.add_cookie({"name": "is_global", "value": "0", "domain": ".bigbasket.com", "path": "/"})
        driver.add_cookie({"name": "xentrycontext", "value": "bbnow", "domain": ".bigbasket.com", "path": "/"})
        driver.add_cookie({"name": "xentrycontextid", "value": "10", "domain": ".bigbasket.com", "path": "/"})
        driver.add_cookie({"name": "_bb_lat_long", "value": '"MTcuMzgzMjU5fDc4LjQzODU5MjI="', "domain": ".bigbasket.com", "path": "/"})
        driver.add_cookie({"name": "_bb_sa_ids", "value": "14761,21951,23278,31099", "domain": ".bigbasket.com", "path": "/"})
        driver.add_cookie({"name": "_bb_cda_sa_info", "value": "djIuY2RhX3NhLjEwLjE0NzYxLDIxOTUxLDIzMjc4LDMxMDk5", "domain": ".bigbasket.com", "path": "/"})
        driver.add_cookie({"name": "_bb_addressinfo", "value": "MTcuMzgzMjU5fDc4LjQzODU5MjJ8U0JJIENvbG9ueSwgR3VkaW1hbGthcHVyfDUwMDAwNnxIeWRlcmFiYWR8MXxmYWxzZXx0cnVlfHRydWV8QmlnYmFza2V0ZWVy", "domain": ".bigbasket.com", "path": "/"})
        
        time.sleep(0.5)
        
        selenium_cookies = driver.get_cookies()
        if selenium_cookies:
            cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in selenium_cookies])
            
    except Exception:
        pass
    finally:
        driver.quit()
        
    return cookie_string

def build_hyderabad_pool(target_total=10, max_simultaneous_workers=4):
    print("Starting BB NOW token initialization engine...")
    success_count = 0
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        pass

    with ThreadPoolExecutor(max_workers=max_simultaneous_workers) as executor:
        futures = {executor.submit(capture_hyderabad_cookie_worker, i): i for i in range(1, target_total + 1)}
        
        for future in as_completed(futures):
            try:
                cookie_res = future.result()
                if cookie_res and "bbnow" in cookie_res:
                    with file_lock:
                        success_count += 1
                        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                            f.write(cookie_res + "\n")
                        print(f"[{success_count}/{target_total}] Compiled BB NOW session.")
            except Exception:
                pass
            time.sleep(0.1)

if __name__ == "__main__":
    build_hyderabad_pool(target_total=15, max_simultaneous_workers=4)
