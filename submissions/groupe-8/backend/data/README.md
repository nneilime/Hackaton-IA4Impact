# Data

`raw/` holds the files provided by the organisers (Drive folder "Challenge"). **Never edit them**; the loaders in
`src/dispatch/data/loaders.py` are the only code that reads them.

| File | Rows | Content |
|---|---|---|
| `poste_v2.csv` | 33,288 | Substations (Ariège, Haute-Garonne, Gers): position, `nb_clients` (5–150, generated), `poste_avec_client_sensible` (0/1) |
| `coupures_v2_100_crises.csv` | 15,681 | Simulated incidents in 100 crises: substation, cause, time, repair duration (2h/4h/8h) |
| `agents_v2.csv` | 18 | Operational sites with their number of teams (63 in total) |
| `insee_v2.csv` | 1,365 | Communes (centroid of their substations) |
| `Hackathon_2026_LISEZ_MOI_Enedis.docx` | – | Official challenge description |
| `Hackathon_2026_PITCH_Enedis.pptx` | – | Organisers' pitch |

Format: `;` separator, UTF-8 with BOM → `pd.read_csv(path, sep=";", encoding="utf-8-sig")`.
Links: `coupures.id_poste → poste.id_poste`, `poste.code_insee → insee.code_insee`.

Known glitches: 5 incidents reference a missing substation (dropped by the loader, with a warning); 43 cases of the same
substation failing twice within one crisis (kept as separate incidents); the organisers' README says 20 sites, but the file has 18.

These files are **example scenarios** that feed the live event stream. The system must not depend on them.
