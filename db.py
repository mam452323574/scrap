import sqlite3
import json
import os

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Create table for sections
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY,
            url TEXT UNIQUE,
            name TEXT,
            parent_id INTEGER,
            scraped BOOLEAN DEFAULT 0
        )
        ''')

        # Create table for topics
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY,
            url TEXT UNIQUE,
            title TEXT,
            section_id INTEGER,
            last_scraped_page INTEGER DEFAULT 0,
            total_pages INTEGER DEFAULT 1,
            scraped BOOLEAN DEFAULT 0,
            FOREIGN KEY(section_id) REFERENCES sections(id)
        )
        ''')

        # Create table for posts
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            post_id TEXT UNIQUE,
            topic_id INTEGER,
            user TEXT,
            content TEXT,
            date_timestamp INTEGER,
            date_str TEXT,
            FOREIGN KEY(topic_id) REFERENCES topics(id)
        )
        ''')
        self.conn.commit()

    def add_section(self, url, name, parent_id=None):
        try:
            self.cursor.execute('INSERT OR IGNORE INTO sections (url, name, parent_id) VALUES (?, ?, ?)', (url, name, parent_id))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error adding section: {e}")
            return None

    def add_topic(self, url, title, section_id):
        try:
            self.cursor.execute('INSERT OR IGNORE INTO topics (url, title, section_id) VALUES (?, ?, ?)', (url, title, section_id))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error adding topic: {e}")
            return None

    def update_topic_scraped(self, topic_id, last_page, total_pages, scraped):
        try:
            self.cursor.execute('UPDATE topics SET last_scraped_page=?, total_pages=?, scraped=? WHERE id=?', (last_page, total_pages, scraped, topic_id))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error updating topic: {e}")

    def add_post(self, post_id, topic_id, user, content, date_timestamp, date_str):
        try:
            self.cursor.execute('''
            INSERT OR IGNORE INTO posts (post_id, topic_id, user, content, date_timestamp, date_str)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (post_id, topic_id, user, content, date_timestamp, date_str))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error adding post: {e}")

    def get_unscraped_sections(self):
        self.cursor.execute('SELECT id, url FROM sections WHERE scraped=0')
        return self.cursor.fetchall()

    def get_unscraped_topics(self):
        self.cursor.execute('SELECT id, url, last_scraped_page FROM topics WHERE scraped=0')
        return self.cursor.fetchall()

    def mark_section_scraped(self, section_id):
        self.cursor.execute('UPDATE sections SET scraped=1 WHERE id=?', (section_id,))
        self.conn.commit()

    def get_topics_count(self):
        self.cursor.execute('SELECT COUNT(*) FROM topics')
        return self.cursor.fetchone()[0]

    def get_posts_count(self):
        self.cursor.execute('SELECT COUNT(*) FROM posts')
        return self.cursor.fetchone()[0]

    def close(self):
        if self.conn:
            self.conn.close()
