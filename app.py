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

from prompt import PROMPT
from service.service_main import carica_tariffario_csv, pulisci_codice

load_dotenv()
print("[AVVIO] Variabili d'ambiente caricate da .env")

print("[AVVIO] Inizializzazione client Anthropic...")
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
print("[AVVIO] Client Anthropic inizializzato con successo")

# Precaricamento del tariffario
TARIFFARIO_NAME = os.environ.get("TARIFFARIO_NAME", "Tariffario2026C")
TARIFFARIO_PATH = os.environ.get("TARIFFARIO_PATH", "./Tariffario2026C.csv")

print(f"[AVVIO] Verifica file tariffario: {TARIFFARIO_PATH}")
if not os.path.exists(TARIFFARIO_PATH):
    raise FileNotFoundError(
        f"File tariffario non trovato: {TARIFFARIO_PATH}. "
        f"Verifica le variabili TARIFFARIO_NAME e TARIFFARIO_PATH nel file .env"
    )

print(f"[AVVIO] Caricamento tariffario '{TARIFFARIO_NAME}' da {TARIFFARIO_PATH}...")
TARIFFARIO = carica_tariffario_csv(TARIFFARIO_PATH)
print(f"[AVVIO] Tariffario '{TARIFFARIO_NAME}' caricato con successo: {len(TARIFFARIO)} voci")


def img_to_base64(img):
    """Converte un'immagine PIL in stringa base64 PNG."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def parse_liste_da_testo(testo):
    """Estrae liste di tuple dal testo restituito da Claude."""
    print(f"[PARSING] Ricerca liste Python nel testo ({len(testo)} caratteri)...")
    matches = re.findall(r'\[.*?\]', testo, re.DOTALL)
    print(f"[PARSING] Trovate {len(matches)} liste candidate")
    tutte = []
    for idx, match in enumerate(matches, 1):
        try:
            data = ast.literal_eval(match)
            tutte.extend(data)
            print(f"[PARSING] Lista {idx}: {len(data)} voci estratte")
        except (ValueError, SyntaxError):
            print(f"[PARSING] Lista {idx}: scartata (formato non valido)")
            continue
    print(f"[PARSING] Totale voci prima della deduplicazione: {len(tutte)}")
    # Rimuovi duplicati mantenendo l'ordine, poi ordina
    seen = set()
    unici = [x for x in tutte if not (x in seen or seen.add(x))]
    print(f"[PARSING] Totale voci dopo deduplicazione: {len(unici)}")
    return sorted(unici)


def estrai_codici_da_pdf(pdf_file, modello="claude-sonnet-4-5-20250929", dpi=200):
    """Estrae coppie (codice, quantità) dal PDF usando Claude."""
    print(f"\n{'='*60}")
    print(f"[PDF] Apertura file PDF: {pdf_file}")
    doc = fitz.open(pdf_file)
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    immagini = []
    print(f"[PDF] Conversione pagine in immagini (DPI={dpi})...")
    for idx, page in enumerate(doc):
        num_pag = idx + 1
        print(f"[PDF] Lettura pagina {num_pag}...")
        pix = page.get_pixmap(matrix=matrix)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        immagini.append(img)
        print(f"[PDF] Pagina {num_pag} convertita in immagine ({img.width}x{img.height} px)")
    doc.close()
    numero_pagine = len(immagini)
    print(f"[PDF] Totale pagine lette: {numero_pagine}")

    if numero_pagine < 2:
        print("[PDF] ERRORE: Il PDF deve avere almeno 2 pagine.")
        return [], "Il PDF deve avere almeno 2 pagine."

    risposte_raw = []
    coppie_totali = numero_pagine - 1
    print(f"\n[CLAUDE] Inizio analisi con modello: {modello}")
    print(f"[CLAUDE] Coppie di pagine da elaborare: {coppie_totali}")

    for i in range(numero_pagine - 1):
        p1 = i + 1
        p2 = i + 2
        img_1 = immagini[i]
        img_2 = immagini[i + 1]

        print(f"\n[CLAUDE] --- Elaborazione coppia {i+1}/{coppie_totali}: pagine {p1}-{p2} ---")
        print(f"[CLAUDE] Preparazione immagini pagina {p1} e pagina {p2} in base64...")

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
            print(f"[CLAUDE] Invio pagine {p1}-{p2} al modello {modello}...")
            response = client.messages.create(
                model=modello,
                max_tokens=4096,
                system=PROMPT,
                messages=[{"role": "user", "content": content}],
            )
            risposta_testo = response.content[0].text
            risposte_raw.append(risposta_testo)
            print(f"[CLAUDE] Risposta ricevuta per pagine {p1}-{p2} ({len(risposta_testo)} caratteri)")
        except Exception as e:
            print(f"[CLAUDE] ERRORE nell'elaborazione pagine {p1}-{p2}: {e}")
            risposte_raw.append(f"ERRORE pagine {p1}-{p2}: {e}")

    print(f"\n[PARSING] Analisi delle risposte di Claude...")
    testo_completo = "\n".join(risposte_raw)
    lista_finale = parse_liste_da_testo(testo_completo)
    print(f"[PARSING] Voci estratte dopo deduplicazione e ordinamento: {len(lista_finale)}")

    log = f"Pagine: {numero_pagine} | Coppie elaborate: {numero_pagine - 1} | Voci estratte: {len(lista_finale)}"
    print(f"[PDF] Riepilogo estrazione: {log}")
    return lista_finale, log


def confronta_pdf_csv(pdf_file):
    """Confronta i codici estratti dal PDF con il Tariffario precaricato."""
    if pdf_file is None:
        print("[CONFRONTO] Nessun file PDF caricato.")
        return [], "", "Carica un file PDF."

    print(f"\n{'='*60}")
    print(f"[CONFRONTO] Inizio elaborazione completa")
    print(f"{'='*60}")

    # 1. Estrai codici dal PDF
    print("[CONFRONTO] Fase 1: Estrazione codici dal PDF...")
    lista_pdf, log_estrazione = estrai_codici_da_pdf(pdf_file)
    if not lista_pdf:
        print("[CONFRONTO] Nessun codice estratto dal PDF. Interruzione.")
        return [], "", log_estrazione

    print(f"[CONFRONTO] Fase 1 completata: {len(lista_pdf)} codici estratti")

    # 2. Usa tariffario precaricato
    tariffario = TARIFFARIO
    print(f"\n[CONFRONTO] Fase 2: Confronto con tariffario '{TARIFFARIO_NAME}' ({len(tariffario)} voci)")

    # 3. Confronta usando xcode (codici puliti)
    risultati = []
    non_trovati = []

    for idx, (codice_pdf, quantita) in enumerate(lista_pdf, 1):
        xcode = pulisci_codice(codice_pdf)
        print(f"[CONFRONTO] Analisi codice {idx}/{len(lista_pdf)}: {codice_pdf} (xcode: {xcode}, qty: {quantita})")

        if xcode in tariffario:
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
            print(f"[CONFRONTO]   -> TROVATO: {voce['codice']} | {voce['descrizione'][:50]}... | Prezzo: {voce['prezzo']:.2f} | Totale: {costo_totale:.2f}")
        else:
            non_trovati.append(codice_pdf)
            print(f"[CONFRONTO]   -> NON TROVATO nel tariffario")

    # 4. Output stringa
    print(f"\n[RISULTATI] Generazione output...")
    righe_str = []
    for r in risultati:
        righe_str.append(
            f"{r[0]} | {r[1]} | {r[2]} | €{r[3]:.2f} | Qty: {r[4]} | Totale: €{r[5]:.2f}"
        )

    output_str = "\n".join(righe_str)
    if non_trovati:
        output_str += f"\n\n--- Codici non trovati nel tariffario ({len(non_trovati)}): ---\n"
        output_str += ", ".join(non_trovati)

    # 5. Log finale
    log_finale = (
        f"{log_estrazione} | "
        f"Trovati nel tariffario: {len(risultati)} | "
        f"Non trovati: {len(non_trovati)}"
    )

    print(f"\n{'='*60}")
    print(f"[RISULTATI] RIEPILOGO FINALE")
    print(f"{'='*60}")
    print(f"[RISULTATI] Codici estratti dal PDF: {len(lista_pdf)}")
    print(f"[RISULTATI] Trovati nel tariffario: {len(risultati)}")
    print(f"[RISULTATI] Non trovati: {len(non_trovati)}")
    if risultati:
        totale_complessivo = sum(r[5] for r in risultati)
        print(f"[RISULTATI] Costo totale complessivo: {totale_complessivo:.2f}")
    print(f"{'='*60}\n")

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
    print(f"\n[AVVIO] Lancio interfaccia Gradio...")
    demo.launch()
