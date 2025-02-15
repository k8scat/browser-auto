import time
import os
from browser import Edge, run_in_browser

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def delete_item(driver: WebDriver):
    operator_buttons = driver.find_elements(By.CSS_SELECTOR, 'span[class="operate-btn"]')
    for operator_button in operator_buttons:
        if operator_button.text == "不合适":
            operator_button.click()
            time.sleep(1)
            operator_button.click()
            break
    
def process_first_item(driver: WebDriver):
    items = WebDriverWait(driver, 60).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div[role="group"]>div[role="listitem"]'))
    )
    if len(items) == 0:
        print("No items found")
        os.exit(1)

    item = items[0]
    item.click()
    time.sleep(10)

    try:
        name = WebDriverWait(item, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'span[class~="geek-name"]'))
        ).text
    except Exception as e:
        print(f"get name failed: {e}")
        raise e
    
    try:
        job = WebDriverWait(item, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'span[class~="source-job"]'))
        ).text
    except Exception as e:
        print(f"get job failed: {e}")
        raise e


    chat = driver.find_element(By.CSS_SELECTOR, 'div[class="chat-message-list is-to-top"]')
    spans = chat.find_elements(By.CSS_SELECTOR, 'span[class="card-btn"]')
    for span in spans:
        if span.text == "点击预览附件简历":
            print(f"{name} {job} 简历已获取")
            delete_item(driver)
            return
    

    try:
        msg_items = chat.find_elements(By.CSS_SELECTOR, 'div[class="item-system"]>div[class="text"]>span')
        if len(msg_items) > 0:
            msg_item = msg_items[0]
            if msg_item.text == "简历请求已发送":
                print(f"{name} {job} 简历请求已发送")
                delete_item(driver)
                return
    
    except Exception as e:
        print(e)

    
    operator_buttons = driver.find_elements(By.CSS_SELECTOR, 'span[class="operate-btn"]')
    for operator_button in operator_buttons:
        if operator_button.text == "求简历":
            operator_button.click()
            time.sleep(10)

            send_button = driver.find_element(By.CSS_SELECTOR, 'span[class="boss-btn-primary boss-btn"]')
            send_button.click()
            time.sleep(10)

            print(f"{name} {job} 求简历 发送成功")

            print(f"wait 1m")
            time.sleep(60)

            delete_item(driver)
                

def main():
    browser = Edge()
    profile = "Default"
    def fn(driver):
        err_count = 0

        while True:
            driver.get("https://www.zhipin.com/web/chat/index")

            try:
                process_first_item(driver)
                err_count = 0
            except Exception as e:
                print(f"process first item failed: {e}")
                err_count += 1
                if err_count >= 3:
                    raise e

            print(f"wait 10m")
            time.sleep(600)
        
    run_in_browser(browser, profile, fn, kill_browser_before_running=True)


if __name__ == "__main__":
    main()
