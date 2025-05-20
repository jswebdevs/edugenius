from get_link_and_title import get_links_and_titles
from get_full_content import get_full_content
from feed_generation import generate_rss_feed
from log import log_step



BASE_URL = "https://www.bbc.com"
TARGET_URL = BASE_URL + "/news/education?page={page_number}"


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36"
}
START_PAGE = 1
END_PAGE = 42

def main():
    all_posts = []

    for page_num in range(START_PAGE, END_PAGE + 1):
        url = TARGET_URL.format(page_number=page_num)
        log_step(f"Scraping page {page_num}: {url}")
        try:
            posts = get_links_and_titles(url, BASE_URL, HEADERS)
        except Exception as e:
            log_step(f"Failed to scrape page {page_num}: {str(e)}")
            continue

        for post in posts:
            try:
                content, featured_image = get_full_content(post['link'], HEADERS)
                # Validate post
                if not post.get('title') or not post.get('link'):
                    log_step(f"Skipping invalid post: {post}")
                    continue
                post['content'] = content
                post['featured_image'] = featured_image
                # Ensure categories is a list
                post['categories'] = post.get('categories', [])
                # Preprocess link to use /thisthat/ format
                post['link'] = post['link'].replace('/main/', '/thisthat/').replace('/page/1', '')
                log_step(f"Added content for: {post['title']} (link: {post['link']}, content length: {len(content)}, categories: {post['categories']})")
                all_posts.append(post)
            except Exception as e:
                log_step(f"Failed to process post {post.get('title', 'unknown')}: {str(e)}")
                continue

    log_step(f"Total posts collected: {len(all_posts)}")
    
    # Debug logging for items
    print(f"Total items to process: {len(all_posts)}")
    for idx, item in enumerate(all_posts):
        print(f"Item {idx + 1}: {item}")

    if all_posts:
        generate_rss_feed(all_posts)
    else:
        log_step("No posts to generate RSS feed")

if __name__ == "__main__":
    main()