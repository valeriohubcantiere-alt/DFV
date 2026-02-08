import os
import re
import csv

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.dirname(SERVICE_DIR)
PATH_PREZZIARI = os.path.join(DIR, "Prezziari")
OUTPUT_DIR = os.path.join(DIR, "output")


def pulisci_codice(codice: str) -> str:
    """
    Pulisce un codice tariffario per il confronto (xcode).
    Rimuove spazi, normalizza in uppercase.
    """
    if not codice:
        return ""
    c = codice.strip()
    c = re.sub(r'\s+', '', c)
    c = c.upper()
    return c


def _trova_colonna(headers, possibili_nomi):
    """Trova una colonna tra i possibili nomi (case-insensitive, match parziale)."""
    if not headers:
        return None
    for h in headers:
        h_lower = h.lower().strip()
        for nome in possibili_nomi:
            if nome in h_lower:
                return h
    return None


def carica_tariffario_csv(csv_path: str) -> dict:
    """
    Carica il tariffario da un file CSV.
    Ritorna un dizionario: {xcode: {codice: str, descrizione: str, unita: str, prezzo: float}}
    """
    tariffario = {}

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(f, dialect=dialect)
        headers = reader.fieldnames

        col_codice = _trova_colonna(headers, ['codice', 'code', 'tariffa', 'cod'])
        col_desc = _trova_colonna(headers, ['descrizione', 'description', 'desc', 'desestesa'])
        col_unita = _trova_colonna(headers, ['unita', 'unità', 'um', 'u.m.', 'unit', 'udm'])
        col_prezzo = _trova_colonna(headers, ['prezzo', 'price', 'prezzo1', 'prezzo_unitario', 'costo'])

        if not col_codice:
            raise ValueError(f"Colonna codice non trovata. Colonne disponibili: {headers}")

        for row in reader:
            codice_raw = row.get(col_codice, '')
            if not codice_raw or not codice_raw.strip():
                continue

            xcode = pulisci_codice(codice_raw)
            descrizione = row.get(col_desc, '') if col_desc else ''
            unita = row.get(col_unita, '') if col_unita else ''
            prezzo_str = row.get(col_prezzo, '0') if col_prezzo else '0'

            try:
                prezzo = float(prezzo_str.replace(',', '.').strip())
            except (ValueError, AttributeError):
                prezzo = 0.0

            tariffario[xcode] = {
                'codice': codice_raw.strip(),
                'descrizione': descrizione.strip(),
                'unita': unita.strip(),
                'prezzo': prezzo,
            }

    return tariffario


def lista_regioni() -> list[str]:
    """
    Legge la cartella Prezziari e restituisce la lista delle regioni disponibili
    (sottocartelle presenti).
    """
    if not os.path.exists(PATH_PREZZIARI):
        raise FileNotFoundError(f"Cartella Prezziari non trovata: {PATH_PREZZIARI}")

    regioni = [
        nome for nome in sorted(os.listdir(PATH_PREZZIARI))
        if os.path.isdir(os.path.join(PATH_PREZZIARI, nome))
    ]

    if not regioni:
        raise ValueError("Nessuna regione trovata nella cartella Prezziari")

    return regioni


def carica_tariffario_regione(nome_regione: str) -> dict:
    """
    Legge tutti i file XML di una regione ed estrae le voci del prezziario.

    Ritorna un dizionario: {codice: {prezzo: float, descrizione: str}}
    """
    path_regione = os.path.join(PATH_PREZZIARI, nome_regione)

    if not os.path.exists(path_regione):
        raise FileNotFoundError(f"Regione non trovata: {path_regione}")

    files = os.listdir(path_regione)
    if not files:
        raise ValueError(f"Nessun file trovato per {nome_regione}")

    str_data = ""
    for file in files:
        file_path = os.path.join(path_regione, file)
        try:
            with open(file_path, "r", encoding="UTF-8") as f:
                str_data += f.read()
        except Exception as e:
            print(f"  [WARN] Impossibile leggere {file}: {e}")
            continue

    pattern = r'<DesEstesa>(.*?)</DesEstesa>.*?<Tariffa>(.*?)</Tariffa>.*?<Prezzo1>(.*?)</Prezzo1>'
    tariffario = {}

    for match in re.finditer(pattern, str_data, re.DOTALL):
        descrizione = match.group(1).strip()
        code = match.group(2).strip()
        prezzo = match.group(3).strip()
        try:
            tariffario[code] = {
                "prezzo": float(prezzo),
                "descrizione": descrizione,
            }
        except ValueError:
            continue

    return tariffario


