from lxml import etree
from datetime import datetime
from log import log_step
from bs4 import BeautifulSoup
import re
import mimetypes
import os
import requests

# Ensure feed.xml is written in the current folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FEED_FILE = os.path.join(BASE_DIR, "feed.xml")

def generate_rss_feed(items, output_file=FEED_FILE):
    rss = etree.Element("rss", version="2.0", nsmap={
        "dc": "http://purl.org/dc/elements/1.1/",
        "content": "http://purl.org/rss/1.0/modules/content/",
        "wp": "http://wordpress.org/export/1.2/"
    })
    channel = etree.SubElement(rss, "channel")

    etree.SubElement(channel, "title").text = "Ggoorr RSS Feed"
    etree.SubElement(channel, "link").text = "https://ggoorr.net/"
    etree.SubElement(channel, "description").text = "RSS feed generated from ggoorr.net"
    # Convert 10:44 AM +06 (May 20, 2025) to UTC: 04:44 AM GMT
    etree.SubElement(channel, "lastBuildDate").text = "Tue, 20 May 2025 04:44:00 GMT"

    seen_guids = set()

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            log_step(f"Skipping invalid item at index {idx}: {item}")
            continue

        item_elem = etree.SubElement(channel, "item")

        # Determine item type
        item_type = item.get('type', 'article')

        if item_type == 'article':
            # Handle article items
            title = (item.get('title') or '').strip() or f"Untitled Post {idx + 1}"
            link = (item.get('link') or '').strip() or f"https://ggoorr.net/placeholder/{idx + 1}"
            content = (item.get('content') or '').strip()
            featured_image = (item.get('featured_image') or '').strip()

        else:
            # Handle video items
            title = f"Video Item {idx + 1}"  # Default title for videos
            link = item.get('src') or f"https://ggoorr.net/video/{idx + 1}"
            # Construct video tag with all specified attributes
            video_attrs = {
                'src': item.get('src', ''),
                'poster': item.get('poster', ''),
                'data-file-srl': item.get('data-file-srl', ''),
                '__idm_id__': item.get('__idm_id__', ''),
                'id': item.get('id', ''),
                'playsinline': item.get('playsinline', '')
            }
            content = f"<video {' '.join(f'{k}=\"{v}\"' for k, v in video_attrs.items() if v)}></video>"


        guid = link
        if guid in seen_guids:
            guid = f"{link}-{idx}"
            log_step(f"Duplicate GUID detected for link {link}, using {guid}")
        seen_guids.add(guid)

        log_step(f"Raw content for item {idx + 1}: {content[:500]}{'...' if len(content) > 500 else ''}")
        log_step(f"Featured image for item {idx + 1}: {featured_image}")

        if item_type == 'video':
            log_step(f"Video attributes for item {idx + 1}: {video_attrs}")

        modified_content = modify_content(content)

        soup = BeautifulSoup(modified_content, 'html.parser')
        plain_text = soup.get_text(strip=True)[:200]

        video_tags = soup.find_all('video')
        for video in video_tags:
            src = video.get('src', '')
            if src:
                try:
                    response = requests.head(src, timeout=5)
                    log_step(f"Video URL {src} status: {response.status_code}, Content-Type: {response.headers.get('Content-Type')}")
                    if response.status_code != 200 or 'video/' not in response.headers.get('Content-Type', ''):
                        log_step(f"Warning: Video URL {src} may not be accessible or is not a video")
                except Exception as e:
                    log_step(f"Error validating video URL {src}: {str(e)}")

        log_step(f"Video tags for item {idx + 1}: {[str(v) for v in video_tags]}")

        log_step(
            f"==============\n"
            f"Item {idx + 1} ({item_type}):\n"
            f"title: {title}\n"
            f"link: {link}\n"
            f"guid: {guid}\n"
            f"content: {modified_content[:500]}{'...' if len(modified_content) > 500 else ''}\n"
            f"length: {len(modified_content)}\n"
            f"plain_text: {plain_text}\n"
            f"featured_image: {featured_image}\n"

            f"=============="
        )

        etree.SubElement(item_elem, "title").text = title
        etree.SubElement(item_elem, "link").text = link


        description_elem = etree.SubElement(item_elem, "description")
        description_elem.text = plain_text or ""

        content_elem = etree.SubElement(item_elem, "{http://purl.org/rss/1.0/modules/content/}encoded")
        content_elem.text = etree.CDATA(modified_content) if modified_content else ""

        if featured_image and featured_image.startswith('http'):
            mime_type, _ = mimetypes.guess_type(featured_image)
            if not mime_type:
                mime_type = 'image/jpeg'
            etree.SubElement(item_elem, "enclosure", url=featured_image, type=mime_type, length="0")
            postmeta_elem = etree.SubElement(item_elem, "{http://wordpress.org/export/1.2/}postmeta")
            etree.SubElement(postmeta_elem, "meta_key").text = "_thumbnail_id"
            etree.SubElement(postmeta_elem, "meta_value").text = featured_image

        # Handle video-specific attributes
        if item_type == 'video':
            # Add video src as an enclosure
            if item.get('src'):
                mime_type, _ = mimetypes.guess_type(item['src'])
                if not mime_type:
                    mime_type = 'video/mp4'  # Default for videos
                etree.SubElement(item_elem, "enclosure", url=item['src'], type=mime_type, length="0")

            # Add video attributes as WordPress metadata
            for attr in ['data-file-srl', '__idm_id__', 'id', 'playsinline']:
                if item.get(attr):
                    postmeta_elem = etree.SubElement(item_elem, "{http://wordpress.org/export/1.2/}postmeta")
                    etree.SubElement(postmeta_elem, "meta_key").text = f"video_{attr}"
                    etree.SubElement(postmeta_elem, "meta_value").text = item[attr]

    try:
        tree = etree.ElementTree(rss)
        tree.write(output_file, encoding="utf-8", xml_declaration=True, pretty_print=True)
        log_step(f"RSS feed written to {output_file}, total items: {len(items)}")
    except Exception as e:
        log_step(f"Failed to write RSS feed: {str(e)}")

def modify_content(content):
    soup = BeautifulSoup(content, 'html.parser')
    modified_elements = []

    youtube_regex = r'(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([a-zA-Z0-9_-]{11})'
    vimeo_regex = r'(?:vimeo\.com/(?:video/|embed/)?)(\d+)'

    for tag in soup.find_all(['p', 'img', 'video', 'iframe', 'a']):
        if tag.name == 'p':
            if tag.get_text(strip=True):
                modified_elements.append(str(tag))
        elif tag.name == 'img':
            img_url = tag.get('src', '')
            if img_url:
                img_attrs = tag.attrs.copy()
                img_tag = f"<img {' '.join(f'{k}=\"{v}\"' for k, v in img_attrs.items() if v is not None)}/>"
                modified_elements.append(f'</br>{img_tag}</br>')
            else:
                log_step(f"Skipping img tag with no src: {str(tag)}")
        elif tag.name == 'video':
            video_url = tag.get('src', '')
            if video_url:
                log_step(f"Input video tag attributes: {tag.attrs}")
                video_attrs = tag.attrs.copy()
                attr_strings = []
                for k, v in video_attrs.items():
                    if v is None:
                        continue
                    elif v == '' or v is True:
                        attr_strings.append(k)
                    else:
                        attr_strings.append(f'{k}="{v}"')
                video_tag = f"<video {' '.join(attr_strings)}></video>"
                modified_elements.append(f'</br>{video_tag}</br>')
                log_step(f"Output video tag: {video_tag}")
            else:
                log_step(f"Skipping video tag with no src: {str(tag)}")
        elif tag.name in ['iframe', 'a']:
            url = tag.get('src') if tag.name == 'iframe' else tag.get('href', '')
            if url:
                youtube_match = re.search(youtube_regex, url)
                vimeo_match = re.search(vimeo_regex, url)
                if youtube_match:
                    video_id = youtube_match.group(1)
                    iframe_tag = (
                        f'</br><iframe width="360px" height="auto" '
                        f'src="https://www.youtube.com/embed/{video_id}" '
                        f'frameborder="0" allowfullscreen></iframe></br>'
                    )
                    modified_elements.append(iframe_tag)
                elif vimeo_match:
                    video_id = vimeo_match.group(1)
                    iframe_tag = (
                        f'</br><iframe width="360px" height="auto" '
                        f'src="https://player.vimeo.com/video/{video_id}" '
                        f'frameborder="0" allowfullscreen></iframe></br>'
                    )
                    modified_elements.append(iframe_tag)
                else:
                    modified_elements.append(f'</br><a href="{url}">Watch Video</a></br>')

    return ''.join(modified_elements)