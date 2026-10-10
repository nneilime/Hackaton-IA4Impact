"""Gabarits des zones du bordereau CERFA 12278 (S 3404), par famille de mise en page.

Les 15 zones sont celles du cahier des charges. Le corpus contient trois mises en page
(familles) produites par trois logiciels d'établissement différents. Les coordonnées sont
exprimées en pixels dans la résolution de référence de la famille puis NORMALISÉES
(divisées par largeur/hauteur de référence) : le gabarit s'applique ainsi à toute
résolution. Un recalage géométrique (translation) est estimé à partir de lignes d'ancrage
du formulaire avant d'appliquer le gabarit.

Colonnes de tableau : (x0, x1) ; boîtes : (x0, y0, x1, y1).
"""
from __future__ import annotations

TEMPLATES = {
    "F1": {
        "label": "Mise en page 1 (POLYCLINIQUE MAYMARD)",
        "ref_size": (1190, 1684),
        # lignes d'ancrage (y des traits horizontaux longs, x des traits verticaux longs)
        "anchors_h": [180, 284, 360, 548, 809, 865, 1418, 1438, 1530],
        "anchors_v": [19, 589, 111, 458, 552, 134, 187, 838, 1017, 147, 258, 736, 913],
        "fields": {
            "Z1": {"box": (14, 60, 125, 86), "kind": "cerfa_id"},
            "Z2": {"box": (462, 86, 668, 110), "kind": "digits"},
            "Z3": {"box": (782, 102, 905, 123), "kind": "digits"},
            "Z4": {"box": (782, 119, 905, 141), "kind": "digits"},
            "Z5": {"box": (155, 225, 305, 249), "kind": "nir"},
            "ST1": {"box": (458, 519, 592, 538), "kind": "amount"},
            "ST2": {"box": (1048, 519, 1178, 538), "kind": "amount"},
            "ST3": {"box": (1017, 811, 1178, 830), "kind": "amount"},
            "Z8": {"box": (1017, 828, 1178, 846), "kind": "amount"},
            "Z12": {"box": (737, 1419, 912, 1437), "kind": "amount"},
            "Z13": {"box": (168, 1531, 322, 1571), "kind": "amount"},
            "Z15": {"box": (1100, 1612, 1185, 1640), "kind": "cerfa_code"},
        },
        "tables": {
            "Z6a": {"body": (20, 414, 592, 518), "zone": "Z6", "cols": {
                "prestation": (108, 135), "ghs": (134, 181), "montant": (458, 553)}},
            "Z6b": {"body": (610, 414, 1178, 518), "zone": "Z6", "cols": {
                "prestation": (695, 728), "ghs": (727, 773), "montant": (1048, 1148)}},
            "Z7": {"body": (18, 604, 1178, 808), "zone": "Z7", "cols": {
                "prestation": (106, 135), "ghs": (134, 188), "code": (714, 838), "montant": (1017, 1146)}},
            "Z10": {"body": (16, 924, 969, 1417), "zone": "Z10", "cols": {
                "executant": (169, 259), "date": (279, 362), "ghs": (437, 479), "code": (482, 551),
                "quantite": (736, 822), "honoraires": (820, 914)}},
        },
        "signature_boxes": {
            "Z11": [(984, 929 + i * 0, 1176, 1000) for i in range(1)] + [
                (984, 1000, 1176, 1064), (984, 1064, 1176, 1132), (984, 1132, 1176, 1200),
                (984, 1200, 1176, 1268), (984, 1268, 1176, 1334), (984, 1334, 1176, 1404),
                (984, 1404, 1176, 1475)],
            "Z14": [(1034, 1502, 1173, 1572)],
        },
        "signature_number_margin": 14,   # bande gauche portant le numéro imprimé de case
    },
    "F2": {
        "label": "Mise en page 2 (POLYCLINIQUE DU PARC)",
        "ref_size": (1190, 1683),
        "anchors_h": [119, 205, 304, 369, 435, 560, 618, 813, 866, 929, 1402, 1511, 1550],
        "anchors_v": [47, 689, 1148, 157, 200, 465, 553, 707, 998, 1117, 449, 484, 730, 813, 898, 967],
        "fields": {
            "Z1": {"box": (44, 91, 140, 112), "kind": "cerfa_id"},
            "Z2": {"box": (474, 116, 662, 137), "kind": "digits"},
            "Z3": {"box": (788, 133, 885, 147), "kind": "digits"},
            "Z4": {"box": (784, 145, 885, 167), "kind": "digits"},
            "Z5": {"box": (172, 250, 330, 273), "kind": "nir"},
            "ST1": {"box": (465, 535, 593, 549), "kind": "amount"},
            "ST2": {"box": (1027, 535, 1151, 549), "kind": "amount"},
            "ST3": {"box": (997, 815, 1149, 832), "kind": "amount"},
            "Z8": {"box": (997, 830, 1149, 847), "kind": "amount"},
            "Z12": {"box": (730, 1404, 900, 1420), "kind": "amount"},
            "Z13": {"box": (180, 1512, 332, 1549), "kind": "amount"},
            "Z15": {"box": (1092, 1590, 1165, 1614), "kind": "cerfa_code"},
        },
        "tables": {
            "Z6a": {"body": (48, 436, 592, 531), "zone": "Z6", "cols": {
                "prestation": (118, 158), "ghs": (157, 201), "montant": (465, 557)}},
            "Z6b": {"body": (609, 437, 1151, 530), "zone": "Z6", "cols": {
                "prestation": (684, 722), "ghs": (721, 764), "montant": (1026, 1123)}},
            "Z7": {"body": (46, 619, 1149, 812), "zone": "Z7", "cols": {
                "prestation": (118, 157), "ghs": (156, 207), "code": (707, 828), "montant": (998, 1118)}},
            "Z10": {"body": (45, 930, 952, 1401), "zone": "Z10", "cols": {
                "executant": (190, 275), "date": (297, 372), "ghs": (448, 485), "code": (484, 553),
                "quantite": (730, 814), "honoraires": (813, 899)}},
        },
        "signature_boxes": {
            "Z11": [(966, 929, 1147, 994), (966, 994, 1147, 1060), (966, 1060, 1147, 1126),
                    (966, 1126, 1147, 1191), (966, 1191, 1147, 1257), (966, 1257, 1147, 1322),
                    (966, 1322, 1147, 1388), (966, 1388, 1147, 1457)],
            "Z14": [(967, 1511, 1145, 1549)],
        },
        "signature_number_margin": 10,
    },
    "F3": {
        "label": "Mise en page 3 (E.C.H.O PAV. MONTFORT)",
        "ref_size": (1684, 2382),
        "anchors_h": [132, 255, 270, 402, 497, 594, 776, 860, 1146, 1224, 1314, 2007, 2035, 2166, 2223],
        "anchors_v": [26, 980, 1663, 191, 255, 649, 780, 1008, 1186, 1439, 1617, 625, 677, 1042, 1164, 1291, 1370],
        "fields": {
            "Z1": {"box": (36, 92, 160, 124), "kind": "cerfa_id"},
            "Z2": {"box": (655, 138, 945, 166), "kind": "digits"},
            "Z3": {"box": (1125, 152, 1300, 180), "kind": "digits"},
            "Z4": {"box": (1125, 178, 1300, 206), "kind": "digits"},
            "Z5": {"box": (222, 326, 420, 354), "kind": "nir"},
            "ST1": {"box": (649, 740, 838, 759), "kind": "amount"},
            "ST2": {"box": (1484, 740, 1667, 759), "kind": "amount"},
            "ST3": {"box": (1439, 1150, 1666, 1174), "kind": "amount"},
            "Z8": {"box": (1439, 1172, 1666, 1195), "kind": "amount"},
            "Z12": {"box": (1164, 2010, 1294, 2032), "kind": "amount"},
            "Z13": {"box": (232, 2167, 462, 2222), "kind": "amount"},
            "Z15": {"box": (1580, 2288, 1684, 2330), "kind": "cerfa_code"},
        },
        "tables": {
            "Z6a": {"body": (29, 597, 837, 732), "zone": "Z6", "cols": {
                "prestation": (156, 192), "ghs": (191, 256), "montant": (649, 781)}},
            "Z6b": {"body": (863, 597, 1667, 732), "zone": "Z6", "cols": {
                "prestation": (986, 1029), "ghs": (1028, 1092), "montant": (1481, 1625)}},
            "Z7": {"body": (26, 861, 1665, 1145), "zone": "Z7", "cols": {
                "prestation": (155, 191), "ghs": (190, 266), "code": (1008, 1187), "montant": (1439, 1618)}},
            "Z10": {"body": (24, 1315, 1371, 2006), "zone": "Z10", "cols": {
                "executant": (241, 367), "date": (399, 509), "ghs": (624, 678), "code": (677, 779),
                "quantite": (1042, 1165), "honoraires": (1164, 1292)}},
        },
        "signature_boxes": {
            "Z11": [(1393, 1313, 1661, 1411), (1393, 1411, 1661, 1506), (1393, 1506, 1661, 1601),
                    (1393, 1601, 1661, 1697), (1393, 1697, 1661, 1794), (1393, 1794, 1661, 1889),
                    (1393, 1889, 1661, 1986), (1393, 1986, 1661, 2087)],
            "Z14": [(1380, 2095, 1684, 2260)],
        },
        "signature_number_margin": 16,
    },
}

ZONE_LABELS = {
    "Z1": "Zone 1 — n° d'identification du formulaire (CERFA)",
    "Z2": "Zone 2 — n° FINESS de l'établissement",
    "Z3": "Zone 3 — N° LOT",
    "Z4": "Zone 4 — N° FACTURE",
    "Z5": "Zone 5 — n° d'immatriculation de l'assuré",
    "Z6": "Zone 6 — prestations (frais de structure et de soins)",
    "Z7": "Zone 7 — prestations LPP / pharmacie / médicaments",
    "Z8": "Zone 8 — sous-total 1+2+3",
    "Z9": "Zone 9 — n° d'identification de l'exécutant",
    "Z10": "Zone 10 — actes effectués (honoraires)",
    "Z11": "Zone 11 — signatures des praticiens",
    "Z12": "Zone 12 — sous-total 4 (honoraires)",
    "Z13": "Zone 13 — montant total",
    "Z14": "Zone 14 — signature du directeur de l'établissement",
    "Z15": "Zone 15 — code CERFA",
}
