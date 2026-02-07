import gradio as gr
import google.generativeai as genai
from pdf2image import convert_from_path
from dotenv import load_dotenv
import os
import tempfile

from prompt import PROMPT

load_dotenv()
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))


def elabora_pdf(pdf_file, modello="gemini-2.5-pro", dpi=200):
    if pdf_file is None:
        return "Carica un file PDF."

    # Converti PDF in immagini
    immagini = convert_from_path(pdf_file, dpi=dpi)
    numero_pagine = len(immagini)

    if numero_pagine < 2:
        return "Il PDF deve avere almeno 2 pagine per confrontare coppie consecutive."

    model = genai.GenerativeModel(modello)
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
            response = model.generate_content(messaggio)
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
