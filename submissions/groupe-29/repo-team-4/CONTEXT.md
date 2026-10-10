## 1. The JPG form — the 15 zones to extract

| Zone   | Location on the form                                                                                                                                                        | What to extract                                                                   |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| **1**  | Top-left, next to "cerfa n°"                                                                                                                                                | CERFA identifier code (expected `12278*0x`, see check 3.1)                        |
| **2**  | Header, "identification de l'établissement dont n° FINESS"                                                                                                                  | Establishment number (FINESS)                                                     |
| **3**  | "références à rappeler" → **N° LOT**                                                                                                                                        | Lot number                                                                        |
| **4**  | "références à rappeler" → **N° FACTURE**                                                                                                                                    | Invoice number                                                                    |
| **5**  | "le bénéficiaire des soins" → **n° d'immatriculation et clé**                                                                                                               | Insured/beneficiary number (+ key) — only **first 13 chars** are compared         |
| **6**  | Block **"frais de structure et de soins (1)"** → column **"prestation"** (rows; each row also has période du/au, prix unitaire, quantité, coefficient, **montant facturé**) | List of prestations (e.g. GHS, PH8, EMI…) with their GHS number and billed amount |
| **7**  | Block **"produits de la LPP facturables, spécialités pharmaceutiques et médicaments soumis à ATU"** → column "prestation"                                                   | List of LPP / drug prestations                                                    |
| **8**  | **"sous-total 1+2+3"** (right side, below LPP block)                                                                                                                        | Amount: subtotal of prestations                                                   |
| **9**  | Block **"relevé des honoraires médicaux, para-médicaux et actes de laboratoire"** → column **"numéro d'identification de l'exécutant"**                                     | Executant (practitioner) IDs                                                      |
| **10** | Same block → **"actes effectués"** (code acte ou lettre clé, coefficient, etc.)                                                                                             | Act codes (≤4 chars = NGAP letter key; 7 chars = CCAM code)                       |
| **11** | Right column **"signature des praticiens ou auxiliaires médicaux attestant la prestation des actes…"** (numbered boxes 1–8)                                                 | Presence of practitioner signatures                                               |
| **12** | **"sous-total 4"** (bottom of honoraires block)                                                                                                                             | Amount: subtotal of fees (honoraires)                                             |
| **13** | **"MONTANT TOTAL en euros (1+2+3+4)"**                                                                                                                                      | Total invoice amount                                                              |
| **14** | **"signature du directeur de l'établissement"**                                                                                                                             | Presence of director signature                                                    |
| **15** | Bottom-right corner small code                                                                                                                                              | CERFA code (expected `S3404`)                                                     |

---

## 2. The structured text file (B2 fixed-width format)

### 2.1 Formatting rules (from reviewer comment [SM1])

- **Numeric (N)** fields: left-padded with `0`.
- **Alphanumeric (A)** fields: right-padded with spaces.
- **Amounts:** the **last 2 digits are cents** (e.g. `00081897` → **818.97 €**).
- O = Obligatoire (mandatory), F = Facultatif (optional).

### 2.2 Record (line) types — determined by **character at position 1**

| Code | Meaning                                               | Sub-type rule                                                                                                 |
| ---- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `0`  | File header (Entête fichier)                          | —                                                                                                             |
| `1`  | Lot start (Début de lot)                              | —                                                                                                             |
| `2`  | Invoice start (Début de facture)                      | **2-S** if pos **39** = `S` (optional); else `2` ⇒ **new invoice**                                            |
| `3`  | Hospital prestation lines (Prestations Hospitalières) | **3-S** if pos **39** = `S`; **3-H** if pos **36** = `H`; else `3` ⇒ **new act**                              |
| `4`  | Act lines (Actes / honoraires)                        | **4-S** if pos **36** = `S`; **4-M** if pos **36** = `M`; **4-B** if pos **36** = `B`; else `4` ⇒ **new act** |
| `5`  | Invoice end (Fin de facture)                          | —                                                                                                             |
| `6`  | Lot end (Fin de lot)                                  | —                                                                                                             |

Sub-type lines (S/H/M/B) are complements attached to the preceding main line (the "act" they follow).

### 2.3 Fields used by the controls

| Field                | Line type | Positions | Format | Req. | Meaning                                                                           |
| -------------------- | --------- | --------- | ------ | ---- | --------------------------------------------------------------------------------- |
| **NumeroTiers**      | 1         | 2–10      | 9N     | O    | National ID of the health partner (establishment) + key                           |
| **NumeroLot**        | 1         | 20–22     | 3N     | O    | Lot number                                                                        |
| **NumeroAssure**     | 2         | 12–24     | 13A    | O    | Insured's registration number (n° immatriculation)                                |
| **NumeroFacture**    | 2         | 30–38     | 9N     | O    | Invoice number                                                                    |
| **Acte**             | 3         | 56–60     | (4+1)A | O    | Act/prestation code (e.g. `GHS`, `PH8`, `EMI`)                                    |
| **Acte**             | 4         | 76–80     | (4+1)A | O    | Act code (e.g. `B`, `K`, `ADC`)                                                   |
| **NumeroGH**         | 3         | 110–113   | 4N     | F    | GHS / GHT / GMT number                                                            |
| **NumeroGH**         | 4-S       | 120–123   | 4N     | F    | GHS / GHT / GMT number                                                            |
| **CodeCCAM**         | 4-M       | 43–55     | 13A    | O    | CCAM code: 7 useful chars, left-aligned, space-padded                             |
| **TotalPrestations** | 5         | 42–49     | (6+2)N | O    | Total of reimbursement bases of type-3 records (CP positions 83–90)               |
| **TotalHonoraires**  | 5         | 58–65     | (6+2)N | O    | Total fees incl. overruns (dépassements) of type-4 records (CP positions 115–121) |

_GHS = Groupe Homogène de Séjour (nature & reason of the stay)._

### 2.4 Example file (as given) and decoded values

```
000TE00000200200145      MA00000002351491260804TRMA0574260804CP  B2            128
1200200145      4915743659507POLYCLINIQUE MAYMARD          B2260804DCP 062005U01202P          20260804
2200200145 25202990070000700026080017517226148510249100002000000000000491000104260803000000000 52021512608032608031400
3200200145 25202990070000700026080017500000260803260803GHS  001 00100A1100700340210003744710000037447000374479606000      M0000000
3200200145 252029900700007000260800175S01000000000 00000000000000900000000000000S000000000000000000000000000000000
3200200145 25202990070000700026080017500000260803260803PH8  001 00100 0000000364740003647410000036474000364749606100      M0000000
3200200145 252029900700007000260800175S01201400330L73260803000000900000000000000 000000000000000000000000000000000
3200200145 252029900700007260800175H01      9002651  10000     0018237000398800079760020036474I000408
3200200145 25202990070000700026080017500000260803260803EMI  001 00100 0000000079760000797610000007976000079769606000      M0000000
3200200145 252029900700007000260800175S01201400330L73260803000000900000000000000 000000000000000000000000000000000
4200200145 25202990070000700026080017500000491702593 164937007102530260718B    01011100050000025000277510000027750002775 000000
4200200145 252029900700007260800175S01L 0000000L0000009        0000000000000000000000000000 00000000000000000009606C
4200200145 252029900700007260800175B010000    26071801000091072607180100009106260718010000900526071801000090042607180100005201
4200200145 25202990070000700026080017500000000000000 002014003302573260803K    01001500010000192000288010000028800002880 000000
4200200145 252024900711207260800175S01L 0000000 0000009 00000 0000000000000000000000000000 00000000000000000009606M
4200200145 25202990070000700026080017500000000000000 004917025933516260718ADC  01000100010027934003813010000381300038130 000000
4200200145 252029900700007260800175S01L 0000000 0000009        0000000000000000000000000000 00000000000000000009606C
4200200145 252029900700007260800175M01      JCPD001      10JK 1 000000
5200200145 25202990070000700026080017500900081897000818970000288000002880000000000000000000000000            00081897
620020014500100040001001000084777000084777000000000574      HPTW1ABN0190            000000000
```

⚠️ The PDF text extraction collapsed runs of spaces, so exact column alignment above is approximate; in the real file, slice strictly by position.

Decoded (from the highlighted example):

- **NumeroTiers** = `200200145` (POLYCLINIQUE MAYMARD)
- **NumeroLot** = `574` (also appears as `TRMA0574` in header and `…0574` in type-6 line)
- **NumeroAssure** = `2520299007000`
- **NumeroFacture** = `260800175`
- **Type-3 Actes:** `GHS`, `PH8`, `EMI` — each with **NumeroGH = `9606`**
- **Type-4 Actes:** `B`, `K`, `ADC`; **4-M CodeCCAM:** `JCPD001`; **4-S NumeroGH** = `9606`
- **TotalPrestations** = `00081897` → **818.97 €**
- **TotalHonoraires** = `00002880` → **28.80 €**
- Type-6 lot total `000084777` → **847.77 €** = 818.97 + 28.80 (consistent with expected zone 13).

Observations useful for parser design:

- Type-3-S lines carry no NumeroGH; type-3-H is a complement line.
- One 4-S line in the example has a different insured number (`2520249007112`) — real files may contain such anomalies.
- Type-4 main lines appear to hold executant IDs (e.g. `491702593`, `002014003302573`, `004917025933516`) but **their positions are NOT specified** in the doc.

### 3.1 Document identifier

- **C1** — Zone 1 code must equal **`12278*0`** (form version suffix may follow, e.g. `12278*02`; treat as prefix/pattern match — confirm with user).

### 3.2 Invoice identification keys

- **C2** — Zone 2 (establishment n°) = **NumeroTiers** (type 1, pos 2–10).
- **C3** — Zone 3 (N° LOT) = **NumeroLot** (type 1, pos 20–22).
- **C4** — Zone 4 (N° FACTURE) = **NumeroFacture** (type 2, pos 30–38).
- **C5** — Zone 5 (n° immatriculation), **first 13 characters only** = **NumeroAssure** (type 2, pos 12–24).

### 3.3 Frais de structure et de soins (zone 6)

- **C6** — Zone 6 "prestation" column must contain a **GHS** prestation together with its **GHS number**.
- **C7** — GHS number read in zone 6 = **NumeroGH** (type 3, pos 110–113) of the type-3 line whose Acte = `GHS`.
- **C8** — Every prestation in zone 6 **that has a billed amount (montant facturé)** exists in the file as a type-3 **Acte**.
- **C9** — For every type-3 act **other than GHS**, NumeroGH = NumeroGH of the GHS act.

### 3.4 Produits LPP / pharmaceutiques / médicaments (zone 7)

- **C10** — NumeroGH of type-3 acts = NumeroGH of the GHS act (read in zone 6). _(Largely duplicates C9; likely intended for LPP-related type-3 lines.)_
- **C11** — Every prestation in zone 7 exists in the file as a type-3 **Acte**.

### 3.5 Recap of zones 6 + 7

- **C12** — Zone 8 amount (sous-total 1+2+3) = **TotalPrestations** (type 5, pos 42–49, /100).
- **C13** — Reverse completeness: every type-3 **Acte** in the file appears in **zone 6 or zone 7**.

### 3.6 Relevé des honoraires (zones 9–12)

- **C14** — Every act in zone 10 coded on **≤ 4 characters** exists in the file as a type-4 **Acte** (pos 76–80).
- **C15** — Every act in zone 10 coded on **7 characters** exists in the file as a type-4M **CodeCCAM** (pos 43–55, trimmed).
- **C16** — NumeroGH of type-4S lines (pos 120–123) = NumeroGH of the GHS act (zone 6).
- **C17** — Zone 12 amount (sous-total 4) = **TotalHonoraires** (type 5, pos 58–65, /100).
- **C18** — For each **distinct** executant number in zone 9 that is **not an establishment** (**3rd character ≠ `0`**), there must be a **signature in one of the boxes of zone 11**.
- **C19** — Reverse completeness: every type-4 **Acte** and every type-4M **CodeCCAM** in the file appears in zone 10.

### 3.7 Document conclusion

- **C20** — Zone 13 (MONTANT TOTAL) = **zone 8 + zone 12** (amounts read from the JPG).
- **C21** — A **signature is present in zone 14** (director).

### 3.8 CERFA code

- **C22** — Zone 15 code = **`S3404`**.
