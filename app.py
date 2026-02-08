import gradio as gr
from google import genai
import fitz  # PyMuPDF
from PIL import Image
from dotenv import load_dotenv
import os
import io
import re
import ast

from prompt import PROMPT

load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def parse_liste_da_testo(testo):
    """Estrae liste di tuple dal testo restituito da Gemini (logica di main2.py)."""
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


def elabora_pdf(pdf_file, modello="gemini-2.5-pro", dpi=200):
    if pdf_file is None:
        return [], "Carica un file PDF."

    # Converti PDF in immagini con PyMuPDF
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
        return [], "Il PDF deve avere almeno 2 pagine per confrontare coppie consecutive."

    risposte_raw = []

    for i in range(numero_pagine - 1):
        p1 = i + 1
        p2 = i + 2
        img_1 = immagini[i]
        img_2 = immagini[i + 1]

        messaggio = [
            PROMPT,
            f"\n--- PAGINA {p1} ---",
            img_1,
            f"\n--- PAGINA {p2} ---",
            img_2,
        ]

        try:
            response = client.models.generate_content(model=modello, contents=messaggio)
            risposte_raw.append(response.text)
        except Exception as e:
            risposte_raw.append(f"ERRORE pagine {p1}-{p2}: {e}")

    testo_completo = "\n".join(risposte_raw)
    lista_finale = parse_liste_da_testo(testo_completo)

    # Prepara dati per la tabella: lista di [codice, quantità]
    tabella = [[codice, quantita] for codice, quantita in lista_finale]

    log = f"Pagine analizzate: {numero_pagine} | Coppie elaborate: {numero_pagine - 1} | Voci estratte: {len(lista_finale)}"

    return tabella, log


demo = gr.Interface(
    fn=elabora_pdf,
    inputs=gr.File(label="Carica PDF", file_types=[".pdf"]),
    outputs=[
        gr.Dataframe(headers=["Codice Tariffario", "Quantità"], label="Risultati"),
        gr.Textbox(label="Log", lines=2),
    ],
    title="Estrazione Codici Tariffario da PDF",
    description="Carica un computo metrico in PDF. Il sistema analizza coppie di pagine consecutive con Gemini, estrae i codici tariffario e le quantità, e restituisce una lista unica e ordinata.",
)

if __name__ == "__main__":
    demo.launch()
