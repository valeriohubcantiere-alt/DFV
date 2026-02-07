import gradio as gr
from google import genai
import fitz  # PyMuPDF
from PIL import Image
from dotenv import load_dotenv
import os
import io

from prompt import PROMPT

load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def elabora_pdf(pdf_file, modello="gemini-2.5-pro", dpi=200):
    if pdf_file is None:
        return "Carica un file PDF."

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
        return "Il PDF deve avere almeno 2 pagine per confrontare coppie consecutive."

    righe = []

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
            righe.append(f"Pagine {p1}-{p2}: {response.text}")
        except Exception as e:
            righe.append(f"Pagine {p1}-{p2}: ERRORE - {e}")

    return "\n\n".join(righe)


demo = gr.Interface(
    fn=elabora_pdf,
    inputs=gr.File(label="Carica PDF", file_types=[".pdf"]),
    outputs=gr.Textbox(label="Risultati", lines=20),
    title="Analisi PDF con Gemini",
    description=f"Carica un PDF. Ogni coppia di pagine consecutive viene analizzata con il prompt:\n\n**{PROMPT}**",
)

if __name__ == "__main__":
    demo.launch()
