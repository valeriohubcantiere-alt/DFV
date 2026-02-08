example_test= """Pagine 1-2: Analizzando il documento, ho estratto i codici del tariffario e le relative quantità totali per ogni voce.

Ho ricostruito i codici che erano divisi su più righe, unendoli per creare la stringa completa. Le quantità sono state convertite in formato numerico.

Ecco la lista di tuple richiesta:

```python
[
    ("ABR25_AT_10.005.005.o", 300.00),
    ("ABR25_AT_10.010.050", 10.00),
    ("ABR25_EL-1_10.100.020.o", 3.00),
    ("A.01.018.09", 25.00),
    ("B.14.103.01", 400.00),
    ("D2.05.154.040.a", 211.00),
    ("CAL25.01.a.04.004.003", 552.00),
    ("CAL25.PR.P.15.085.003", 1500.00),
    ("CAL25.PR.P.20.085.013", 100.00)
]
```

Pagine 2-3: Certamente, ecco la lista di tuple estratta dalle pagine del PDF, contenente i codici del tariffario e le relative quantità.

```python
[
    ("ABR25_AT_10.005.005.o", 300.00),
    ("ABR25_AT_10.010.050", 10.00),
    ("ABR25_EL.110.100.020.b", 3.00),
    ("A.01.018.09", 25.00),
    ("B.14.103.01", 400.00),
    ("D2.05.154.040", 211.00),
    ("CAL25_01.a04.004.003", 552.00),
    ("CAL25_PR.P15.085.003", 1500.00),
    ("CAL25_PR.P29.085.013", 100.00),
    ("CAL25_PR.P29.088.003", 580.00),
    ("CAM25_M02.010.020.K", 10.00),
    ("CAM25_MT.L11.810.017", 10.00),
    ("CAM25_MT.L11.050.005", 20.00),
    ("CAM25_MT.U1.001.139", 35.00),
    ("A.07.01.0124", 3000.00),
    ("C03.022.013.c", 250.00),
    ("D08.001.015205", 150.00),
    ("E04.12.32.020", 155.00)
]
```

Pagine 3-4: Certamente. Ecco la lista di tuple con i codici dei tariffari e le relative quantità estratte dal PDF:

```python
[
    ("CAL25_PR.P29.088.003", 330),
    ("CAM25_M02.010.020.K", 10),
    ("CAM25_MTL.11.010.017", 10),
    ("CAM25_MTL.11.050.005", 20),
    ("CAM25_MTU1.001.139", 35),
    ("A.07.01.0124", 3000),
    ("C03.022.013.c", 250),
    ("D08.001.015205", 150),
    ("E04.12.32.020", 155),
    ("E26.04.90.100", 200),
    ("E01.061.015.o", 100),
    ("TOS25_1.21.B04.000.001", 565),
    ("TOS25_1.21.B04.000.005300", 470),
    ("TOS25_1.PR.P26.110.tos", 325)
]
```"""


import ast
import re

# Trova tutto ciò che è compreso tra parentesi quadre [ ]
matches = re.findall(r'\[.*?\]', example_test, re.DOTALL)

final_list = []
for match in matches:
    # Converte la stringa trovata in una vera lista di tuple
    data = ast.literal_eval(match)
    final_list.extend(data)

# Rimuoviamo eventuali duplicati mantenendo l'ordine
seen = set()
_list = sorted(list(set([x for x in final_list if not (x in seen or seen.add(x))])))

print(_list)

for l in _list:
    print(l)
