import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import logging
import sys
from scraper import Scraper
from exporter import Exporter

class TextHandler(logging.Handler):
    """This class allows you to log to a Tkinter Text or ScrolledText widget"""
    def __init__(self, text):
        # run the regular Handler __init__
        logging.Handler.__init__(self)
        # Store a reference to the Text it will log to
        self.text = text

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text.configure(state='normal')
            self.text.insert(tk.END, msg + '\n')
            self.text.configure(state='disabled')
            # Autoscroll to the bottom
            self.text.yview(tk.END)
        # This is necessary because we can't modify the Text from other threads
        try:
            self.text.after(0, append)
        except Exception:
            pass # Window likely closed

class ScraperUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Atelier801 Forum Scraper")
        self.root.geometry("800x600")
        self.root.configure(padx=20, pady=20)

        # Variable d'état pour le scraping
        self.is_scraping = False
        self.stop_event = threading.Event()

        # --- LIGNE 1 : Configuration du délai ---
        frame_config = tk.Frame(root)
        frame_config.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame_config, text="Délai entre chaque page (secondes) :", font=("Arial", 10)).pack(side=tk.LEFT)
        self.delay_var = tk.DoubleVar(value=1.5)
        delay_entry = tk.Entry(frame_config, textvariable=self.delay_var, width=5)
        delay_entry.pack(side=tk.LEFT, padx=10)

        # --- LIGNE 2 : Boutons d'action ---
        frame_buttons = tk.Frame(root)
        frame_buttons.pack(fill=tk.X, pady=(0, 15))

        self.btn_discover = tk.Button(frame_buttons, text="🔍 Découvrir Sections", bg="#FF9800", fg="white", width=20, command=self.start_discovery)
        self.btn_discover.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_start = tk.Button(frame_buttons, text="▶ Démarrer Scraping", bg="#4CAF50", fg="white", width=20, command=self.start_scraping)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_stop = tk.Button(frame_buttons, text="⏸ Stop", bg="#f44336", fg="white", width=15, state=tk.DISABLED, command=self.stop_scraping)
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_export = tk.Button(frame_buttons, text="📁 Exporter Données", bg="#2196F3", fg="white", width=20, command=self.export_data)
        self.btn_export.pack(side=tk.RIGHT)

        # --- LIGNE 3 : Zone de logs (Console) ---
        tk.Label(root, text="Journal d'activité :", font=("Arial", 10, "bold")).pack(anchor=tk.W)

        self.log_area = scrolledtext.ScrolledText(root, height=20, width=90, font=("Consolas", 9), bg="#f5f5f5")
        self.log_area.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self.log_area.configure(state='disabled')

        # Setup Logging
        text_handler = TextHandler(self.log_area)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        text_handler.setFormatter(formatter)

        # Get the root logger and add handler
        logger = logging.getLogger()
        logger.addHandler(text_handler)
        logger.setLevel(logging.INFO) # Ensure level captures INFO

        logging.info("Prêt. En attente du lancement...")

    def discovery_process(self):
        try:
            scraper = Scraper(stop_event=self.stop_event)
            scraper.delay = self.delay_var.get()
            scraper.discover_sections()
            logging.info("Découverte terminée.")
        except Exception as e:
            logging.error(f"Erreur lors de la découverte : {e}")
        finally:
            self.reset_ui_state()

    def start_discovery(self):
        self.stop_event.clear()
        self.set_ui_busy()
        threading.Thread(target=self.discovery_process, daemon=True).start()

    def scraping_process(self):
        try:
            scraper = Scraper(stop_event=self.stop_event)
            scraper.delay = self.delay_var.get()

            # Check if sections exist
            if scraper.db.get_topics_count() == 0 and len(scraper.db.get_unscraped_sections()) == 0:
                logging.warning("Aucune section trouvée. Lancement de la découverte automatique...")
                scraper.discover_sections()

            logging.info("Démarrage du scraping des sections...")
            # We need to make the scraper stoppable.
            # Since scraper loops are blocking, we can't easily inject the stop event inside scraper methods
            # unless we modify Scraper class to accept a stop_event or check a flag.
            # Ideally, we modify scraper.py to check `self.should_stop` flag.

            # Hack: We can just let it run one batch and check loop condition?
            # Or modify Scraper to be more interactive.
            # For now, let's run the standard methods. Stopping might not be instant.

            scraper.crawl_sections()
            scraper.crawl_topics()

            logging.info("Scraping terminé (ou boucle finie).")

        except Exception as e:
            logging.error(f"Erreur lors du scraping : {e}")
        finally:
            self.reset_ui_state()

    def start_scraping(self):
        if not self.is_scraping:
            self.is_scraping = True
            self.stop_event.clear()
            self.set_ui_busy()
            self.btn_stop.config(state=tk.NORMAL)

            threading.Thread(target=self.scraping_process, daemon=True).start()

    def stop_scraping(self):
        logging.info("Demande d'arrêt... (L'arrêt effectif peut prendre quelques secondes)")
        self.stop_event.set()

    def export_data(self):
        """Lance ta fonction d'exportation depuis SQLite vers les fichiers TXT."""
        logging.info("Début de l'exportation des données par utilisateur...")
        try:
            exporter = Exporter()
            exporter.run()
            messagebox.showinfo("Exportation", "L'exportation des fichiers utilisateurs est terminée !")
            logging.info("Exportation réussie dans le dossier de sortie.")
        except Exception as e:
            logging.error(f"Erreur export : {e}")

    def set_ui_busy(self):
        self.btn_start.config(state=tk.DISABLED)
        self.btn_discover.config(state=tk.DISABLED)
        self.btn_export.config(state=tk.DISABLED)

    def reset_ui_state(self):
        self.is_scraping = False
        self.root.after(0, lambda: [
            self.btn_start.config(state=tk.NORMAL),
            self.btn_discover.config(state=tk.NORMAL),
            self.btn_export.config(state=tk.NORMAL),
            self.btn_stop.config(state=tk.DISABLED)
        ])

if __name__ == "__main__":
    root = tk.Tk()
    app = ScraperUI(root)
    root.mainloop()
