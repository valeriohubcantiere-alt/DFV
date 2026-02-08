import os

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.dirname(SERVICE_DIR)
PATH_PREZZIARI = os.path.join(DIR, "Prezziari")
OUTPUT_DIR = os.path.join(DIR, "output")

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


