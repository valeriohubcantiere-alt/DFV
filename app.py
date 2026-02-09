import gradio as gr
import anthropic
import fitz  # PyMuPDF
from PIL import Image
from dotenv import load_dotenv
import os
import io
import re
import ast
import base64
import time

from prompt import PROMPT
from service.service_main import carica_tariffario_csv, pulisci_codice, normalizza_codice, trova_codice_simile


def log(msg):
    """Stampa un messaggio di log con timestamp."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Precaricamento del tariffario
TARIFFARIO_NAME = os.environ.get("TARIFFARIO_NAME", "Tariffario2026C")
TARIFFARIO_PATH = os.environ.get("TARIFFARIO_PATH", "./Tariffario2026C.csv")

if not os.path.exists(TARIFFARIO_PATH):
    raise FileNotFoundError(
        f"File tariffario non trovato: {TARIFFARIO_PATH}. "
        f"Verifica le variabili TARIFFARIO_NAME e TARIFFARIO_PATH nel file .env"
    )

log(f"Caricamento tariffario '{TARIFFARIO_NAME}' da {TARIFFARIO_PATH}...")
TARIFFARIO = carica_tariffario_csv(TARIFFARIO_PATH)
# Precomputa mappa normalizzata: {codice_normalizzato: chiave_xcode}
TARIFFARIO_NORM = {}
for xcode_key in TARIFFARIO:
    norm_key = normalizza_codice(xcode_key)
    if norm_key not in TARIFFARIO_NORM:
        TARIFFARIO_NORM[norm_key] = xcode_key
log(f"Tariffario '{TARIFFARIO_NAME}' caricato: {len(TARIFFARIO)} voci")


def img_to_base64(img):
    """Converte un'immagine PIL in stringa base64 PNG."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def parse_liste_da_testo(testo):
    """
    Estrae liste di tuple dal testo restituito da Claude.
    Aggrega le quantita' per codici che si normalizzano allo stesso valore,
    risolvendo inconsistenze tra pagine (underscore vs punti, ecc.).
    """
    matches = re.findall(r'\[.*?\]', testo, re.DOTALL)
    tutte = []
    for match in matches:
        try:
            data = ast.literal_eval(match)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, tuple) and len(item) == 2:
                        codice, quantita = item
                        if isinstance(codice, str) and isinstance(quantita, (int, float)):
                            tutte.append((codice.strip(), float(quantita)))
        except (ValueError, SyntaxError):
            continue

    # Aggrega per codice normalizzato: tiene il primo codice raw trovato
    # e somma le quantita' se lo stesso codice appare da pagine diverse
    aggregati = {}  # normalizzato -> (codice_raw, quantita_totale)
    for codice, quantita in tutte:
        chiave = normalizza_codice(codice)
        if chiave in aggregati:
            raw_esistente, qty_esistente = aggregati[chiave]
            # Se la quantita' e' identica, e' un duplicato da pagine sovrapposte
            if qty_esistente == quantita:
                continue
            # Altrimenti somma (casi di codice spezzato su piu' coppie di pagine)
            aggregati[chiave] = (raw_esistente, qty_esistente + quantita)
        else:
            aggregati[chiave] = (codice, quantita)

    risultato = [(raw, qty) for raw, qty in aggregati.values()]
    return sorted(risultato)


def estrai_codici_da_pdf(pdf_file, modello="claude-sonnet-4-5-20250929", dpi=200):
    """Estrae coppie (codice, quantità) dal PDF usando Claude."""
    log("=" * 60)
    log("INIZIO ELABORAZIONE PDF")
    log("=" * 60)

    log(f"Apertura PDF: {pdf_file}")
    doc = fitz.open(pdf_file)
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    immagini = []
    numero_pagine = len(doc)
    log(f"PDF aperto: {numero_pagine} pagine trovate")

    log("Conversione pagine in immagini...")
    for idx, page in enumerate(doc):
        num_pag = idx + 1
        log(f"  Lettura pagina {num_pag}/{numero_pagine}...")
        pix = page.get_pixmap(matrix=matrix)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        immagini.append(img)
    doc.close()
    log(f"Conversione completata: {numero_pagine} immagini generate ({dpi} DPI)")

    if numero_pagine < 2:
        log("ERRORE: il PDF deve avere almeno 2 pagine.")
        return [], "Il PDF deve avere almeno 2 pagine."

    risposte_raw = []
    coppie_totali = numero_pagine - 1

    log("-" * 60)
    log(f"ANALISI CODICI CON CLAUDE ({coppie_totali} coppie di pagine)")
    log("-" * 60)

    for i in range(coppie_totali):
        p1 = i + 1
        p2 = i + 2
        img_1 = immagini[i]
        img_2 = immagini[i + 1]

        log(f"  Invio coppia pagine {p1}-{p2} a Claude... [{i + 1}/{coppie_totali}]")

        content = [
            {"type": "text", "text": f"\n--- PAGINA {p1} ---"},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_to_base64(img_1),
                },
            },
            {"type": "text", "text": f"\n--- PAGINA {p2} ---"},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_to_base64(img_2),
                },
            },
        ]

        try:
            response = client.messages.create(
                model=modello,
                max_tokens=4096,
                system=PROMPT,
                messages=[{"role": "user", "content": content}],
            )
            testo_risposta = response.content[0].text
            risposte_raw.append(testo_risposta)
            # Conta voci estratte da questa coppia
            voci_coppia = len(re.findall(r'\(', testo_risposta.split('[')[-1])) if '[' in testo_risposta else 0
            log(f"  Risposta ricevuta per pagine {p1}-{p2} (~{voci_coppia} voci)")
        except Exception as e:
            log(f"  ERRORE pagine {p1}-{p2}: {e}")
            risposte_raw.append(f"ERRORE pagine {p1}-{p2}: {e}")

    log("-" * 60)
    log("AGGREGAZIONE RISULTATI")
    log("-" * 60)

    testo_completo = "\n".join(risposte_raw)
    lista_finale = parse_liste_da_testo(testo_completo)

    log(f"Voci estratte dopo aggregazione: {len(lista_finale)}")

    log_str = f"Pagine: {numero_pagine} | Coppie elaborate: {coppie_totali} | Voci estratte: {len(lista_finale)}"
    return lista_finale, log_str


def deduplica_risultati(risultati):
    """
    Rimuove doppioni dai risultati: per ogni codice tiene solo la voce
    con la quantità più alta.
    """
    log("-" * 60)
    log("DEDUPLICAZIONE RISULTATI")
    log("-" * 60)

    # Raggruppa per codice (colonna 0)
    per_codice = {}
    for riga in risultati:
        codice = riga[0]
        xcode = pulisci_codice(codice)
        if xcode in per_codice:
            esistente = per_codice[xcode]
            if riga[4] > esistente[4]:
                log(f"  Doppione trovato: {codice} — qty {esistente[4]} sostituita con {riga[4]}")
                per_codice[xcode] = riga
            else:
                log(f"  Doppione trovato: {codice} — qty {riga[4]} scartata (esiste già con qty {esistente[4]})")
        else:
            per_codice[xcode] = riga

    deduplicati = list(per_codice.values())
    rimossi = len(risultati) - len(deduplicati)
    if rimossi > 0:
        log(f"  Rimossi {rimossi} doppioni, mantenute {len(deduplicati)} voci")
    else:
        log("  Nessun doppione trovato")

    return deduplicati


def inserisci_voci_mancanti(risultati, non_trovati, tariffario, tariffario_norm):
    """
    Per i codici non trovati, prova un ulteriore tentativo di ricerca nel tariffario.
    Se trovati, li inserisce nei risultati copiando la descrizione dal tariffario,
    senza modificare le voci già inserite.
    """
    log("-" * 60)
    log("INSERIMENTO VOCI MANCANTI")
    log("-" * 60)

    if not non_trovati:
        log("  Nessuna voce mancante da inserire")
        return risultati, non_trovati

    # Codici già presenti nei risultati (per non duplicare)
    codici_presenti = set()
    for riga in risultati:
        codici_presenti.add(pulisci_codice(riga[0]))

    ancora_mancanti = []
    inseriti = 0

    for codice_pdf, quantita in non_trovati:
        xcode = pulisci_codice(codice_pdf)
        norm = normalizza_codice(xcode)

        # Controlla se il codice è già nei risultati
        if xcode in codici_presenti:
            log(f"  Voce {codice_pdf} già presente nei risultati, salto")
            continue

        # Cerca nel tariffario con normalizzazione
        chiave = tariffario_norm.get(norm)
        if chiave and chiave in tariffario:
            voce = tariffario[chiave]
            costo_totale = round(voce['prezzo'] * quantita, 2)
            risultati.append([
                voce['codice'],
                voce['descrizione'],
                voce['unita'],
                voce['prezzo'],
                quantita,
                costo_totale,
            ])
            codici_presenti.add(pulisci_codice(voce['codice']))
            inseriti += 1
            log(f"  Voce mancante inserita: {codice_pdf} -> {voce['codice']} (qty: {quantita})")
        else:
            ancora_mancanti.append((codice_pdf, quantita))

    if inseriti > 0:
        log(f"  Inserite {inseriti} voci mancanti")
    else:
        log("  Nessuna voce mancante recuperata dal tariffario")

    if ancora_mancanti:
        log(f"  Ancora non trovati: {len(ancora_mancanti)} codici")

    return risultati, ancora_mancanti


def confronta_pdf_csv(pdf_file):
    """Confronta i codici estratti dal PDF con il Tariffario precaricato."""
    if pdf_file is None:
        return [], "", "Carica un file PDF."

    # 1. Estrai codici dal PDF
    lista_pdf, log_estrazione = estrai_codici_da_pdf(pdf_file)
    if not lista_pdf:
        return [], "", log_estrazione

    # 2. Usa tariffario precaricato
    tariffario = TARIFFARIO

    # 3. Confronta usando xcode (codici puliti) con fallback fuzzy
    log("-" * 60)
    log("CONFRONTO CON TARIFFARIO")
    log("-" * 60)

    risultati = []
    non_trovati = []
    match_fuzzy = []

    for codice_pdf, quantita in lista_pdf:
        xcode = pulisci_codice(codice_pdf)

        if xcode in tariffario:
            # Match esatto
            voce = tariffario[xcode]
            costo_totale = round(voce['prezzo'] * quantita, 2)
            risultati.append([
                voce['codice'],
                voce['descrizione'],
                voce['unita'],
                voce['prezzo'],
                quantita,
                costo_totale,
            ])
            log(f"  Match esatto: {codice_pdf} -> {voce['codice']}")
        else:
            # Fallback: fuzzy matching
            log(f"  Ricerca fuzzy per: {codice_pdf}...")
            chiave_simile = trova_codice_simile(xcode, tariffario, TARIFFARIO_NORM)
            if chiave_simile:
                voce = tariffario[chiave_simile]
                costo_totale = round(voce['prezzo'] * quantita, 2)
                risultati.append([
                    voce['codice'],
                    voce['descrizione'],
                    voce['unita'],
                    voce['prezzo'],
                    quantita,
                    costo_totale,
                ])
                match_fuzzy.append(f"{codice_pdf} -> {voce['codice']}")
                log(f"  Match fuzzy: {codice_pdf} -> {voce['codice']}")
            else:
                non_trovati.append((codice_pdf, quantita))
                log(f"  NON TROVATO: {codice_pdf}")

    log(f"Confronto completato: {len(risultati)} trovati, {len(non_trovati)} non trovati")

    # 4. Deduplicazione: rimuove doppioni tenendo la quantità più alta
    risultati = deduplica_risultati(risultati)

    # 5. Inserimento voci mancanti: tenta di recuperare codici non trovati
    risultati, non_trovati_finali = inserisci_voci_mancanti(
        risultati, non_trovati, tariffario, TARIFFARIO_NORM
    )
    codici_non_trovati = [codice for codice, _ in non_trovati_finali]

    # 6. Output stringa
    righe_str = []
    for r in risultati:
        righe_str.append(
            f"{r[0]} | {r[1]} | {r[2]} | €{r[3]:.2f} | Qty: {r[4]} | Totale: €{r[5]:.2f}"
        )

    output_str = "\n".join(righe_str)
    if match_fuzzy:
        output_str += f"\n\n--- Codici trovati tramite match approssimato ({len(match_fuzzy)}): ---\n"
        output_str += "\n".join(match_fuzzy)
    if codici_non_trovati:
        output_str += f"\n\n--- Codici non trovati nel tariffario ({len(codici_non_trovati)}): ---\n"
        output_str += ", ".join(codici_non_trovati)

    # 7. Log finale
    log_finale = (
        f"{log_estrazione} | "
        f"Trovati (esatti): {len(risultati) - len(match_fuzzy)} | "
        f"Trovati (fuzzy): {len(match_fuzzy)} | "
        f"Non trovati: {len(codici_non_trovati)}"
    )

    log("=" * 60)
    log("ELABORAZIONE COMPLETATA")
    log(f"  {log_finale}")
    log("=" * 60)

    return risultati, output_str, log_finale


demo = gr.Interface(
    fn=confronta_pdf_csv,
    inputs=[
        gr.File(label="Carica PDF (computo metrico)", file_types=[".pdf"]),
    ],
    outputs=[
        gr.Dataframe(
            headers=["Codice", "Descrizione", "Unità", "Prezzo Unitario", "Quantità", "Costo Totale"],
            label="Risultati confronto",
        ),
        gr.Textbox(label="Output in linea", lines=10),
        gr.Textbox(label="Log", lines=2),
    ],
    title=f"Confronto PDF ↔ {TARIFFARIO_NAME}",
    description=(
        f"Carica un computo metrico in PDF. "
        f"Il tariffario '{TARIFFARIO_NAME}' è precaricato ({len(TARIFFARIO)} voci). "
        f"Il sistema estrae i codici dal PDF, li confronta (tramite xcode pulito) "
        f"con il tariffario e restituisce: codice, descrizione, unità, prezzo unitario, quantità e costo totale."
    ),
)

if __name__ == "__main__":
    demo.launch()
