from bs4 import BeautifulSoup, Comment
from log import log_step
from playwright.sync_api import sync_playwright
import requests
import uuid

def get_full_content(post_url, headers):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(extra_http_headers=headers)
            page = context.new_page()

            page.goto(post_url, timeout=10000)
            page.wait_for_selector('article', timeout=5000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, 'lxml')
        content_root = soup.find('article')
        if not content_root:
            log_step(f"No article element found at {post_url}")
            return '', ''

        # Remove headline-block and byline-block
        for block in content_root.find_all(['div'], attrs={'data-component': ['headline-block', 'byline-block']}):
            block.decompose()

        # Remove comments
        for comment in content_root.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Fix URLs in <img> and <video>
        image_urls = []
        video_urls = []
        for tag in content_root.find_all(['img', 'video']):
            if tag.name == 'img':
                src = tag.get('src', '')
                if src and not src.startswith('http'):
                    src = 'https://ichef.bbci.co.uk' + src if src.startswith('news/') else 'https://ichef.bbci.co.uk/news/800/cpsprodpb/f784/live' + src
                tag['src'] = src
                tag['width'] = '720px'
                image_urls.append(src)

            if tag.name == 'video':
                src = tag.get('src', '')
                poster = tag.get('poster', '')

                if src and not src.startswith('http'):
                    src = 'https://ichef.bbci.co.uk' + src if src.startswith('news/') else 'https://ichef.bbci.co.uk/news/800/cpsprodpb/f784/live' + src
                if poster and not poster.startswith('http'):
                    poster = 'https://ichef.bbci.co.uk' + poster if poster.startswith('news/') else 'https://ichef.bbci.co.uk/news/800/cpsprodpb/f784/live' + poster

                tag['src'] = src
                tag['poster'] = poster
                tag['width'] = '720px'
                if 'controls' not in tag.attrs:
                    tag['controls'] = ''
                video_urls.append(src)

        cleaned_html = str(content_root)

        # Pick featured image
        featured_image = image_urls[0] if image_urls else None
        if featured_image:
            try:
                response = requests.head(featured_image, headers=headers, timeout=5)
                if response.status_code != 200:
                    featured_image = None
            except Exception as e:
                log_step(f"Failed to verify featured image {featured_image}: {str(e)}")
                featured_image = None

        log_step(
            f"==============\n"
            f"link: {post_url}\n"
            f"content: {cleaned_html[:500]}{'...' if len(cleaned_html) > 500 else ''}\n"
            f"length: {len(cleaned_html)}\n"
            f"Featured Image: {featured_image}\n"
            f"Image URLs: {image_urls}\n"
            f"Video URLs: {video_urls}\n"
            f"=============="
        )

        return cleaned_html, featured_image

    except Exception as e:
        log_step(f"Error fetching content from {post_url}: {str(e)}")
        return '', ''