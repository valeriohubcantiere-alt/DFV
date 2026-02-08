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
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Precaricamento del tariffario
TARIFFARIO_NAME = os.environ.get("TARIFFARIO_NAME", "Tariffario2026C")
TARIFFARIO_PATH = os.environ.get("TARIFFARIO_PATH", "./Tariffario2026C.csv")
AI_TEMPERATURE = float(os.environ.get("AI_TEMPERATURE", "0.2"))

if not os.path.exists(TARIFFARIO_PATH):
    raise FileNotFoundError(
        f"File tariffario non trovato: {TARIFFARIO_PATH}. "
        f"Verifica le variabili TARIFFARIO_NAME e TARIFFARIO_PATH nel file .env"
    )

TARIFFARIO = carica_tariffario_csv(TARIFFARIO_PATH)
print(f"Tariffario '{TARIFFARIO_NAME}' caricato da {TARIFFARIO_PATH} ({len(TARIFFARIO)} voci)")


def img_to_base64(img):
    """Converte un'immagine PIL in stringa base64 PNG."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def parse_liste_da_testo(testo):
    """Estrae liste di tuple dal testo restituito da Claude."""
    matches = re.findall(r'\[.*?\]', testo, re.DOTALL)
    tutte = []
    for match in matches:
        try:
            data = ast.literal_eval(match)
            tutte.extend(data)
        except (ValueError, SyntaxError):
            continue
    # Rimuovi duplicati mantenendo l'ordine, poi ordina
    seen = set()
    unici = [x for x in tutte if not (x in seen or seen.add(x))]
    return sorted(unici)


def estrai_codici_da_pdf(pdf_file, modello="claude-sonnet-4-5-20250929", dpi=200):
    """Estrae coppie (codice, quantità) dal PDF usando Claude."""
    doc = fitz.open(pdf_file)
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    immagini = []
    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        immagini.append(img)
    doc.close()
    numero_pagine = len(immagini)

    if numero_pagine < 2:
        return [], "Il PDF deve avere almeno 2 pagine."

    risposte_raw = []

    for i in range(numero_pagine - 1):
        p1 = i + 1
        p2 = i + 2
        img_1 = immagini[i]
        img_2 = immagini[i + 1]

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
                temperature=AI_TEMPERATURE,
                system=PROMPT,
                messages=[{"role": "user", "content": content}],
            )
            risposte_raw.append(response.content[0].text)
        except Exception as e:
            risposte_raw.append(f"ERRORE pagine {p1}-{p2}: {e}")

    testo_completo = "\n".join(risposte_raw)
    lista_finale = parse_liste_da_testo(testo_completo)

    log = f"Pagine: {numero_pagine} | Coppie elaborate: {numero_pagine - 1} | Voci estratte: {len(lista_finale)}"
    return lista_finale, log


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

    # 3. Confronta usando xcode (codici puliti)
    risultati = []
    non_trovati = []

    for codice_pdf, quantita in lista_pdf:
        xcode = pulisci_codice(codice_pdf)

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
        else:
            non_trovati.append(codice_pdf)

    # 4. Output stringa
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
