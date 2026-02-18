# Atelier 801 Forum Scraper

Un outil pour archiver intégralement le forum Atelier 801 (Transformice, Bouboum, etc.).

## Fonctionnalités

*   **Découverte automatique** des sections et sous-sections.
*   **Aspiration (Scraping)** récursive des sujets et des messages.
*   **Gestion des interruptions** : le script reprend là où il s'est arrêté (grâce à la base de données locale).
*   **Export** : génère un fichier texte par utilisateur contenant tous ses messages classés par date.
*   **Respectueux** : délai configurable entre les requêtes pour ne pas surcharger le serveur.

## Installation

1.  Installer Python 3.
2.  Installer les dépendances :
    ```bash
    pip install -r requirements.txt
    ```

## Utilisation

Le script s'utilise en ligne de commande via `main.py`.

### 1. Découverte (Première fois)
Lancez cette commande pour identifier toutes les sections du forum :
```bash
python main.py --action discover
```

### 2. Aspiration (Le gros du travail)
Lancez cette commande pour commencer à télécharger les messages.
Vous pouvez arrêter le script (Ctrl+C) et le relancer plus tard, il reprendra automatiquement.
```bash
python main.py --action scrape
```
*Note : Cette étape peut prendre beaucoup de temps selon la taille du forum.*

### 3. Export (Une fois fini)
Une fois l'aspiration terminée (ou même pendant), vous pouvez générer les fichiers par utilisateur :
```bash
python main.py --action export
```
Les fichiers seront créés dans le dossier `Archives_Atelier801`.

### Tout en un
Pour tout enchaîner (déconseillé si vous voulez surveiller) :
```bash
python main.py --action all
```

## Configuration

Vous pouvez modifier `config.json` pour ajuster :
*   `delay` : temps d'attente entre deux pages (en secondes).
*   `timeout` : temps d'attente max pour une réponse.
*   `db_path` : nom de la base de données.
