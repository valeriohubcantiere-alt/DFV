import google.generativeai as genai
from pdf2image import convert_from_path
import os
from PIL import Image

# Configurazione API Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Importa il prompt dal file esterno
from prompt import PROMPT


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
    immagini = convert_from_path(percorso_pdf, dpi=dpi)
    print(f"✓ Convertite {len(immagini)} pagine")
    return immagini


def elabora_pdf_con_gemini(percorso_pdf, modello="gemini-2.5-pro", dpi=200):
    """
    Elabora un PDF inviando coppie di pagine consecutive come immagini a Gemini.

    Args:
        percorso_pdf: Path del file PDF
        modello: Nome del modello Gemini da utilizzare
        dpi: Risoluzione delle immagini

    Returns:
        Lista di risposte da Gemini
    """
    # Converti il PDF in immagini
    immagini = converti_pdf_in_immagini(percorso_pdf, dpi)
    numero_totale_pagine = len(immagini)

    print(f"\nPDF caricato: {numero_totale_pagine} pagine totali")

    # Inizializza il modello
    model = genai.GenerativeModel(modello)

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

        # Costruisci il messaggio con le immagini
        messaggio = [
            PROMPT,
            f"\n--- PAGINA {pagina_corrente} ---",
            img_1,
            f"\n--- PAGINA {pagina_successiva} ---",
            img_2
        ]

        # Invia a Gemini
        try:
            response = model.generate_content(messaggio)
            risposte.append({
                'pagine': f"{pagina_corrente}-{pagina_successiva}",
                'risposta': response.text
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
    risultati = elabora_pdf_con_gemini(pdf_path)

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