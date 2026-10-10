import pandas as pd
import numpy as np
from datetime import timedelta

# ==========================================
# 1. CHARGEMENT ET NETTOYAGE DES DONNÉES
# ==========================================
def load_data(agents_file, postes_file, coupures_file):
    df_agents = pd.read_excel(agents_file)
    df_postes = pd.read_excel(postes_file)
    df_coupures = pd.read_excel(coupures_file)

    # Nettoyage Coupures
    df_coupures['dureeDepannage'] = df_coupures['dureeDepannage'].str.replace('h', '').astype(int)
    df_coupures['dateHeureIncident'] = pd.to_datetime(df_coupures['dateHeureIncident'])

    # Jointure pour récupérer les coordonnées L93 et les clients
    df_incidents = df_coupures.merge(df_postes, on='id_poste', how='left')
    df_incidents['nb_clients_sensibles'] = df_incidents['poste_avec_client_sensible']
    
    # Nettoyage basique des agents (génère des techniciens individuels basés sur 'nb_equipes')
    # Pour la démo, on simule des coordonnées L93 pour les sites d'agents basés sur une moyenne
    mean_x, mean_y = df_postes['x_l93'].mean(), df_postes['y_l93'].mean()
    techniciens = []
    tech_id = 0
    for _, row in df_agents.iterrows():
        for _ in range(row['nb_equipes']):
            techniciens.append({
                'id_tech': f"TECH_{tech_id}",
                'id_site_initial': row['id_site'],
                'x_site': mean_x + np.random.randint(-50000, 50000), # Simulé pour l'exemple
                'y_site': mean_y + np.random.randint(-50000, 50000),
                'available_at': df_incidents['dateHeureIncident'].min(), # Dispo dès le début
                'current_x': mean_x,
                'current_y': mean_y
            })
            tech_id += 1
            
    df_techs = pd.DataFrame(techniciens)
    return df_techs, df_incidents

# ==========================================
# 2. FONCTIONS UTILITAIRES
# ==========================================
def calcul_temps_trajet(x1, y1, x2, y2, vitesse_kmh=50):
    """Retourne un timedelta correspondant au temps de trajet en ligne droite"""
    distance_m = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    distance_km = distance_m / 1000.0
    heures = distance_km / vitesse_kmh
    return timedelta(hours=heures)

# ==========================================
# 3. L'ALGORITHME DE RÉFÉRENCE (GLOUTON)
# ==========================================
class GreedyAlgorithm:
    def dispatch(self, current_time, available_techs, active_incidents):
        assignments = []
        
        # Trier les incidents: priorité aux sensibles, puis par nombre de clients (décroissant)
        active_incidents = sorted(
            active_incidents, 
            key=lambda x: (x['nb_clients_sensibles'], x['nb_clients']), 
            reverse=True
        )
        
        for incident in active_incidents:
            if available_techs.empty:
                break # Plus de techniciens dispos
                
            # Trouver le tech le plus proche
            available_techs['dist'] = np.sqrt(
                (available_techs['current_x'] - incident['x_l93'])**2 + 
                (available_techs['current_y'] - incident['y_l93'])**2
            )
            available_techs = available_techs.sort_values('dist')
            
            for idx, tech in available_techs.iterrows():
                # Vérification de la contrainte des 12h
                trajet_aller = calcul_temps_trajet(tech['current_x'], tech['current_y'], incident['x_l93'], incident['y_l93'])
                temps_repa = timedelta(hours=incident['dureeDepannage'])
                temps_restauration = timedelta(minutes=30)
                trajet_retour = calcul_temps_trajet(incident['x_l93'], incident['y_l93'], tech['x_site'], tech['y_site'])
                
                duree_totale_mission = trajet_aller + temps_repa + temps_restauration + trajet_retour
                
                # Si la mission fait moins de 12h, on assigne
                if duree_totale_mission <= timedelta(hours=12):
                    assignments.append({
                        'id_tech': tech['id_tech'],
                        'id_incident': incident['id_incident'],
                        'trajet_aller': trajet_aller,
                        'temps_repa': temps_repa,
                        'trajet_retour': trajet_retour,
                        'duree_totale': duree_totale_mission,
                        'incident_idx': incident.name,
                        'tech_idx': idx
                    })
                    # Retirer le tech des dispos pour cette boucle
                    available_techs = available_techs.drop(idx)
                    break 
                    
        return assignments

# ==========================================
# 4. LE MOTEUR DE SIMULATION
# ==========================================
class Simulation:
    def __init__(self, df_techs, df_incidents, algo):
        self.techs = df_techs.copy()
        self.incidents = df_incidents.copy()
        self.incidents['resolved'] = False
        self.algo = algo
        
        self.current_time = self.incidents['dateHeureIncident'].min()
        self.end_time = self.incidents['dateHeureIncident'].max() + timedelta(days=5)
        
        # KPIs
        self.kpi_sensible = 0.0 # nb_clients_sensibles * heures_attente
        self.kpi_lambda = 0.0   # nb_clients_lambdas * heures_attente

    def run(self):
        print(f"Début de la simulation à {self.current_time}")
        pas_de_temps = timedelta(minutes=30)
        
        while self.current_time < self.end_time:
            # 1. Filtrer incidents actifs non résolus
            mask_actifs = (self.incidents['dateHeureIncident'] <= self.current_time) & (~self.incidents['resolved'])
            incidents_actifs = self.incidents[mask_actifs].to_dict('records')
            
            # 2. Filtrer techs disponibles
            mask_dispos = self.techs['available_at'] <= self.current_time
            techs_dispos = self.techs[mask_dispos].copy()
            
            # 3. Lancer l'algo si besoin
            if incidents_actifs and not techs_dispos.empty:
                assignments = self.algo.dispatch(self.current_time, techs_dispos, incidents_actifs)
                
                for assign in assignments:
                    # Mettre à jour l'incident
                    idx_inc = assign['incident_idx']
                    self.incidents.at[idx_inc, 'resolved'] = True
                    
                    # Calcul du temps d'attente total (de l'apparition jusqu'à la fin de la réparation)
                    heure_resolution = self.current_time + assign['trajet_aller'] + assign['temps_repa']
                    temps_attente = heure_resolution - self.incidents.at[idx_inc, 'dateHeureIncident']
                    heures_attente = temps_attente.total_seconds() / 3600.0
                    
                    # Mise à jour des KPI
                    nb_sensibles = self.incidents.at[idx_inc, 'nb_clients_sensibles']
                    nb_lambdas = self.incidents.at[idx_inc, 'nb_clients'] - nb_sensibles
                    
                    self.kpi_sensible += nb_sensibles * heures_attente
                    self.kpi_lambda += nb_lambdas * heures_attente
                    
                    # Mettre à jour le technicien (bloqué jusqu'à son retour + 11h de repos)
                    idx_tech = assign['tech_idx']
                    repos_obligatoire = timedelta(hours=11)
                    heure_dispo_future = self.current_time + assign['duree_totale'] + repos_obligatoire
                    
                    self.techs.at[idx_tech, 'available_at'] = heure_dispo_future
                    self.techs.at[idx_tech, 'current_x'] = self.techs.at[idx_tech, 'x_site']
                    self.techs.at[idx_tech, 'current_y'] = self.techs.at[idx_tech, 'y_site']

            self.current_time += pas_de_temps
            
            # Condition d'arrêt anticipée si tout est résolu
            if self.incidents['resolved'].all():
                break
                
        print("Simulation terminée !")
        print(f"KPI Clients Sensibles : {self.kpi_sensible:,.2f} heures d'attente cumulées")
        print(f"KPI Clients Lambdas   : {self.kpi_lambda:,.2f} heures d'attente cumulées")

# ==========================================
# EXECUTION
# ==========================================
if __name__ == "__main__":
    # Assure-toi que les fichiers sont dans le même dossier que ce script
    df_techs, df_incidents = load_data("Copie de agents_v2.xlsx", "Copie de poste_v2.xlsx", "coupures_v2_100_crises.xlsx")
    
    algo = GreedyAlgorithm()
    sim = Simulation(df_techs, df_incidents, algo)
    sim.run()
