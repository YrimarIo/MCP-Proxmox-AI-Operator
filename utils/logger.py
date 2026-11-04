import logging
import os

# Den Pfad absolut machen, damit die Datei IMMER im Projekt-Hauptordner landet
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, "proxmox_ai.log")

def setup_logger():
    # Wir holen uns den Logger "ProxmoxAI"
    logger = logging.getLogger("ProxmoxAI")
    
    # Verhindern, dass Logs mehrfach ausgegeben werden, falls setup_logger 
    # mehrfach aufgerufen wird
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # Datei-Ausgabe
        file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Konsolen-Ausgabe (damit du es auch im Terminal siehst)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        
    return logger

# WICHTIG: Hier wird das 'log' Objekt erstellt, das alle anderen importieren
log = setup_logger()