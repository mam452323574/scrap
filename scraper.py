import requests
from bs4 import BeautifulSoup
import time
import json
import logging
import datetime
from db import Database
from urllib.parse import urljoin, parse_qs, urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Scraper:
    def __init__(self, config_path='config.json', stop_event=None):
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.base_url = self.config['base_url']
        self.delay = self.config['delay']
        self.db = Database(self.config['db_path'])
        self.db.connect()

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.config['user_agent'],
            'Referer': f"{self.base_url}/forums",
            'X-Requested-With': 'XMLHttpRequest'
        })
        self.stop_event = stop_event

    def should_stop(self):
        return self.stop_event and self.stop_event.is_set()

    def get_soup(self, url, params=None):
        retries = 0
        backoff = 5
        while retries <= self.config.get('max_retries', 3):
            try:
                response = self.session.get(url, params=params, timeout=self.config['timeout'])
                if response.status_code == 200:
                    return BeautifulSoup(response.content, 'html.parser')
                elif response.status_code in [429, 502, 503, 504]:
                    logger.warning(f"Server error {response.status_code} for {url}. Retrying in {backoff}s...")
                    time.sleep(backoff)
                    backoff *= 2
                    retries += 1
                else:
                    logger.error(f"Failed to fetch {url}: Status {response.status_code}")
                    return None
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                time.sleep(backoff)
                backoff *= 2
                retries += 1
            finally:
                if retries == 0: # Only sleep the regular delay if success
                    time.sleep(self.delay)
        return None

    def discover_sections(self):
        """Discovers sub-sections from the main forum IDs."""
        logger.info("Starting section discovery...")
        main_ids = self.config['main_section_ids']

        for section_id in main_ids:
            logger.info(f"Checking main section ID: {section_id}")
            # Add the main section itself if not exists (though we don't have a URL for it other than the ajax one)
            # We can construct a dummy URL or just use the ID.
            # But the scraper relies on URLs.
            # The main page has these sections.
            # Let's just focus on sub-sections returned by AJAX.

            ajax_url = f"{self.base_url}/forum-ajax"
            params = {'f': section_id, 'c': 0, 's': ''}

            soup = self.get_soup(ajax_url, params=params)
            if not soup:
                continue

            # Find sub-sections
            # Look for links like section?f=...&s=...
            # Structure: <a class="cadre-section-titre-mini lien-blanc" href="section?f=6&s=102" ...>

            links = soup.find_all('a', href=True)
            count = 0
            for link in links:
                href = link['href']
                if 'section?f=' in href and '&s=' in href:
                    full_url = urljoin(self.base_url, href)
                    name = link.get_text(strip=True)
                    logger.info(f"Found section: {name} ({href})")
                    self.db.add_section(full_url, name, parent_id=section_id)
                    count += 1
                elif 'topic?f=' in href:
                    # Some sections might list topics directly (e.g. Archives)
                    # If we find topics here, we should probably treat the main section ID as a crawlable section?
                    # But usually topics are inside a sub-section.
                    # Wait, if forum-ajax returns topics, it means we are already in a view that lists topics.
                    # We can add this 'main' section as a crawlable URL?
                    pass

            logger.info(f"Found {count} sub-sections for ID {section_id}")

    def crawl_sections(self):
        """Iterates through all discovered sections and finds topics."""
        sections = self.db.get_unscraped_sections() # Returns [(id, url), ...]
        logger.info(f"Found {len(sections)} unscraped sections.")

        for section_id, url in sections:
            logger.info(f"Crawling section: {url}")
            self._crawl_section_pages(section_id, url)
            self.db.mark_section_scraped(section_id)

    def _crawl_section_pages(self, section_id, url):
        page = 1
        while True:
            logger.info(f"  Scanning page {page} of section...")
            soup = self.get_soup(url, params={'p': page})
            if not soup:
                break

            # Extract topics
            # <a class="element-sujet lien-blanc" href="topic?f=6&t=850791">
            topic_links = soup.find_all('a', class_='element-sujet')
            found_topics = 0
            for link in topic_links:
                href = link.get('href')
                if href and 'topic?f=' in href:
                    # Check if it's the title link (usually contains 'cadre-sujet-titre')
                    if link.find('span', class_='cadre-sujet-titre-mini') or link.find('span', class_='cadre-sujet-titre'):
                        full_topic_url = urljoin(self.base_url, href)
                        # Remove fragment/anchor if any
                        if '#' in full_topic_url:
                            full_topic_url = full_topic_url.split('#')[0]

                        title = link.get_text(strip=True)
                        self.db.add_topic(full_topic_url, title, section_id)
                        found_topics += 1

            if found_topics == 0 and page > 1:
                logger.info("  No topics found on this page, stopping pagination.")
                break

            # Check for next page
            # <a class="btn btn-inverse " href="section?f=6&s=102&p=2">&rsaquo;</a>
            # Or check max page input
            pagination_input = soup.find('input', {'name': 'p', 'class': 'input-pagination'})
            if pagination_input:
                max_page = int(pagination_input.get('max', 1))
                if page >= max_page:
                    break
            else:
                # Single page
                break

            page += 1

    def crawl_topics(self):
        """Iterates through unscraped topics and extracts posts."""
        # Get topics that need scraping
        # We can fetch them in batches to avoid huge memory usage
        while True:
            # Replaced limiting 'scraped=0' with scraping logic inside loop to support delta/resume properly?
            # Actually, for resuming, scraped=0 is fine.
            # But what if we want to update? We might want to reset scraped=0 for all topics occasionally.
            # For now, let's stick to scraping unscraped ones.
            topics = self.db.cursor.execute('SELECT id, url, last_scraped_page FROM topics WHERE scraped=0 LIMIT 100').fetchall()
            if not topics:
                break

            logger.info(f"Processing batch of {len(topics)} topics...")
            for topic_id, url, last_page in topics:
                if self.should_stop():
                    logger.info("Scraping stopped by user.")
                    return

                logger.info(f"Crawling topic: {url}")
                if not self._crawl_topic_pages(topic_id, url, last_page):
                    # If scraping failed entirely, we might want to skip or retry later
                    pass

    def _crawl_topic_pages(self, topic_id, url, start_page):
        page = start_page if start_page > 0 else 1
        total_pages = 1

        if self.should_stop():
            return False

        # First visit to get max pages
        soup = self.get_soup(url, params={'p': page})
        if not soup:
            logger.error(f"Failed to load topic {url}")
            # Mark as failed (2)
            self.db.update_topic_scraped(topic_id, 0, 1, 2)
            return False

        pagination_input = soup.find('input', {'name': 'p', 'class': 'input-pagination'})
        if pagination_input:
            total_pages = int(pagination_input.get('max', 1))

        # Update topic total pages
        self.db.update_topic_scraped(topic_id, page, total_pages, 0) # Not fully scraped yet

        while page <= total_pages:
            if self.should_stop():
                logger.info("Scraping stopped by user (during topic).")
                return False

            if page > 1: # We already have soup for page 1 (or start_page)
                soup = self.get_soup(url, params={'p': page})
                if not soup:
                    logger.error(f"Failed to load page {page} of topic {url}")
                    # If we fail mid-way, we stop but record progress
                    return False

            logger.info(f"  Scraping page {page}/{total_pages}...")

            # Extract posts
            # Structure: <div id="m..." class="cadre cadre-relief cadre-message ltr ">
            posts_divs = soup.find_all('div', class_='cadre-message')
            if not posts_divs and page <= total_pages:
                 # Sometimes empty page if deleted content?
                 logger.warning(f"  No posts found on page {page}")

            for div in posts_divs:
                try:
                    # Post ID
                    # <a class="numero-message" href="...#m17">#17</a>
                    anchor = div.find('a', class_='numero-message')
                    post_ref = anchor['href'].split('#')[-1] if anchor else "unknown"

                    # User
                    # <span class="element-bouton-profil bouton-profil-nom ...">...User...</span>
                    # Or inside the dropdown menu <li class="nav-header">...User#Tag...</li>
                    user_elem = div.find('li', class_='nav-header')
                    if user_elem:
                        user = user_elem.get_text(strip=True)
                    else:
                        # Fallback
                        user_span = div.find('span', class_='bouton-profil-nom')
                        user = user_span.get_text(strip=True) if user_span else "Unknown"

                    # Date
                    # <span class="date-ms hidden" data-afficher-secondes="false">1497154920000</span>
                    date_span = div.find('span', class_='date-ms')
                    if date_span:
                        timestamp = int(date_span.get_text(strip=True))
                        # Convert to string (optional, usually handled by exporter)
                        date_str = datetime.datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        timestamp = 0
                        date_str = ""

                    # Content
                    # <div class="cadre-message-message">...</div>
                    content_div = div.find('div', class_='cadre-message-message')
                    content = content_div.get_text("\n", strip=True) if content_div else ""

                    self.db.add_post(post_ref, topic_id, user, content, timestamp, date_str)

                except Exception as e:
                    logger.error(f"Error parsing post in {url}: {e}")

            # Update progress
            self.db.update_topic_scraped(topic_id, page, total_pages, 0)
            page += 1

        # Mark topic as fully scraped
        self.db.update_topic_scraped(topic_id, total_pages, total_pages, 1)
        return True

if __name__ == '__main__':
    scraper = Scraper()
    scraper.discover_sections()
    scraper.crawl_sections()
    scraper.crawl_topics()
