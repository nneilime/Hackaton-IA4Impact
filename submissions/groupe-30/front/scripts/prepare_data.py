"""Prépare les données de consultation locales. Aucun entraînement, aucune API."""
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import csv
import json
import re
import shutil

FRONT = Path(__file__).resolve().parents[1]
ROOT = FRONT.parent
KIT = ROOT / 'DATA 2 _le kit étudiants' / 'BatIA_Kit_Hackathon'
OUT = FRONT / 'tests' / 'fixtures'
END = datetime(2026, 1, 1)


def rows(name):
    with (KIT / 'donnees' / name).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    equipments = rows('04_equipements.csv')
    buildings = {r['batiment_id']: r for r in rows('02_batiments.csv')}
    residences = rows('01_residences.csv')
    providers = rows('09_prestataires.csv')
    events = defaultdict(list)
    for r in rows('06_interventions.csv'):
        when = datetime.fromisoformat(r['date_intervention'])
        if when >= END:
            continue
        events[r['equipement_id']].append({
            'id': r['intervention_id'], 'date': r['date_intervention'].replace(' ', 'T'),
            'type': r['type_intervention'], 'symptom': r['symptome'], 'severity': r['gravite'],
            'result': r['resultat'], 'comment': r['commentaire_technicien'],
            'providerId': r['prestataire_id'], 'requestId': r['demande_id_liee'] or None,
        })
    requests = []
    for r in rows('05_demandes_locataires.csv'):
        if datetime.fromisoformat(r['date_creation']) < END:
            requests.append({
                'id': r['demande_id'], 'date': r['date_creation'].replace(' ', 'T'),
                'closedAt': r['date_cloture'].replace(' ', 'T') or None,
                'housingId': r['logement_id'], 'buildingId': r['batiment_id'],
                'parts': r['parties'], 'motif': r['motif'], 'subject': r['objet'], 'text': r['texte_demande'],
            })
    observations = defaultdict(list)
    for quarter in (2, 3, 4):
        text_path = ROOT / 'analyses' / 'sources_lisibles' / f'Rapport_activite_T{quarter}_2025_FICTIF.md'
        text = text_path.read_text(encoding='utf-8')
        for match in re.finditer(r'•\s+([^\n]+?\((EQP-\d+)\)\s*:[\s\S]*?)(?=\n•|\n## Page|\Z)', text):
            preceding = text[:match.start()]
            pages = re.findall(r'## Page (\d+)', preceding)
            observations[match.group(2)].append({
                'id': f'report-T{quarter}-{match.group(2)}', 'quarter': quarter,
                'page': int(pages[-1]) if pages else None,
                'text': ' '.join(match.group(1).split()),
                'url': f'/sources/Rapport_activite_T{quarter}_2025_FICTIF.pdf',
            })
    RESIDENCE_GEO = {
        'RES-A': {'lat': 43.5615, 'lng': 1.4642, 'district': 'Toulouse - Rangueil / Pech-David'},
        'RES-B': {'lat': 43.6348, 'lng': 1.3862, 'district': 'Blagnac - Grand Noble'},
        'RES-C': {'lat': 43.5746, 'lng': 1.4021, 'district': 'Toulouse - Reynerie / Mirail'},
        'RES-D': {'lat': 43.6264, 'lng': 1.4883, 'district': 'Balma - Gramont'},
        'RES-E': {'lat': 43.5992, 'lng': 1.4115, 'district': 'Toulouse - La Cartoucherie'},
        'RES-F': {'lat': 43.6118, 'lng': 1.3347, 'district': 'Colomiers - Centre'},
        'RES-G': {'lat': 43.5828, 'lng': 1.4446, 'district': 'Toulouse - Saint-Agne / Empalot'},
        'RES-H': {'lat': 43.5442, 'lng': 1.4745, 'district': 'Ramonville-Saint-Agne'},
    }
    housings_raw = rows('03_logements.csv')
    housings_data = []
    housing_dpe_map = {}
    for h in housings_raw:
        housing_dpe_map[h['logement_id']] = h['dpe_etiquette_globale']
        housings_data.append({
            'id': h['logement_id'],
            'buildingId': h['batiment_id'],
            'residenceId': h['residence_id'],
            'typology': h['typologie'],
            'area': float(h['surface_habitable_m2']) if h['surface_habitable_m2'] else 0.0,
            'floor': int(h['etage']) if h['etage'] else 0,
            'dpeEnergy': h['dpe_etiquette_energie'],
            'dpeGes': h['dpe_etiquette_ges'],
            'dpeGlobal': h['dpe_etiquette_globale'],
            'consoEp': float(h['dpe_conso_ep_kwh_m2_an']) if h['dpe_conso_ep_kwh_m2_an'] else 0.0,
            'ges': float(h['dpe_ges_kgco2_m2_an']) if h['dpe_ges_kgco2_m2_an'] else 0.0,
            'tenantTurnover': int(h['nb_changements_locataire_2018_2025']) if h['nb_changements_locataire_2018_2025'] else 0,
            'occupancyStatus': h['statut_occupation'],
        })

    residences_data = []
    for r in residences:
        geo = RESIDENCE_GEO.get(r['residence_id'], {'lat': 43.6047, 'lng': 1.4442, 'district': 'Métropole toulousaine'})
        residences_data.append({
            'id': r['residence_id'],
            'name': r['nom'],
            'housingCount': int(r['nb_logements']),
            'buildingCount': int(r['nb_batiments']),
            'constructionYear': int(r['annee_construction']),
            'energyHeating': r['energie_chauffage'],
            'heatingType': r['type_chauffage'],
            'heatingGenerator': r['generateur_chauffage'],
            'ecsProduction': r['production_ecs'],
            'ventilation': r['ventilation'],
            'dpeTag': r['etiquette_dpe_majoritaire'],
            'consoEp': float(r['conso_ep_moyenne_kwh_m2_an']),
            'ges': float(r['ges_moyen_kgco2_m2_an']),
            'lat': geo['lat'],
            'lng': geo['lng'],
            'district': geo['district'],
        })

    catalog = []
    scores = {}
    for r in equipments:
        history = sorted(events[r['equipement_id']], key=lambda e: (e['date'], e['id']), reverse=True)
        pose = datetime.fromisoformat(r['date_pose']) if r['date_pose'] else None
        replacements = [e for e in history if e['type'] == 'Remplacement' and e['date'][:10] == r['date_pose']]
        cycle_start = replacements[0]['date'] if replacements else (r['date_pose'] + 'T00:00:00' if pose else None)
        current = [e for e in history if cycle_start and e['date'] >= cycle_start]
        recent = [e for e in current if datetime.fromisoformat(e['date']) >= END - timedelta(days=365)]
        age = (END - timedelta(microseconds=1) - pose).total_seconds() / (365.25 * 86400) if pose and pose < END else None
        in_scope = r['dans_perimetre_prediction'] == 'Oui'
        if in_scope and age is not None:
            scores[r['equipement_id']] = age / float(r['duree_vie_reference_ans'])
        note = next((e for e in recent if e['comment'] or e['symptom']), None)
        catalog.append({
            'id': r['equipement_id'], 'family': r['famille'], 'label': r['libelle_famille'],
            'residenceId': r['residence_id'], 'buildingId': r['batiment_id'],
            'housingId': r['logement_id'] or None, 'collective': r['niveau_rattachement'] == 'Bâtiment (parties communes)',
            'housingDpe': housing_dpe_map.get(r['logement_id']) or None,
            'installedAt': r['date_pose'] or None, 'installationOrigin': r['origine_date_pose'],
            'cycleStartedAt': cycle_start, 'ageYears': age, 'referenceLifeYears': int(r['duree_vie_reference_ans']),
            'underContract': r['sous_contrat_entretien'] == 'Oui', 'annualVisit': r['visite_annuelle_prevue'] == 'Oui',
            'providerId': r['prestataire_id'], 'inScope': in_scope,
            'buildingHousingCount': int(buildings[r['batiment_id']]['nb_logements']),
            'recentRepairCount': sum(e['type'] == 'Dépannage' for e in recent),
            'recentAnomalyCount': sum(e['result'] == 'Anomalie constatée' for e in recent),
            'latestObservation': {'text': note['comment'] or note['symptom'], 'date': note['date'], 'id': note['id']} if note else None,
            'needsVerification': age is None or 'hypoth' in r['origine_date_pose'].lower(),
        })
    assert len(catalog) == 4217
    assert sum(e['inScope'] for e in catalog) == 1285
    assert sum(e['inScope'] and e['collective'] for e in catalog) == 45
    assert len(scores) == 1285
    write('catalog.json', {
        'snapshotDate': '2025-12-31', 'equipment': catalog,
        'residences': residences_data,
        'housings': housings_data,
        'providers': [{'id': r['prestataire_id'], 'name': r['nom'], 'domain': r['domaine']} for r in providers],
        'baselineScores': scores,
    })
    write('history.json', {'events': dict(events), 'requests': requests, 'reports': dict(observations)})
    sources = FRONT / 'public' / 'sources'
    sources.mkdir(exist_ok=True)
    for path in (KIT / 'rapports_prestataire').glob('*.pdf'):
        shutil.copyfile(path, sources / path.name)
    brand = FRONT / 'public' / 'brand'
    brand.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'analyses' / 'assets' / 'action-logement-logo.png', brand / 'action-logement-logo.png')
    print(f'Préparation OK : {len(catalog)} équipements, {len(scores)} scores de référence, {sum(map(len, observations.values()))} observations PDF.')


if __name__ == '__main__':
    main()
