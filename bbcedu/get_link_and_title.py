import requests
from bs4 import BeautifulSoup
from log import log_step
from urllib.parse import urljoin

def get_links_and_titles(page_url, base_url, headers):
    try:
        response = requests.get(page_url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        
        articles = soup.select('a.ssrcss-9haqql-LinkPostLink')

        results = []

        for a in articles:
            link = a.get('href', '')
            full_link = urljoin(base_url, link)

            # Try to extract the "aria-hidden" span text as the main title
            headline_span = a.select_one('span[aria-hidden="true"].ssrcss-yjj6jm-LinkPostHeadline')
            title = headline_span.get_text(strip=True) if headline_span else a.get_text(strip=True)

            log_step(f"Found title: {title} | Link: {full_link}")

            if title and link:
                results.append({
                    'title': title,
                    'link': full_link
                })

        log_step(f"Total titles found on {page_url}: {len(results)}")
        return results

    except Exception as e:
        log_step(f"Error fetching {page_url}: {str(e)}")
        return []
