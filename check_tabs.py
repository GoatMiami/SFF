import requests, json

tabs = requests.get('http://localhost:8080/json').json()
print(f"Total tabs: {len(tabs)}")
for tab in tabs:
    title = tab.get('title', '')
    url = tab.get('url', '')
    tab_id = tab.get('id', '')
    print(f"\n  Title: {title}")
    print(f"  URL:   {url}")
    print(f"  ID:    {tab_id}")
