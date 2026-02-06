def run(page):
    page.goto("https://example.com")
    page.get_by_role("link", name="Learn more").click()
    
