import os
import json
import logging
import sqlite3
import re
from db import Database

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Exporter:
    def __init__(self, config_path='config.json'):
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.db_path = self.config['db_path']
        self.output_dir = self.config['output_dir']

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def sanitize_filename(self, filename):
        # Remove invalid characters for filenames
        return re.sub(r'[<>:"/\\|?*]', '_', filename)

    def get_users(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT user FROM posts")
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        return users

    def export_user(self, user):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT p.date_str, t.title, t.url, p.content
            FROM posts p
            JOIN topics t ON p.topic_id = t.id
            WHERE p.user = ?
            ORDER BY p.date_timestamp ASC
        """

        cursor.execute(query, (user,))
        posts = cursor.fetchall()
        conn.close()

        if not posts:
            return

        filename = self.sanitize_filename(user) + ".txt"
        filepath = os.path.join(self.output_dir, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Archive des messages de : {user}\n")
                f.write(f"Nombre de messages : {len(posts)}\n")
                f.write("="*50 + "\n\n")

                for date, title, url, content in posts:
                    f.write(f"Date : {date}\n")
                    f.write(f"Sujet : {title}\n")
                    f.write(f"Lien : {url}\n")
                    f.write("-" * 20 + "\n")
                    f.write(content + "\n")
                    f.write("\n" + "="*50 + "\n\n")

            logger.info(f"Exported {len(posts)} messages for {user} to {filepath}")
        except Exception as e:
            logger.error(f"Failed to export {user}: {e}")

    def run(self):
        logger.info("Starting export...")
        users = self.get_users()
        logger.info(f"Found {len(users)} users to export.")

        for user in users:
            self.export_user(user)

        logger.info("Export complete.")

if __name__ == "__main__":
    exporter = Exporter()
    exporter.run()
