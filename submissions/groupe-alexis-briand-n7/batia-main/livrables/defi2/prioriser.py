import sys, re, math, json
import numpy as np, pandas as pd, pulp

D, OUT = sys.argv[1], sys.argv[2]
W0, W1 = pd.Timestamp("2023-01-01"), pd.Timestamp("2026-01-01")
REF = pd.Timestamp("2026-01-01")
BUDGET = 1_500_000
YEARS = list(range(2026, 2036))

res = pd.read_csv(f"{D}/01_residences.csv")
bat = pd.read_csv(f"{D}/02_batiments.csv")
lgt = pd.read_csv(f"{D}/03_logements.csv")
eqp = pd.read_csv(f"{D}/04_equipements.csv")
dem = pd.read_csv(f"{D}/05_demandes_locataires.csv")
itv = pd.read_csv(f"{D}/06_interventions.csv")
cmd = pd.read_csv(f"{D}/07_commandes.csv")
ops = pd.read_csv(f"{D}/08_plan_investissement.csv")

lgt = lgt.merge(bat[["batiment_id", "nb_niveaux"]], on="batiment_id")
lgt["top_floor"] = lgt.etage == lgt.nb_niveaux - 1
itv["dt"] = pd.to_datetime(itv.date_intervention)
dem["dt"] = pd.to_datetime(dem.date_creation)
cmd["dt"] = pd.to_datetime(cmd.date_commande)
eqp["age"] = (REF - pd.to_datetime(eqp.date_pose)).dt.days / 365.25
eqp["ratio"] = eqp.age / eqp.duree_vie_reference_ans

E_TH = [(70, "A"), (110, "B"), (180, "C"), (250, "D"), (330, "E"), (420, "F")]
G_TH = [(6, "A"), (11, "B"), (30, "C"), (50, "D"), (70, "E"), (100, "F")]
ORDER = "ABCDEFG"
def lab(v, th):
    for t, l in th:
        if v <= t:
            return l
    return "G"
def glob(c, g):
    a, b = lab(c, E_TH), lab(g, G_TH)
    return a if ORDER.index(a) >= ORDER.index(b) else b
lgt["lab_check"] = [glob(c, g) for c, g in zip(lgt.dpe_conso_ep_kwh_m2_an, lgt.dpe_ges_kgco2_m2_an)]
LABEL_MISMATCH = int((lgt.lab_check != lgt.dpe_etiquette_globale).sum())
REGW = {"G": 3, "F": 2, "E": 1}

itv_w = itv[(itv.dt >= W0) & (itv.dt < W1)]
dem_w = dem[(dem.dt >= W0) & (dem.dt < W1)]
cmd_w = cmd[(cmd.dt >= W0) & (cmd.dt < W1)]
dtext = (dem_w.motif.fillna("") + " | " + dem_w.objet.fillna("") + " | " + dem_w.texte_demande.fillna("")).str.lower()

THEMES = {
    "heat": r"chauffage|radiateur|convecteur|reste froid|logement froid|temp[ée]rature basse|chaudi[eè]re|pompe [àa] chaleur|panneau",
    "ecs": r"eau chaude|eau ti[eè]de|cumulus|ballon|chauffe[- ]eau",
    "window": r"fen[eê]tre|volet",
    "damp": r"humidit|moisissure|condensation",
    "infil": r"infiltration",
    "vmc": r"vmc|ventilation|aspiration",
    "elev": r"ascenseur",
    "hall": r"propret[ée] r[ée]sidence|parties communes sales|propret[ée] du hall|vandalisme|porte hall|porte de hall|panne [ée]lectrique dans les parties communes|[ée]clairage hall",
    "door": r"porte hall|porte de hall|interphon",
}
NOISE_RE = r"bruit|bruyant|nuisances sonores"

HALL_CMD = r"ECLAIRAGE PARTIES COMMUNES|NETTOYAGE PARTIES COMMUNES"
SPEC = {
    "OPE-007": dict(fam=["ballon_ecs_electrique"], cmd=r"CUMULUS|GROUPE DE SECURITE", th=["ecs"], kind="equipment"),
    "OPE-005": dict(fam=[], cmd=None, th=["heat", "damp", "infil"], kind="envelope"),
    "OPE-023": dict(fam=[], cmd=HALL_CMD, th=["hall"], kind="common"),
    "OPE-013": dict(fam=["caisson_vmc", "bouches_vmc"], cmd=r"VMC", th=["vmc", "damp"], kind="equipment"),
    "OPE-026": dict(fam=[], cmd=HALL_CMD, th=["hall"], kind="common"),
    "OPE-004": dict(fam=["ascenseur"], bats=["BAT-C1", "BAT-C2", "BAT-C3"], cmd=None, th=["elev"], kind="equipment"),
    "OPE-029": dict(fam=[], cmd=None, th=["infil"], kind="envelope"),
    "OPE-014": dict(fam=[], cmd=None, th=["heat", "damp"], kind="envelope"),
    "OPE-011": dict(fam=[], cmd=None, th=["heat", "damp"], kind="envelope"),
    "OPE-009": dict(fam=["ascenseur"], cmd=None, th=["elev"], kind="equipment"),
    "OPE-001": dict(fam=["chaufferie_collective"], cmd=r"CHAUFFERIE", th=["heat", "ecs"], kind="equipment"),
    "OPE-006": dict(fam=["convecteurs_electriques"], cmd="A34", th=["heat"], kind="equipment"),
    "OPE-016": dict(fam=["ballon_ecs_electrique"], cmd=r"CUMULUS|GROUPE DE SECURITE", th=["ecs"], kind="equipment"),
    "OPE-025": dict(fam=[], cmd=HALL_CMD, th=["hall"], kind="common"),
    "OPE-012": dict(fam=["volets_roulants"], cmd=r"VOLET", th=["window", "damp"], kind="envelope"),
    "OPE-021": dict(fam=["production_ecs_solaire"], cmd=None, th=["ecs"], kind="equipment"),
    "OPE-028": dict(fam=[], cmd=None, th=["infil"], kind="envelope"),
    "OPE-020": dict(fam=["ballon_thermodynamique"], lot=30, cmd=r"BALLON THERMODYNAMIQUE", th=["ecs"], kind="equipment"),
    "OPE-027": dict(fam=[], cmd=None, th=["infil"], kind="envelope"),
    "OPE-018": dict(fam=["ascenseur"], bats=["BAT-B1"], cmd=None, th=["elev"], kind="equipment"),
    "OPE-010": dict(fam=["chaudiere_gaz_individuelle"], cmd=r"CHAUDIERE GAZ", th=["heat", "ecs"], kind="equipment"),
    "OPE-022": dict(fam=[], cmd=HALL_CMD, th=["hall"], kind="common"),
    "OPE-008": dict(fam=[], cmd=None, th=["damp", "vmc"], kind="envelope"),
    "OPE-002": dict(fam=[], cmd=None, th=["heat", "damp", "infil"], kind="envelope"),
    "OPE-024": dict(fam=[], cmd=HALL_CMD, th=["hall"], kind="common"),
    "OPE-017": dict(fam=["porte_hall_interphonie"], bats=["BAT-B1"], cmd=r"PORTE HALL|VENTOUSE|INTERPHONIE", th=["door"], kind="common"),
    "OPE-003": dict(fam=["volets_roulants"], cmd=r"VOLET", th=["window", "damp"], kind="envelope"),
    "OPE-019": dict(fam=["pompe_a_chaleur"], lot=20, cmd=r"POMPE A CHALEUR", th=["heat", "ecs"], kind="equipment"),
    "OPE-015": dict(fam=["chaudiere_gaz_individuelle"], cmd=r"CHAUDIERE GAZ", th=["heat", "ecs"], kind="equipment"),
}

GRAV = {"Arrêt total": 3, "Fonctionnement dégradé": 2, "Gêne mineure": 1}
itv_w = itv_w.assign(gw=itv_w.gravite.map(GRAV).fillna(0))
dep_w = itv_w[itv_w.type_intervention == "Dépannage"]
fail_by_eq = dep_w.groupby("equipement_id").gw.sum()

resi = res.set_index("residence_id")
rows = []
for _, o in ops.iterrows():
    s = SPEC[o.operation_id]
    r = o.residence_id
    L = lgt[lgt.residence_id == r]
    E = eqp[(eqp.residence_id == r) & (eqp.famille.isin(s["fam"]))]
    if s.get("bats"):
        L = L[L.batiment_id.isin(s["bats"])]
        E = E[E.batiment_id.isin(s["bats"])]
    if s.get("lot"):
        E = E.assign(f=E.equipement_id.map(fail_by_eq).fillna(0)).sort_values(["ratio", "f"], ascending=False).head(s["lot"])
        L = L[L.logement_id.isin(E.logement_id)]
    share = len(L) / resi.loc[r, "nb_logements"]
    lg = set(L.logement_id)
    eqs = set(E.equipement_id)

    Dp = dep_w[dep_w.equipement_id.isin(eqs)]
    Iw = itv_w[itv_w.equipement_id.isin(eqs)]
    n_dep = len(Dp)
    n_block = int((Dp.gravite == "Arrêt total").sum())
    fail_idx = Dp.gw.sum() / 3
    n_anom = int(Iw.resultat.isin(["Anomalie constatée", "Remplacement nécessaire"]).sum())
    n_absent = int((Iw.resultat == "Logement absent - visite non réalisée").sum())

    spend = 0.0
    capex_past = 0.0
    C = cmd_w[cmd_w.residence_id == r]
    if s["cmd"]:
        if s["cmd"] == "A34":
            M = C[C.corps_etat == "A34"]
        else:
            M = C[C.libelle.str.contains(s["cmd"], regex=True)]
        M = M[M.type_commande != "GROS ENTRETIEN"]
        priv = M[M.logement_id.notna() & M.logement_id.isin(lg)].montant_ttc.sum()
        pco = M[M.logement_id.isna()].montant_ttc.sum() * share
        spend = (priv + pco) / 3
    Gc = cmd[(cmd.residence_id == r) & (cmd.type_commande == "GROS ENTRETIEN")]
    if "ascenseur" in s["fam"]:
        capex_past = Gc[Gc.libelle.str.contains("ASCENSEUR")].montant_ttc.sum()
    if "chaufferie_collective" in s["fam"]:
        capex_past = Gc[Gc.libelle.str.contains("CHAUFFERIE")].montant_ttc.sum()

    if len(E):
        age_mean = E.age.mean()
        life = E.duree_vie_reference_ans.iloc[0] if E.famille.nunique() == 1 else np.nan
        ratio_mean = E.ratio.clip(upper=1.2).mean()
        past_life_2026 = (E.ratio >= 1).mean()
        yrs_to = int(o.annee_souhaitee) - 2026
        past_life_wish = ((E.age + yrs_to) / E.duree_vie_reference_ans >= 1).mean()
        recent5 = (E.age < 5).mean()
        repl = int(E.nb_remplacements_2018_2025.sum())
    else:
        age_mean = life = ratio_mean = past_life_2026 = past_life_wish = recent5 = np.nan
        repl = 0

    Dm = dem_w[(dem_w.residence_id == r)]
    if s.get("bats"):
        Dm = Dm[Dm.batiment_id.isin(s["bats"]) | Dm.batiment_id.isna()]
    if s.get("lot"):
        Dm = Dm[Dm.logement_id.isin(lg)]
    tx = dtext.loc[Dm.index]
    pat = "|".join(THEMES[t] for t in s["th"])
    hit = tx.str.contains(pat, regex=True)
    n_compl = int(hit.sum())
    n_compl_reopen = int((hit & (Dm.demande_reouverte == "Oui")).sum())
    n_noise = int(tx.str.contains(NOISE_RE, regex=True).sum())
    n_noise_equip = int((tx.str.contains(NOISE_RE, regex=True) & ~Dm.motif.eq("Nuisances sonores")).sum())

    gain = o.gain_conso_ep_estime_kwh_m2_an
    fac = 1 - gain / resi.loc[r, "conso_ep_moyenne_kwh_m2_an"]
    before = L.lab_check
    after = [glob(c * fac, g * fac) for c, g in zip(L.dpe_conso_ep_kwh_m2_an, L.dpe_ges_kgco2_m2_an)]
    after = pd.Series(after, index=L.index)
    reg_pts = before.map(REGW).fillna(0).sum() - after.map(REGW).fillna(0).sum()
    surf = L.surface_habitable_m2.sum()
    mwh = gain * surf / 1000
    rows.append(dict(
        operation_id=o.operation_id, perimetre_logements=len(L), perimetre_surface_m2=round(surf),
        res_label=resi.loc[r, "etiquette_dpe_majoritaire"], res_conso=resi.loc[r, "conso_ep_moyenne_kwh_m2_an"],
        res_energie=resi.loc[r, "energie_chauffage"], res_annee=resi.loc[r, "annee_construction"],
        n_G=int((L.dpe_etiquette_globale == "G").sum()), n_F=int((L.dpe_etiquette_globale == "F").sum()), n_E=int((L.dpe_etiquette_globale == "E").sum()),
        share_FG=round(L.dpe_etiquette_globale.isin(["F", "G"]).mean(), 3), share_E=round((L.dpe_etiquette_globale == "E").mean(), 3),
        old_dpe_share=round(L.dpe_methode.str.startswith("Ancien").mean(), 3),
        vacants=int((L.statut_occupation == "Vacant").sum()), vacancy_rate=round((L.statut_occupation == "Vacant").mean(), 3),
        turnover_per_lgt_yr=round(L.nb_changements_locataire_2018_2025.mean() / 8, 3),
        n_equip=len(E), equip_age_mean=round(age_mean, 1) if len(E) else np.nan, equip_life_ref=life,
        equip_age_ratio_mean=round(ratio_mean, 2) if len(E) else np.nan,
        share_past_life_2026=round(past_life_2026, 2) if len(E) else np.nan,
        share_past_life_wish_year=round(past_life_wish, 2) if len(E) else np.nan,
        share_installed_lt5y=round(recent5, 2) if len(E) else np.nan, replacements_2018_2025=repl,
        depannages_2023_2025=n_dep, arrets_totaux_2023_2025=n_block, failure_index_per_yr=round(fail_idx, 1),
        anomalies_2023_2025=n_anom, absences_visite_2023_2025=n_absent,
        spend_related_per_yr=round(spend), past_capex_same_scope=round(capex_past),
        complaints_related_2023_2025=n_compl, complaints_related_reopened=n_compl_reopen,
        noise_complaints_2023_2025=n_noise, noise_from_equipment=n_noise_equip,
        mwh_ep_saved_per_yr=round(mwh, 1), kwh_ep_per_eur=round(mwh * 1000 / o.cout_estime_ttc, 3),
        reg_points_removed=reg_pts,
        lgt_out_of_G=int(((before == "G") & (after != "G")).sum()),
        lgt_out_of_FG=int((before.isin(["F", "G"]) & ~after.isin(["F", "G"])).sum()),
        lgt_out_of_EFG=int((before.isin(["E", "F", "G"]) & ~after.isin(["E", "F", "G"])).sum()),
        kind=s["kind"],
    ))
en = ops.merge(pd.DataFrame(rows), on="operation_id")
def flags(o):
    f = []
    if o.past_capex_same_scope > 0:
        f.append(f"capex deja commande sur ce perimetre 2018-2025: {o.past_capex_same_scope:.0f} EUR")
    if o.share_installed_lt5y >= 0.3:
        f.append(f"{o.share_installed_lt5y:.0%} des equipements cibles poses il y a moins de 5 ans")
    if o.n_equip > 0 and o.share_past_life_wish_year == 0:
        f.append("aucun equipement cible au-dela de sa duree de vie a l'annee souhaitee")
    if o.nb_logements_concernes != o.perimetre_logements:
        f.append(f"nb_logements_concernes {o.nb_logements_concernes} vs perimetre {o.perimetre_logements}")
    return "; ".join(f)
en["alertes_donnees"] = en.apply(flags, axis=1)
def years_needed(c):
    return max(1, math.ceil(c / BUDGET))

PREC = [("OPE-029", "OPE-005"), ("OPE-005", "OPE-008"), ("OPE-027", "OPE-002"), ("OPE-003", "OPE-002")]
from itertools import combinations
def subset_counts():
    out = {}
    for r in ["RES-A", "RES-C", "RES-F", "RES-G"]:
        O = en[(en.residence_id == r) & (en.gain_conso_ep_estime_kwh_m2_an > 0)]
        ids = list(O.operation_id)
        L = lgt[lgt.residence_id == r]
        tab = {}
        for n in range(len(ids) + 1):
            for S in combinations(ids, n):
                f = 1.0
                for op in S:
                    f *= 1 - O.set_index("operation_id").loc[op, "gain_conso_ep_estime_kwh_m2_an"] / resi.loc[r, "conso_ep_moyenne_kwh_m2_an"]
                labs = [glob(c * f, g * f) for c, g in zip(L.dpe_conso_ep_kwh_m2_an, L.dpe_ges_kgco2_m2_an)]
                tab[S] = (sum(l == "G" for l in labs), sum(l in "FG" for l in labs), sum(l in "EFG" for l in labs))
        out[r] = (ids, tab)
    return out

def place(order):
    cost = en.set_index("operation_id").cout_estime_ttc
    used = {t: 0.0 for t in YEARS}
    start = {}
    for op in order:
        k = years_needed(cost[op])
        for s in YEARS:
            span = list(range(s, s + k))
            if span[-1] > YEARS[-1]:
                break
            if all(used[t] + cost[op] / k <= BUDGET + 1e-6 for t in span):
                for t in span:
                    used[t] += cost[op] / k
                start[op] = s
                break
    return start

def strict_fifo(order):
    cost = en.set_index("operation_id").cout_estime_ttc
    used = {t: 0.0 for t in YEARS}
    start, cur = {}, YEARS[0]
    for op in order:
        k = years_needed(cost[op])
        s = cur
        while True:
            span = list(range(s, s + k))
            if span[-1] > YEARS[-1]:
                s = None
                break
            if all(used[t] + cost[op] / k <= BUDGET + 1e-6 for t in span):
                break
            s += 1
        if s is None:
            continue
        for t in range(s, s + k):
            used[t] += cost[op] / k
        start[op] = s
        cur = s
    return start

def simulate(start, year):
    cost = en.set_index("operation_id")
    f = pd.Series(1.0, index=lgt.index)
    for op, s in start.items():
        k = years_needed(cost.loc[op, "cout_estime_ttc"])
        if s + k - 1 < year:
            sp = SPEC[op]
            r = cost.loc[op, "residence_id"]
            m = lgt.residence_id == r
            if sp.get("bats"):
                m &= lgt.batiment_id.isin(sp["bats"])
            if sp.get("lot"):
                E = eqp[(eqp.residence_id == r) & eqp.famille.isin(sp["fam"])]
                E = E.assign(f=E.equipement_id.map(fail_by_eq).fillna(0)).sort_values(["ratio", "f"], ascending=False).head(sp["lot"])
                m &= lgt.logement_id.isin(E.logement_id)
            f[m] *= 1 - cost.loc[op, "gain_conso_ep_estime_kwh_m2_an"] / resi.loc[r, "conso_ep_moyenne_kwh_m2_an"]
    labs = pd.Series([glob(c * k, g * k) for c, g, k in zip(lgt.dpe_conso_ep_kwh_m2_an, lgt.dpe_ges_kgco2_m2_an, f)])
    mwh = ((1 - f) * lgt.dpe_conso_ep_kwh_m2_an * lgt.surface_habitable_m2).sum() / 1000
    return labs, mwh


RISQUE = pd.read_csv(sys.argv[3]).set_index("equipement_id").score_risque if len(sys.argv) > 3 else None
LOYER_ANNUEL = 7000
TAUX_ROTATION = (lgt.groupby("residence_id").nb_changements_locataire_2018_2025.mean() / 8).to_dict()
EURO_PAR_POINT = 1000
DELAI_SOLVEUR = 240

def norm_p90(x):
    x = x.fillna(0).astype(float)
    cap = x[x > 0].quantile(0.9) if (x > 0).any() else 0
    xc = x.clip(upper=cap)
    return 10 * xc / xc.max() if xc.max() > 0 else xc * 0

en["c_reg"] = norm_p90(en.reg_points_removed)
en["c_energy"] = norm_p90(en.kwh_ep_per_eur)
en["c_maint"] = 0.5 * norm_p90(en.spend_related_per_yr) + 0.5 * norm_p90(en.failure_index_per_yr)
en["c_tenant"] = 0.6 * norm_p90(en.complaints_related_2023_2025) + 0.2 * norm_p90(en.vacancy_rate) + 0.2 * norm_p90(en.turnover_per_lgt_yr)
en["c_eol"] = 10 * en.equip_age_ratio_mean.fillna(0) / 1.2
en["c_energy_abs"] = norm_p90(en.mwh_ep_saved_per_yr)
en["c_cost"] = 10 * (1 - en.cout_estime_ttc / en.cout_estime_ttc.max())
CRIT = ["c_reg", "c_energy", "c_maint", "c_tenant", "c_eol"]
SCEN = {
    "base": dict(c_reg=25, c_energy=20, c_maint=20, c_tenant=15, c_eol=20),
    "reglementaire_d_abord": dict(c_reg=50, c_energy=15, c_maint=10, c_tenant=15, c_eol=10),
    "cout_d_abord": dict(c_reg=10, c_energy=35, c_maint=35, c_tenant=10, c_eol=10),
    "locataire_d_abord": dict(c_reg=15, c_energy=10, c_maint=15, c_tenant=45, c_eol=15),
    "commanditaire": dict(c_maint=20, c_eol=20, c_energy_abs=30, c_cost=20, c_tenant=10),
}
def score(w):
    return sum(en[k] * w[k] for k in w) / 10

def cibles(o):
    s = SPEC[o.operation_id]; r = o.residence_id
    E = eqp[(eqp.residence_id == r) & (eqp.famille.isin(s["fam"]))]
    if s.get("bats"):
        E = E[E.batiment_id.isin(s["bats"])]
    if s.get("lot"):
        E = E.assign(f=E.equipement_id.map(fail_by_eq).fillna(0)).sort_values(["ratio", "f"], ascending=False).head(s["lot"])
    return E
if RISQUE is not None:
    pa = []
    for _, o in en.iterrows():
        E = cibles(o); rk = E.equipement_id.map(RISQUE)
        pa.append(round(float(rk.fillna(0).sum() * 12 / 9), 1) if len(E) else 0.0)
    en["pannes_attendues_par_an_defi1"] = pa

ops_idx = en.set_index("operation_id")
COST = ops_idx.cout_estime_ttc
OPS = list(en.operation_id)
SUBSETS = subset_counts()

def indice_interdit(t):
    if t < 2027: return None
    if t < 2028: return 0
    if t < 2034: return 1
    return 2

def ilp(sc, lam=2.0, disc=0.08, mode="score", mu=None):
    p = pulp.LpProblem("plan", pulp.LpMaximize)
    x = {}
    for op in OPS:
        k = years_needed(COST[op])
        for s in YEARS:
            if s + k - 1 <= YEARS[-1]:
                x[op, s] = pulp.LpVariable(f"x_{op}_{s}".replace("-", "_"), cat="Binary")
    val = {(op, s): sc[op] * (1 - disc * (s - 2026)) - lam * abs(s - ops_idx.loc[op, "annee_souhaitee"]) for (op, s) in x}
    obj = pulp.lpSum(val[k] * v for k, v in x.items())
    for op in OPS:
        p += pulp.lpSum(v for (o2, s), v in x.items() if o2 == op) == 1
    for t in YEARS:
        p += pulp.lpSum(COST[op] / years_needed(COST[op]) * v for (op, s), v in x.items() if s <= t <= s + years_needed(COST[op]) - 1) <= BUDGET
    for a, b in PREC:
        p += pulp.lpSum(s * v for (o2, s), v in x.items() if o2 == a) <= pulp.lpSum(s * v for (o2, s), v in x.items() if o2 == b)
    breach, euros = [], []
    statuts = []
    if mode != "score":
        def done_by(op, last):
            k = years_needed(COST[op])
            return pulp.lpSum(v for (o2, s), v in x.items() if o2 == op and s + k - 1 <= last)
        for r, (ids, tab) in SUBSETS.items():
            for t in range(2027, YEARS[-1] + 1):
                idx = indice_interdit(t)
                z = {S: pulp.LpVariable(f"z_{r}_{t}_{'_'.join(S) or 'none'}".replace("-", "_"), cat="Binary") for S in tab}
                p += pulp.lpSum(z.values()) == 1
                for op in ids:
                    p += pulp.lpSum(z[S] for S in tab if op in S) == done_by(op, t - 1)
                b = pulp.lpSum(tab[S][idx] * z[S] for S in tab)
                breach.append(b); euros.append(b * TAUX_ROTATION[r] * LOYER_ANNUEL)
    if mode == "conformite":
        p.setObjective(-pulp.lpSum(breach)); p.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=DELAI_SOLVEUR)); statuts.append(pulp.LpStatus[p.status])
        m1 = round(pulp.value(pulp.lpSum(breach))); p += pulp.lpSum(breach) <= m1; p.setObjective(obj)
    elif mode == "monetise":
        p.setObjective(obj - pulp.lpSum(euros) / mu)
    else:
        p.setObjective(obj)
    p.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=DELAI_SOLVEUR)); statuts.append(pulp.LpStatus[p.status])
    return {op: s for (op, s), v in x.items() if v.value() and v.value() > 0.5}, " puis ".join(statuts)

def mesures(nom, start, sc, statut=""):
    m = dict(plan=nom, statut_solveur=statut)
    depense = {t: 0 for t in YEARS}
    for op, s in start.items():
        k = years_needed(COST[op])
        for t in range(s, s + k):
            depense[t] += COST[op] / k
    for t in YEARS[:6]:
        m[f"depense_{t}"] = round(depense[t])
    for y in [2026, 2028, 2031, 2034]:
        labs, mwh = simulate(start, y)
        m[f"G_1er_janvier_{y}"] = int((labs == "G").sum()); m[f"F_1er_janvier_{y}"] = int((labs == "F").sum()); m[f"E_1er_janvier_{y}"] = int((labs == "E").sum()); m[f"mwhep_economises_par_an_{y}"] = round(mwh)
    bd, eur = 0, 0.0
    for t in range(2027, 2036):
        labs, _ = simulate(start, t)
        cls = [["G"], ["F", "G"], ["E", "F", "G"]][indice_interdit(t)]
        br = labs.isin(cls)
        bd += int(br.sum()); eur += sum(TAUX_ROTATION[r] * LOYER_ANNUEL for r in lgt.residence_id[br.values])
    m["logements_annees_en_infraction_2027_2035"] = bd
    m["loyers_perdus_estimes_eur"] = round(eur)
    m["points_de_score_actualises"] = round(sum(sc[o] * (1 - 0.08 * (s - 2026)) - 2.0 * abs(s - ops_idx.loc[o, "annee_souhaitee"]) for o, s in start.items()), 1)
    m["retard_moyen_vs_souhait_annees"] = round(np.mean([s - ops_idx.loc[o, "annee_souhaitee"] for o, s in start.items()]), 2)
    m["operations_lancees_avant_2032"] = sum(1 for s in start.values() if s <= 2031)
    return m

classement = []
poids_effectifs = []
scores = {}
for nom, w in SCEN.items():
    sc = score(w); scores[nom] = sc
    en[f"score_{nom}"] = sc.round(1)
    en[f"rang_{nom}"] = sc.rank(ascending=False, method="min").astype(int)
    eff = {k: w[k] * en[k].mean() / 10 for k in w}; tot = sum(eff.values())
    for k in w:
        poids_effectifs.append(dict(scenario=nom, critere=k, poids_annonce=w[k], contribution_moyenne=round(eff[k], 2), poids_effectif_pct=round(100 * eff[k] / tot, 1)))
sc_base = dict(zip(OPS, scores["base"]))
plans, comparaison = {}, []
fifo = place(list(en.sort_values("rang_actuel_chronologique").operation_id)); plans["fifo_avec_remplissage"] = fifo; comparaison.append(mesures("fifo_avec_remplissage", fifo, sc_base, "sans solveur"))
st, statut = ilp(sc_base); plans["score_seul"] = st; comparaison.append(mesures("score_seul", st, sc_base, statut))
st, statut = ilp(sc_base, mode="conformite"); plans["conformite_d_abord"] = st; comparaison.append(mesures("conformite_d_abord", st, sc_base, statut))
for mu in (250, 500, 1000, 2000):
    st, statut = ilp(sc_base, mode="monetise", mu=mu); plans[f"monetise_{mu}_eur_par_point"] = st; comparaison.append(mesures(f"monetise_{mu}_eur_par_point", st, sc_base, statut))
    print("monétisé", mu, statut, flush=True)
st, statut = ilp(dict(zip(OPS, scores["commanditaire"])), mode="monetise", mu=EURO_PAR_POINT); plans["commanditaire_monetise_1000"] = st; comparaison.append(mesures("commanditaire_monetise_1000", st, dict(zip(OPS, scores["commanditaire"])), statut))
RECOMMANDE = plans[f"monetise_{EURO_PAR_POINT}_eur_par_point"]
en["annee_debut_recommandee"] = en.operation_id.map(RECOMMANDE)
en["annees_de_travaux"] = en.cout_estime_ttc.map(years_needed)
for nom, st in plans.items():
    en[f"annee_debut_{nom}"] = en.operation_id.map(st)

en.to_csv(f"{OUT}/operations_enrichies.csv", index=False)
cols = ["operation_id", "residence_id", "type_operation", "cout_estime_ttc", "annee_souhaitee", "rang_actuel_chronologique", "c_reg", "c_energy", "c_maint", "c_tenant", "c_eol", "c_energy_abs", "c_cost"] + [f"score_{n}" for n in SCEN] + [f"rang_{n}" for n in SCEN] + (["pannes_attendues_par_an_defi1"] if RISQUE is not None else []) + ["annee_debut_recommandee", "annees_de_travaux", "alertes_donnees"]
cl = en[cols].copy()
for c in ["c_reg", "c_energy", "c_maint", "c_tenant", "c_eol", "c_energy_abs", "c_cost"]:
    cl[c] = cl[c].round(2)
cl.sort_values("rang_base").to_csv(f"{OUT}/classement_operations.csv", index=False)
pd.DataFrame(poids_effectifs).to_csv(f"{OUT}/poids_effectifs.csv", index=False)
pd.DataFrame(comparaison).to_csv(f"{OUT}/plans_comparaison.csv", index=False)
pl = en[["operation_id", "residence_id", "type_operation", "cout_estime_ttc", "annee_souhaitee", "annee_debut_recommandee", "annees_de_travaux", "score_base", "rang_base"]].copy()
pl["cout_par_an"] = (pl.cout_estime_ttc / pl.annees_de_travaux).round()
pl["ecart_vs_souhait"] = pl.annee_debut_recommandee - pl.annee_souhaitee
pl.sort_values(["annee_debut_recommandee", "rang_base"]).to_csv(f"{OUT}/plan_recommande.csv", index=False)
pd.DataFrame({k: pd.Series(v) for k, v in plans.items()}).to_csv(f"{OUT}/plans_tous.csv")

pd.set_option("display.width", 300); pd.set_option("display.max_columns", 80); pd.set_option("display.max_rows", 200)
print("écarts d'étiquette recalculée :", LABEL_MISMATCH)
print(pd.DataFrame(poids_effectifs).pivot(index="critere", columns="scenario", values="poids_effectif_pct").round(1).to_string())
print(cl.sort_values("rang_base")[["operation_id", "type_operation", "score_base", "rang_base", "rang_commanditaire", "rang_reglementaire_d_abord", "rang_cout_d_abord", "rang_locataire_d_abord"] + (["pannes_attendues_par_an_defi1"] if RISQUE is not None else []) + ["annee_debut_recommandee"]].to_string(index=False))
print(pd.DataFrame(comparaison).T.to_string())
