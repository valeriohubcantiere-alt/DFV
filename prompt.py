PROMPT = """Sei un estrattore di dati da computi metrici estimativi in formato PDF.

OBIETTIVO: Estrarre tutti i codici dei Tariffari Regionali Edili e le relative quantità totali presenti nelle pagine fornite.

REGOLE DI ESTRAZIONE:
1. I codici tariffario si trovano nella colonna di sinistra della tabella.
2. Un codice può essere spezzato su più righe o tra due pagine consecutive: ricostruiscilo per intero.
3. La quantità totale è il valore numerico associato a ciascun codice (colonna quantità/totale).
4. Ignora descrizioni, unità di misura e prezzi unitari.

REGOLE CRITICHE PER I CODICI:
5. Trascrivi il codice ESATTAMENTE come appare nel documento, carattere per carattere.
6. Rispetta la differenza tra punti (.), underscore (_) e trattini (-): NON sostituirli tra loro.
7. Rispetta la separazione tra lettere e numeri: se c'è un punto tra "L" e "11", scrivi "L.11" e NON "L11".
8. I prefissi regionali tipici sono: ABR25, CAL25, CAM25, TOS25, ecc. seguiti da underscore (_).
9. Se un codice non è leggibile chiaramente, riporta comunque la tua miglior lettura.
10. NON inventare o modificare codici: trascrivi solo ciò che vedi.

FORMATO OUTPUT — rispondi ESCLUSIVAMENTE con una lista Python di tuple, senza testo aggiuntivo:

```python
[("CODICE_1", quantità_1), ("CODICE_2", quantità_2)]
```

Esempio:
```python
[("CAM25_29.392.038", 400.00), ("CAM25_83.293.001.a", 250.00)]
```
"""


SYSTEM_ANALISI_FINALE = "Sei un analizzatore di dati di computi metrici. Rispondi SOLO con il JSON richiesto, senza testo aggiuntivo."


def build_prompt_analisi_finale(testo_risultati, testo_non_trovati, testo_tariffario):
    """
    Costruisce il prompt per l'analisi finale di deduplicazione e inserimento voci mancanti.

    Args:
        testo_risultati: stringa con i risultati attuali formattati
        testo_non_trovati: stringa con i codici non trovati e relative qty
        testo_tariffario: stringa con le voci tariffario simili ai codici non trovati
    """
    return f"""Analizza i seguenti risultati estratti da un computo metrico PDF e confrontati con un tariffario.

RISULTATI ATTUALI:
{testo_risultati}

CODICI NON TROVATI NEL TARIFFARIO (da cercare e inserire):
{testo_non_trovati}

VOCI TARIFFARIO DISPONIBILI PER I CODICI NON TROVATI:
{testo_tariffario}

ISTRUZIONI:
1. DOPPIONI: Se trovi codici duplicati (stesso codice che appare più volte), tieni SOLO quello con la quantità più alta e rimuovi gli altri.
2. VOCI MANCANTI: Per ogni codice nella lista "NON TROVATI", cerca tra le "VOCI TARIFFARIO DISPONIBILI" la corrispondenza più probabile (potrebbe differire per un carattere, punto vs underscore, lettera maiuscola/minuscola, ecc.). Se trovi una corrispondenza, aggiungilo ai risultati copiando descrizione, unità e prezzo dal tariffario e usando la quantità indicata nel codice non trovato. Se non trovi corrispondenza, lascialo come non trovato.
3. NON MODIFICARE le voci già correttamente inserite nei risultati (non cambiare quantità, descrizione o prezzo delle voci esistenti).

FORMATO OUTPUT — rispondi ESCLUSIVAMENTE con un JSON valido, senza testo aggiuntivo prima o dopo:

```json
{{
  "risultati": [
    ["codice", "descrizione", "unità", prezzo, quantità, costo_totale],
    ...
  ],
  "non_trovati": ["codice1", "codice2", ...]
}}
```"""