import anthropic
import fitz  # PyMuPDF
import os
from dotenv import load_dotenv
from PIL import Image
import io
import base64

# Configurazione API Claude
load_dotenv()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
AI_TEMPERATURE = float(os.environ.get("AI_TEMPERATURE", "0.2"))

# Importa il prompt dal file esterno
from prompt import PROMPT


def img_to_base64(img):
    """Converte un'immagine PIL in stringa base64 PNG."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def converti_pdf_in_immagini(percorso_pdf, dpi=200):
    """
    Converte tutte le pagine del PDF in immagini.

    Args:
        percorso_pdf: Path del file PDF
        dpi: Risoluzione delle immagini (default 200)

    Returns:
        Lista di immagini PIL
    """
    print("Conversione PDF in immagini...")
    doc = fitz.open(percorso_pdf)
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    immagini = []
    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        immagini.append(img)
    doc.close()
    print(f"✓ Convertite {len(immagini)} pagine")
    return immagini


def elabora_pdf_con_claude(percorso_pdf, modello="claude-sonnet-4-20250514", dpi=200):
    """
    Elabora un PDF inviando coppie di pagine consecutive come immagini a Claude.

    Args:
        percorso_pdf: Path del file PDF
        modello: Nome del modello Claude da utilizzare
        dpi: Risoluzione delle immagini

    Returns:
        Lista di risposte da Claude
    """
    # Converti il PDF in immagini
    immagini = converti_pdf_in_immagini(percorso_pdf, dpi)
    numero_totale_pagine = len(immagini)

    print(f"\nPDF caricato: {numero_totale_pagine} pagine totali")

    # Lista per memorizzare tutte le risposte
    risposte = []

    # Elabora le coppie di pagine (1-2, 2-3, 3-4, ...)
    for i in range(numero_totale_pagine - 1):
        pagina_corrente = i + 1
        pagina_successiva = i + 2

        print(f"\nElaborazione pagine {pagina_corrente}-{pagina_successiva}...")

        # Prendi le due immagini consecutive
        img_1 = immagini[i]
        img_2 = immagini[i + 1]

        # Costruisci il messaggio con le immagini in formato Claude
        content = [
            {"type": "text", "text": f"\n--- PAGINA {pagina_corrente} ---"},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_to_base64(img_1),
                },
            },
            {"type": "text", "text": f"\n--- PAGINA {pagina_successiva} ---"},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_to_base64(img_2),
                },
            },
        ]

        # Invia a Claude
        try:
            response = client.messages.create(
                model=modello,
                max_tokens=4096,
                temperature=AI_TEMPERATURE,
                system=PROMPT,
                messages=[{"role": "user", "content": content}],
            )
            risposte.append({
                'pagine': f"{pagina_corrente}-{pagina_successiva}",
                'risposta': response.content[0].text
            })
            print(f"✓ Completato pagine {pagina_corrente}-{pagina_successiva}")
        except Exception as e:
            print(f"✗ Errore nell'elaborazione pagine {pagina_corrente}-{pagina_successiva}: {e}")
            risposte.append({
                'pagine': f"{pagina_corrente}-{pagina_successiva}",
                'risposta': f"ERRORE: {str(e)}"
            })

    return risposte


# Esempio d'uso
if __name__ == "__main__":
    # Specifica il percorso del tuo PDF
    pdf_path = "documento.pdf"

    # Elabora il PDF
    risultati = elabora_pdf_con_claude(pdf_path)

    # Stampa i risultati
    print("\n" + "=" * 50)
    print("RISULTATI")
    print("=" * 50)

    for risultato in risultati:
        print(f"\n--- Pagine {risultato['pagine']} ---")
        print(risultato['risposta'])
        print("-" * 50)

    # Salva i risultati in un file
    with open("risultati.txt", "w", encoding="utf-8") as f:
        for risultato in risultati:
            f.write(f"=== Pagine {risultato['pagine']} ===\n")
            f.write(risultato['risposta'])
            f.write("\n\n" + "=" * 50 + "\n\n")

    print("\n✓ Risultati salvati in 'risultati.txt'")
