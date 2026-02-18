import argparse
import sys
import logging
import json
import os
from scraper import Scraper
from exporter import Exporter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Atelier 801 Forum Scraper")
    parser.add_argument('--action', choices=['discover', 'scrape', 'export', 'all'], required=True, help="Action to perform")
    parser.add_argument('--config', default='config.json', help="Path to config file")

    args = parser.parse_args()

    # Load config
    if not os.path.exists(args.config):
        logger.error(f"Config file not found: {args.config}")
        sys.exit(1)

    if args.action == 'discover':
        scraper = Scraper(args.config)
        scraper.discover_sections()

    elif args.action == 'scrape':
        scraper = Scraper(args.config)
        # If no sections, maybe discover first?
        # But user might want to run discover separately.
        # We can check if sections exist.
        if scraper.db.cursor.execute('SELECT COUNT(*) FROM sections').fetchone()[0] == 0:
            logger.info("No sections found in DB. Running discovery first...")
            scraper.discover_sections()

        scraper.crawl_sections()
        scraper.crawl_topics()

    elif args.action == 'export':
        exporter = Exporter(args.config)
        exporter.run()

    elif args.action == 'all':
        scraper = Scraper(args.config)
        logger.info("Starting FULL process...")
        scraper.discover_sections()
        scraper.crawl_sections()
        scraper.crawl_topics()

        exporter = Exporter(args.config)
        exporter.run()

if __name__ == "__main__":
    main()
