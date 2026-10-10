create schema if not exists prive;
grant usage on schema prive to authenticated,batia_api;
alter function public.est_membre() set schema prive;
alter function public.est_admin() set schema prive;
create or replace function public.importer_lot(p_lot jsonb,p_revision bigint,p_fichiers jsonb default '[]') returns jsonb
language plpgsql security definer set search_path=public,pg_temp as $$
declare ajouts integer; modifications integer; total_ajouts integer:=0; total_modifications integer:=0;
 modele boolean:=false; bilan jsonb:='{}'; nouvelle_revision bigint; ancien bigint;
begin
 if auth.uid() is null then
  if session_user not in ('postgres','supabase_admin') then raise exception 'Accès administrateur requis'; end if;
 elsif not prive.est_admin() then raise exception 'Accès administrateur requis'; end if;
 if exists(select 1 from jsonb_object_keys(p_lot) k where k not in ('residences','batiments','logements','equipements','demandes','interventions','commandes','investissements','prestataires','metiers','familles','motifs','seuils_dpe','dictionnaire','hypotheses','documentation')) then raise exception 'Table inconnue'; end if;
 perform pg_advisory_xact_lock(821906);
 select coalesce(max(id),0) into ancien from public.imports where statut='applique' and nb_ajouts+nb_modifications>0;
 if p_revision<>ancien then raise exception 'Aperçu périmé : vérifier à nouveau le lot' using errcode='40001'; end if;
 set constraints all deferred;
 
 if p_lot ? 'residences' then
  select count(*) filter(where d.residence_id is null),count(*) filter(where d.residence_id is not null and (d.nom is distinct from s.nom or d.localisation is distinct from s.localisation or d.annee_construction is distinct from s.annee_construction or d.nb_batiments is distinct from s.nb_batiments or d.nb_logements is distinct from s.nb_logements or d.surface_habitable_totale_m2 is distinct from s.surface_habitable_totale_m2 or d.ascenseur is distinct from s.ascenseur or d.energie_chauffage is distinct from s.energie_chauffage or d.type_chauffage is distinct from s.type_chauffage or d.generateur_chauffage is distinct from s.generateur_chauffage or d.production_ecs is distinct from s.production_ecs or d.ventilation is distinct from s.ventilation or d.etiquette_dpe_majoritaire is distinct from s.etiquette_dpe_majoritaire or d.conso_ep_moyenne_kwh_m2_an is distinct from s.conso_ep_moyenne_kwh_m2_an or d.ges_moyen_kgco2_m2_an is distinct from s.ges_moyen_kgco2_m2_an))
  into ajouts,modifications from jsonb_populate_recordset(null::public.residences,p_lot->'residences') s left join public.residences d on d.residence_id=s.residence_id;
  insert into public.residences(residence_id,nom,localisation,annee_construction,nb_batiments,nb_logements,surface_habitable_totale_m2,ascenseur,energie_chauffage,type_chauffage,generateur_chauffage,production_ecs,ventilation,etiquette_dpe_majoritaire,conso_ep_moyenne_kwh_m2_an,ges_moyen_kgco2_m2_an) select residence_id,nom,localisation,annee_construction,nb_batiments,nb_logements,surface_habitable_totale_m2,ascenseur,energie_chauffage,type_chauffage,generateur_chauffage,production_ecs,ventilation,etiquette_dpe_majoritaire,conso_ep_moyenne_kwh_m2_an,ges_moyen_kgco2_m2_an from jsonb_populate_recordset(null::public.residences,p_lot->'residences')
  on conflict(residence_id) do update set nom=excluded.nom,localisation=excluded.localisation,annee_construction=excluded.annee_construction,nb_batiments=excluded.nb_batiments,nb_logements=excluded.nb_logements,surface_habitable_totale_m2=excluded.surface_habitable_totale_m2,ascenseur=excluded.ascenseur,energie_chauffage=excluded.energie_chauffage,type_chauffage=excluded.type_chauffage,generateur_chauffage=excluded.generateur_chauffage,production_ecs=excluded.production_ecs,ventilation=excluded.ventilation,etiquette_dpe_majoritaire=excluded.etiquette_dpe_majoritaire,conso_ep_moyenne_kwh_m2_an=excluded.conso_ep_moyenne_kwh_m2_an,ges_moyen_kgco2_m2_an=excluded.ges_moyen_kgco2_m2_an where residences.nom is distinct from excluded.nom or residences.localisation is distinct from excluded.localisation or residences.annee_construction is distinct from excluded.annee_construction or residences.nb_batiments is distinct from excluded.nb_batiments or residences.nb_logements is distinct from excluded.nb_logements or residences.surface_habitable_totale_m2 is distinct from excluded.surface_habitable_totale_m2 or residences.ascenseur is distinct from excluded.ascenseur or residences.energie_chauffage is distinct from excluded.energie_chauffage or residences.type_chauffage is distinct from excluded.type_chauffage or residences.generateur_chauffage is distinct from excluded.generateur_chauffage or residences.production_ecs is distinct from excluded.production_ecs or residences.ventilation is distinct from excluded.ventilation or residences.etiquette_dpe_majoritaire is distinct from excluded.etiquette_dpe_majoritaire or residences.conso_ep_moyenne_kwh_m2_an is distinct from excluded.conso_ep_moyenne_kwh_m2_an or residences.ges_moyen_kgco2_m2_an is distinct from excluded.ges_moyen_kgco2_m2_an;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'residences' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('residences',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'batiments' then
  select count(*) filter(where d.batiment_id is null),count(*) filter(where d.batiment_id is not null and (d.residence_id is distinct from s.residence_id or d.nb_niveaux is distinct from s.nb_niveaux or d.nb_logements is distinct from s.nb_logements or d.ascenseur is distinct from s.ascenseur))
  into ajouts,modifications from jsonb_populate_recordset(null::public.batiments,p_lot->'batiments') s left join public.batiments d on d.batiment_id=s.batiment_id;
  insert into public.batiments(batiment_id,residence_id,nb_niveaux,nb_logements,ascenseur) select batiment_id,residence_id,nb_niveaux,nb_logements,ascenseur from jsonb_populate_recordset(null::public.batiments,p_lot->'batiments')
  on conflict(batiment_id) do update set residence_id=excluded.residence_id,nb_niveaux=excluded.nb_niveaux,nb_logements=excluded.nb_logements,ascenseur=excluded.ascenseur where batiments.residence_id is distinct from excluded.residence_id or batiments.nb_niveaux is distinct from excluded.nb_niveaux or batiments.nb_logements is distinct from excluded.nb_logements or batiments.ascenseur is distinct from excluded.ascenseur;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'batiments' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('batiments',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'logements' then
  select count(*) filter(where d.logement_id is null),count(*) filter(where d.logement_id is not null and (d.batiment_id is distinct from s.batiment_id or d.residence_id is distinct from s.residence_id or d.typologie is distinct from s.typologie or d.surface_habitable_m2 is distinct from s.surface_habitable_m2 or d.etage is distinct from s.etage or d.dpe_methode is distinct from s.dpe_methode or d.dpe_date is distinct from s.dpe_date or d.dpe_conso_ep_kwh_m2_an is distinct from s.dpe_conso_ep_kwh_m2_an or d.dpe_ges_kgco2_m2_an is distinct from s.dpe_ges_kgco2_m2_an or d.dpe_etiquette_energie is distinct from s.dpe_etiquette_energie or d.dpe_etiquette_ges is distinct from s.dpe_etiquette_ges or d.dpe_etiquette_globale is distinct from s.dpe_etiquette_globale or d.nb_changements_locataire_2018_2025 is distinct from s.nb_changements_locataire_2018_2025 or d.date_entree_locataire_actuel is distinct from s.date_entree_locataire_actuel or d.statut_occupation is distinct from s.statut_occupation))
  into ajouts,modifications from jsonb_populate_recordset(null::public.logements,p_lot->'logements') s left join public.logements d on d.logement_id=s.logement_id;
  insert into public.logements(logement_id,batiment_id,residence_id,typologie,surface_habitable_m2,etage,dpe_methode,dpe_date,dpe_conso_ep_kwh_m2_an,dpe_ges_kgco2_m2_an,dpe_etiquette_energie,dpe_etiquette_ges,dpe_etiquette_globale,nb_changements_locataire_2018_2025,date_entree_locataire_actuel,statut_occupation) select logement_id,batiment_id,residence_id,typologie,surface_habitable_m2,etage,dpe_methode,dpe_date,dpe_conso_ep_kwh_m2_an,dpe_ges_kgco2_m2_an,dpe_etiquette_energie,dpe_etiquette_ges,dpe_etiquette_globale,nb_changements_locataire_2018_2025,date_entree_locataire_actuel,statut_occupation from jsonb_populate_recordset(null::public.logements,p_lot->'logements')
  on conflict(logement_id) do update set batiment_id=excluded.batiment_id,residence_id=excluded.residence_id,typologie=excluded.typologie,surface_habitable_m2=excluded.surface_habitable_m2,etage=excluded.etage,dpe_methode=excluded.dpe_methode,dpe_date=excluded.dpe_date,dpe_conso_ep_kwh_m2_an=excluded.dpe_conso_ep_kwh_m2_an,dpe_ges_kgco2_m2_an=excluded.dpe_ges_kgco2_m2_an,dpe_etiquette_energie=excluded.dpe_etiquette_energie,dpe_etiquette_ges=excluded.dpe_etiquette_ges,dpe_etiquette_globale=excluded.dpe_etiquette_globale,nb_changements_locataire_2018_2025=excluded.nb_changements_locataire_2018_2025,date_entree_locataire_actuel=excluded.date_entree_locataire_actuel,statut_occupation=excluded.statut_occupation where logements.batiment_id is distinct from excluded.batiment_id or logements.residence_id is distinct from excluded.residence_id or logements.typologie is distinct from excluded.typologie or logements.surface_habitable_m2 is distinct from excluded.surface_habitable_m2 or logements.etage is distinct from excluded.etage or logements.dpe_methode is distinct from excluded.dpe_methode or logements.dpe_date is distinct from excluded.dpe_date or logements.dpe_conso_ep_kwh_m2_an is distinct from excluded.dpe_conso_ep_kwh_m2_an or logements.dpe_ges_kgco2_m2_an is distinct from excluded.dpe_ges_kgco2_m2_an or logements.dpe_etiquette_energie is distinct from excluded.dpe_etiquette_energie or logements.dpe_etiquette_ges is distinct from excluded.dpe_etiquette_ges or logements.dpe_etiquette_globale is distinct from excluded.dpe_etiquette_globale or logements.nb_changements_locataire_2018_2025 is distinct from excluded.nb_changements_locataire_2018_2025 or logements.date_entree_locataire_actuel is distinct from excluded.date_entree_locataire_actuel or logements.statut_occupation is distinct from excluded.statut_occupation;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'logements' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('logements',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'equipements' then
  select count(*) filter(where d.equipement_id is null),count(*) filter(where d.equipement_id is not null and (d.famille is distinct from s.famille or d.libelle_famille is distinct from s.libelle_famille or d.niveau_rattachement is distinct from s.niveau_rattachement or d.residence_id is distinct from s.residence_id or d.batiment_id is distinct from s.batiment_id or d.logement_id is distinct from s.logement_id or d.date_pose is distinct from s.date_pose or d.origine_date_pose is distinct from s.origine_date_pose or d.date_pose_precedente is distinct from s.date_pose_precedente or d.nb_remplacements_2018_2025 is distinct from s.nb_remplacements_2018_2025 or d.duree_vie_reference_ans is distinct from s.duree_vie_reference_ans or d.sous_contrat_entretien is distinct from s.sous_contrat_entretien or d.visite_annuelle_prevue is distinct from s.visite_annuelle_prevue or d.code_metier is distinct from s.code_metier or d.prestataire_id is distinct from s.prestataire_id or d.dans_perimetre_prediction is distinct from s.dans_perimetre_prediction))
  into ajouts,modifications from jsonb_populate_recordset(null::public.equipements,p_lot->'equipements') s left join public.equipements d on d.equipement_id=s.equipement_id;
  insert into public.equipements(equipement_id,famille,libelle_famille,niveau_rattachement,residence_id,batiment_id,logement_id,date_pose,origine_date_pose,date_pose_precedente,nb_remplacements_2018_2025,duree_vie_reference_ans,sous_contrat_entretien,visite_annuelle_prevue,code_metier,prestataire_id,dans_perimetre_prediction) select equipement_id,famille,libelle_famille,niveau_rattachement,residence_id,batiment_id,logement_id,date_pose,origine_date_pose,date_pose_precedente,nb_remplacements_2018_2025,duree_vie_reference_ans,sous_contrat_entretien,visite_annuelle_prevue,code_metier,prestataire_id,dans_perimetre_prediction from jsonb_populate_recordset(null::public.equipements,p_lot->'equipements')
  on conflict(equipement_id) do update set famille=excluded.famille,libelle_famille=excluded.libelle_famille,niveau_rattachement=excluded.niveau_rattachement,residence_id=excluded.residence_id,batiment_id=excluded.batiment_id,logement_id=excluded.logement_id,date_pose=excluded.date_pose,origine_date_pose=excluded.origine_date_pose,date_pose_precedente=excluded.date_pose_precedente,nb_remplacements_2018_2025=excluded.nb_remplacements_2018_2025,duree_vie_reference_ans=excluded.duree_vie_reference_ans,sous_contrat_entretien=excluded.sous_contrat_entretien,visite_annuelle_prevue=excluded.visite_annuelle_prevue,code_metier=excluded.code_metier,prestataire_id=excluded.prestataire_id,dans_perimetre_prediction=excluded.dans_perimetre_prediction where equipements.famille is distinct from excluded.famille or equipements.libelle_famille is distinct from excluded.libelle_famille or equipements.niveau_rattachement is distinct from excluded.niveau_rattachement or equipements.residence_id is distinct from excluded.residence_id or equipements.batiment_id is distinct from excluded.batiment_id or equipements.logement_id is distinct from excluded.logement_id or equipements.date_pose is distinct from excluded.date_pose or equipements.origine_date_pose is distinct from excluded.origine_date_pose or equipements.date_pose_precedente is distinct from excluded.date_pose_precedente or equipements.nb_remplacements_2018_2025 is distinct from excluded.nb_remplacements_2018_2025 or equipements.duree_vie_reference_ans is distinct from excluded.duree_vie_reference_ans or equipements.sous_contrat_entretien is distinct from excluded.sous_contrat_entretien or equipements.visite_annuelle_prevue is distinct from excluded.visite_annuelle_prevue or equipements.code_metier is distinct from excluded.code_metier or equipements.prestataire_id is distinct from excluded.prestataire_id or equipements.dans_perimetre_prediction is distinct from excluded.dans_perimetre_prediction;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'equipements' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('equipements',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'demandes' then
  select count(*) filter(where d.demande_id is null),count(*) filter(where d.demande_id is not null and (d.date_creation is distinct from s.date_creation or d.date_cloture is distinct from s.date_cloture or d.logement_id is distinct from s.logement_id or d.batiment_id is distinct from s.batiment_id or d.residence_id is distinct from s.residence_id or d.parties is distinct from s.parties or d.canal is distinct from s.canal or d.motif is distinct from s.motif or d.objet is distinct from s.objet or d.texte_demande is distinct from s.texte_demande or d.priorite is distinct from s.priorite or d.nb_echanges is distinct from s.nb_echanges or d.demande_reouverte is distinct from s.demande_reouverte or d.delai_resolution_h is distinct from s.delai_resolution_h))
  into ajouts,modifications from jsonb_populate_recordset(null::public.demandes,p_lot->'demandes') s left join public.demandes d on d.demande_id=s.demande_id;
  insert into public.demandes(demande_id,date_creation,date_cloture,logement_id,batiment_id,residence_id,parties,canal,motif,objet,texte_demande,priorite,nb_echanges,demande_reouverte,delai_resolution_h) select demande_id,date_creation,date_cloture,logement_id,batiment_id,residence_id,parties,canal,motif,objet,texte_demande,priorite,nb_echanges,demande_reouverte,delai_resolution_h from jsonb_populate_recordset(null::public.demandes,p_lot->'demandes')
  on conflict(demande_id) do update set date_creation=excluded.date_creation,date_cloture=excluded.date_cloture,logement_id=excluded.logement_id,batiment_id=excluded.batiment_id,residence_id=excluded.residence_id,parties=excluded.parties,canal=excluded.canal,motif=excluded.motif,objet=excluded.objet,texte_demande=excluded.texte_demande,priorite=excluded.priorite,nb_echanges=excluded.nb_echanges,demande_reouverte=excluded.demande_reouverte,delai_resolution_h=excluded.delai_resolution_h where demandes.date_creation is distinct from excluded.date_creation or demandes.date_cloture is distinct from excluded.date_cloture or demandes.logement_id is distinct from excluded.logement_id or demandes.batiment_id is distinct from excluded.batiment_id or demandes.residence_id is distinct from excluded.residence_id or demandes.parties is distinct from excluded.parties or demandes.canal is distinct from excluded.canal or demandes.motif is distinct from excluded.motif or demandes.objet is distinct from excluded.objet or demandes.texte_demande is distinct from excluded.texte_demande or demandes.priorite is distinct from excluded.priorite or demandes.nb_echanges is distinct from excluded.nb_echanges or demandes.demande_reouverte is distinct from excluded.demande_reouverte or demandes.delai_resolution_h is distinct from excluded.delai_resolution_h;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'demandes' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('demandes',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'interventions' then
  select count(*) filter(where d.intervention_id is null),count(*) filter(where d.intervention_id is not null and (d.date_intervention is distinct from s.date_intervention or d.residence_id is distinct from s.residence_id or d.batiment_id is distinct from s.batiment_id or d.logement_id is distinct from s.logement_id or d.equipement_id is distinct from s.equipement_id or d.type_intervention is distinct from s.type_intervention or d.code_metier is distinct from s.code_metier or d.prestataire_id is distinct from s.prestataire_id or d.symptome is distinct from s.symptome or d.gravite is distinct from s.gravite or d.resultat is distinct from s.resultat or d.commentaire_technicien is distinct from s.commentaire_technicien or d.demande_id_liee is distinct from s.demande_id_liee))
  into ajouts,modifications from jsonb_populate_recordset(null::public.interventions,p_lot->'interventions') s left join public.interventions d on d.intervention_id=s.intervention_id;
  insert into public.interventions(intervention_id,date_intervention,residence_id,batiment_id,logement_id,equipement_id,type_intervention,code_metier,prestataire_id,symptome,gravite,resultat,commentaire_technicien,demande_id_liee) select intervention_id,date_intervention,residence_id,batiment_id,logement_id,equipement_id,type_intervention,code_metier,prestataire_id,symptome,gravite,resultat,commentaire_technicien,demande_id_liee from jsonb_populate_recordset(null::public.interventions,p_lot->'interventions')
  on conflict(intervention_id) do update set date_intervention=excluded.date_intervention,residence_id=excluded.residence_id,batiment_id=excluded.batiment_id,logement_id=excluded.logement_id,equipement_id=excluded.equipement_id,type_intervention=excluded.type_intervention,code_metier=excluded.code_metier,prestataire_id=excluded.prestataire_id,symptome=excluded.symptome,gravite=excluded.gravite,resultat=excluded.resultat,commentaire_technicien=excluded.commentaire_technicien,demande_id_liee=excluded.demande_id_liee where interventions.date_intervention is distinct from excluded.date_intervention or interventions.residence_id is distinct from excluded.residence_id or interventions.batiment_id is distinct from excluded.batiment_id or interventions.logement_id is distinct from excluded.logement_id or interventions.equipement_id is distinct from excluded.equipement_id or interventions.type_intervention is distinct from excluded.type_intervention or interventions.code_metier is distinct from excluded.code_metier or interventions.prestataire_id is distinct from excluded.prestataire_id or interventions.symptome is distinct from excluded.symptome or interventions.gravite is distinct from excluded.gravite or interventions.resultat is distinct from excluded.resultat or interventions.commentaire_technicien is distinct from excluded.commentaire_technicien or interventions.demande_id_liee is distinct from excluded.demande_id_liee;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'interventions' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('interventions',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'commandes' then
  select count(*) filter(where d.commande_id is null),count(*) filter(where d.commande_id is not null and (d.date_commande is distinct from s.date_commande or d.residence_id is distinct from s.residence_id or d.logement_id is distinct from s.logement_id or d.libelle is distinct from s.libelle or d.type_commande is distinct from s.type_commande or d.nature is distinct from s.nature or d.corps_etat is distinct from s.corps_etat or d.prestataire_id is distinct from s.prestataire_id or d.montant_ttc is distinct from s.montant_ttc or d.date_facture is distinct from s.date_facture or d.montant_facture_ttc is distinct from s.montant_facture_ttc or d.statut is distinct from s.statut))
  into ajouts,modifications from jsonb_populate_recordset(null::public.commandes,p_lot->'commandes') s left join public.commandes d on d.commande_id=s.commande_id;
  insert into public.commandes(commande_id,date_commande,residence_id,logement_id,libelle,type_commande,nature,corps_etat,prestataire_id,montant_ttc,date_facture,montant_facture_ttc,statut) select commande_id,date_commande,residence_id,logement_id,libelle,type_commande,nature,corps_etat,prestataire_id,montant_ttc,date_facture,montant_facture_ttc,statut from jsonb_populate_recordset(null::public.commandes,p_lot->'commandes')
  on conflict(commande_id) do update set date_commande=excluded.date_commande,residence_id=excluded.residence_id,logement_id=excluded.logement_id,libelle=excluded.libelle,type_commande=excluded.type_commande,nature=excluded.nature,corps_etat=excluded.corps_etat,prestataire_id=excluded.prestataire_id,montant_ttc=excluded.montant_ttc,date_facture=excluded.date_facture,montant_facture_ttc=excluded.montant_facture_ttc,statut=excluded.statut where commandes.date_commande is distinct from excluded.date_commande or commandes.residence_id is distinct from excluded.residence_id or commandes.logement_id is distinct from excluded.logement_id or commandes.libelle is distinct from excluded.libelle or commandes.type_commande is distinct from excluded.type_commande or commandes.nature is distinct from excluded.nature or commandes.corps_etat is distinct from excluded.corps_etat or commandes.prestataire_id is distinct from excluded.prestataire_id or commandes.montant_ttc is distinct from excluded.montant_ttc or commandes.date_facture is distinct from excluded.date_facture or commandes.montant_facture_ttc is distinct from excluded.montant_facture_ttc or commandes.statut is distinct from excluded.statut;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'commandes' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('commandes',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'investissements' then
  select count(*) filter(where d.operation_id is null),count(*) filter(where d.operation_id is not null and (d.residence_id is distinct from s.residence_id or d.type_operation is distinct from s.type_operation or d.perimetre is distinct from s.perimetre or d.annee_souhaitee is distinct from s.annee_souhaitee or d.cout_estime_ttc is distinct from s.cout_estime_ttc or d.gain_conso_ep_estime_kwh_m2_an is distinct from s.gain_conso_ep_estime_kwh_m2_an or d.nb_logements_concernes is distinct from s.nb_logements_concernes or d.date_inscription_demande is distinct from s.date_inscription_demande or d.origine_demande is distinct from s.origine_demande or d.statut is distinct from s.statut or d.rang_actuel_chronologique is distinct from s.rang_actuel_chronologique))
  into ajouts,modifications from jsonb_populate_recordset(null::public.investissements,p_lot->'investissements') s left join public.investissements d on d.operation_id=s.operation_id;
  insert into public.investissements(operation_id,residence_id,type_operation,perimetre,annee_souhaitee,cout_estime_ttc,gain_conso_ep_estime_kwh_m2_an,nb_logements_concernes,date_inscription_demande,origine_demande,statut,rang_actuel_chronologique) select operation_id,residence_id,type_operation,perimetre,annee_souhaitee,cout_estime_ttc,gain_conso_ep_estime_kwh_m2_an,nb_logements_concernes,date_inscription_demande,origine_demande,statut,rang_actuel_chronologique from jsonb_populate_recordset(null::public.investissements,p_lot->'investissements')
  on conflict(operation_id) do update set residence_id=excluded.residence_id,type_operation=excluded.type_operation,perimetre=excluded.perimetre,annee_souhaitee=excluded.annee_souhaitee,cout_estime_ttc=excluded.cout_estime_ttc,gain_conso_ep_estime_kwh_m2_an=excluded.gain_conso_ep_estime_kwh_m2_an,nb_logements_concernes=excluded.nb_logements_concernes,date_inscription_demande=excluded.date_inscription_demande,origine_demande=excluded.origine_demande,statut=excluded.statut,rang_actuel_chronologique=excluded.rang_actuel_chronologique where investissements.residence_id is distinct from excluded.residence_id or investissements.type_operation is distinct from excluded.type_operation or investissements.perimetre is distinct from excluded.perimetre or investissements.annee_souhaitee is distinct from excluded.annee_souhaitee or investissements.cout_estime_ttc is distinct from excluded.cout_estime_ttc or investissements.gain_conso_ep_estime_kwh_m2_an is distinct from excluded.gain_conso_ep_estime_kwh_m2_an or investissements.nb_logements_concernes is distinct from excluded.nb_logements_concernes or investissements.date_inscription_demande is distinct from excluded.date_inscription_demande or investissements.origine_demande is distinct from excluded.origine_demande or investissements.statut is distinct from excluded.statut or investissements.rang_actuel_chronologique is distinct from excluded.rang_actuel_chronologique;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'investissements' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('investissements',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'prestataires' then
  select count(*) filter(where d.prestataire_id is null),count(*) filter(where d.prestataire_id is not null and (d.nom is distinct from s.nom or d.domaine is distinct from s.domaine or d.type_contrat is distinct from s.type_contrat))
  into ajouts,modifications from jsonb_populate_recordset(null::public.prestataires,p_lot->'prestataires') s left join public.prestataires d on d.prestataire_id=s.prestataire_id;
  insert into public.prestataires(prestataire_id,nom,domaine,type_contrat) select prestataire_id,nom,domaine,type_contrat from jsonb_populate_recordset(null::public.prestataires,p_lot->'prestataires')
  on conflict(prestataire_id) do update set nom=excluded.nom,domaine=excluded.domaine,type_contrat=excluded.type_contrat where prestataires.nom is distinct from excluded.nom or prestataires.domaine is distinct from excluded.domaine or prestataires.type_contrat is distinct from excluded.type_contrat;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'prestataires' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('prestataires',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'metiers' then
  select count(*) filter(where d.code_metier is null),count(*) filter(where d.code_metier is not null and (d.libelle is distinct from s.libelle))
  into ajouts,modifications from jsonb_populate_recordset(null::public.metiers,p_lot->'metiers') s left join public.metiers d on d.code_metier=s.code_metier;
  insert into public.metiers(code_metier,libelle) select code_metier,libelle from jsonb_populate_recordset(null::public.metiers,p_lot->'metiers')
  on conflict(code_metier) do update set libelle=excluded.libelle where metiers.libelle is distinct from excluded.libelle;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'metiers' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('metiers',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'familles' then
  select count(*) filter(where d.famille is null),count(*) filter(where d.famille is not null and (d.libelle is distinct from s.libelle or d.niveau is distinct from s.niveau or d.code_metier is distinct from s.code_metier or d.duree_vie_reference_ans is distinct from s.duree_vie_reference_ans or d.sous_contrat_entretien is distinct from s.sous_contrat_entretien or d.visite_annuelle is distinct from s.visite_annuelle or d.cout_remplacement_min_ttc is distinct from s.cout_remplacement_min_ttc or d.cout_remplacement_max_ttc is distinct from s.cout_remplacement_max_ttc or d.dans_perimetre_prediction is distinct from s.dans_perimetre_prediction))
  into ajouts,modifications from jsonb_populate_recordset(null::public.familles,p_lot->'familles') s left join public.familles d on d.famille=s.famille;
  insert into public.familles(famille,libelle,niveau,code_metier,duree_vie_reference_ans,sous_contrat_entretien,visite_annuelle,cout_remplacement_min_ttc,cout_remplacement_max_ttc,dans_perimetre_prediction) select famille,libelle,niveau,code_metier,duree_vie_reference_ans,sous_contrat_entretien,visite_annuelle,cout_remplacement_min_ttc,cout_remplacement_max_ttc,dans_perimetre_prediction from jsonb_populate_recordset(null::public.familles,p_lot->'familles')
  on conflict(famille) do update set libelle=excluded.libelle,niveau=excluded.niveau,code_metier=excluded.code_metier,duree_vie_reference_ans=excluded.duree_vie_reference_ans,sous_contrat_entretien=excluded.sous_contrat_entretien,visite_annuelle=excluded.visite_annuelle,cout_remplacement_min_ttc=excluded.cout_remplacement_min_ttc,cout_remplacement_max_ttc=excluded.cout_remplacement_max_ttc,dans_perimetre_prediction=excluded.dans_perimetre_prediction where familles.libelle is distinct from excluded.libelle or familles.niveau is distinct from excluded.niveau or familles.code_metier is distinct from excluded.code_metier or familles.duree_vie_reference_ans is distinct from excluded.duree_vie_reference_ans or familles.sous_contrat_entretien is distinct from excluded.sous_contrat_entretien or familles.visite_annuelle is distinct from excluded.visite_annuelle or familles.cout_remplacement_min_ttc is distinct from excluded.cout_remplacement_min_ttc or familles.cout_remplacement_max_ttc is distinct from excluded.cout_remplacement_max_ttc or familles.dans_perimetre_prediction is distinct from excluded.dans_perimetre_prediction;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'familles' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('familles',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'motifs' then
  select count(*) filter(where d.motif is null),count(*) filter(where d.motif is not null and (d.nb_demandes_2019_2025 is distinct from s.nb_demandes_2019_2025))
  into ajouts,modifications from jsonb_populate_recordset(null::public.motifs,p_lot->'motifs') s left join public.motifs d on d.motif=s.motif and d.parties=s.parties;
  insert into public.motifs(motif,parties,nb_demandes_2019_2025) select motif,parties,nb_demandes_2019_2025 from jsonb_populate_recordset(null::public.motifs,p_lot->'motifs')
  on conflict(motif,parties) do update set nb_demandes_2019_2025=excluded.nb_demandes_2019_2025 where motifs.nb_demandes_2019_2025 is distinct from excluded.nb_demandes_2019_2025;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'motifs' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('motifs',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'seuils_dpe' then
  select count(*) filter(where d.classe is null),count(*) filter(where d.classe is not null and (d.energie_primaire_kwh_m2_an is distinct from s.energie_primaire_kwh_m2_an or d.ges_kgco2_m2_an is distinct from s.ges_kgco2_m2_an))
  into ajouts,modifications from jsonb_populate_recordset(null::public.seuils_dpe,p_lot->'seuils_dpe') s left join public.seuils_dpe d on d.classe=s.classe;
  insert into public.seuils_dpe(classe,energie_primaire_kwh_m2_an,ges_kgco2_m2_an) select classe,energie_primaire_kwh_m2_an,ges_kgco2_m2_an from jsonb_populate_recordset(null::public.seuils_dpe,p_lot->'seuils_dpe')
  on conflict(classe) do update set energie_primaire_kwh_m2_an=excluded.energie_primaire_kwh_m2_an,ges_kgco2_m2_an=excluded.ges_kgco2_m2_an where seuils_dpe.energie_primaire_kwh_m2_an is distinct from excluded.energie_primaire_kwh_m2_an or seuils_dpe.ges_kgco2_m2_an is distinct from excluded.ges_kgco2_m2_an;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'seuils_dpe' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('seuils_dpe',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'dictionnaire' then
  select count(*) filter(where d.table_source is null),count(*) filter(where d.table_source is not null and (d.type is distinct from s.type or d.description is distinct from s.description or d.equivalent_reel is distinct from s.equivalent_reel))
  into ajouts,modifications from jsonb_populate_recordset(null::public.dictionnaire,p_lot->'dictionnaire') s left join public.dictionnaire d on d.table_source=s.table_source and d.colonne=s.colonne;
  insert into public.dictionnaire(table_source,colonne,type,description,equivalent_reel) select table_source,colonne,type,description,equivalent_reel from jsonb_populate_recordset(null::public.dictionnaire,p_lot->'dictionnaire')
  on conflict(table_source,colonne) do update set type=excluded.type,description=excluded.description,equivalent_reel=excluded.equivalent_reel where dictionnaire.type is distinct from excluded.type or dictionnaire.description is distinct from excluded.description or dictionnaire.equivalent_reel is distinct from excluded.equivalent_reel;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'dictionnaire' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('dictionnaire',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'hypotheses' then
  select count(*) filter(where d.numero_ligne is null),count(*) filter(where d.numero_ligne is not null and (d.theme is distinct from s.theme or d.regle is distinct from s.regle or d.niveau_preuve is distinct from s.niveau_preuve or d.source is distinct from s.source))
  into ajouts,modifications from jsonb_populate_recordset(null::public.hypotheses,p_lot->'hypotheses') s left join public.hypotheses d on d.numero_ligne=s.numero_ligne;
  insert into public.hypotheses(numero_ligne,theme,regle,niveau_preuve,source) select numero_ligne,theme,regle,niveau_preuve,source from jsonb_populate_recordset(null::public.hypotheses,p_lot->'hypotheses')
  on conflict(numero_ligne) do update set theme=excluded.theme,regle=excluded.regle,niveau_preuve=excluded.niveau_preuve,source=excluded.source where hypotheses.theme is distinct from excluded.theme or hypotheses.regle is distinct from excluded.regle or hypotheses.niveau_preuve is distinct from excluded.niveau_preuve or hypotheses.source is distinct from excluded.source;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'hypotheses' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('hypotheses',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 if p_lot ? 'documentation' then
  select count(*) filter(where d.numero_ligne is null),count(*) filter(where d.numero_ligne is not null and (d.colonne_1 is distinct from s.colonne_1 or d.colonne_2 is distinct from s.colonne_2 or d.colonne_3 is distinct from s.colonne_3 or d.colonne_4 is distinct from s.colonne_4 or d.colonne_5 is distinct from s.colonne_5 or d.colonne_6 is distinct from s.colonne_6))
  into ajouts,modifications from jsonb_populate_recordset(null::public.documentation,p_lot->'documentation') s left join public.documentation d on d.numero_ligne=s.numero_ligne;
  insert into public.documentation(numero_ligne,colonne_1,colonne_2,colonne_3,colonne_4,colonne_5,colonne_6) select numero_ligne,colonne_1,colonne_2,colonne_3,colonne_4,colonne_5,colonne_6 from jsonb_populate_recordset(null::public.documentation,p_lot->'documentation')
  on conflict(numero_ligne) do update set colonne_1=excluded.colonne_1,colonne_2=excluded.colonne_2,colonne_3=excluded.colonne_3,colonne_4=excluded.colonne_4,colonne_5=excluded.colonne_5,colonne_6=excluded.colonne_6 where documentation.colonne_1 is distinct from excluded.colonne_1 or documentation.colonne_2 is distinct from excluded.colonne_2 or documentation.colonne_3 is distinct from excluded.colonne_3 or documentation.colonne_4 is distinct from excluded.colonne_4 or documentation.colonne_5 is distinct from excluded.colonne_5 or documentation.colonne_6 is distinct from excluded.colonne_6;
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if 'documentation' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('documentation',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;

 -- Les contraintes différées sont vérifiées avant d'inscrire le succès.
 set constraints all immediate;
 insert into public.imports(auteur,nb_ajouts,nb_modifications,modifie_modele,details)
 values(auth.uid(),total_ajouts,total_modifications,modele,jsonb_build_object('files',p_fichiers,'tables',bilan)) returning id into nouvelle_revision;
 return jsonb_build_object('importId',nouvelle_revision,'revision',case when total_ajouts+total_modifications=0 then ancien else nouvelle_revision end,'modelChanged',modele,'tables',bilan);
end $$;
revoke execute on function public.importer_lot(jsonb,bigint,jsonb) from authenticated;
comment on column public.residences.residence_id is 'Identifiant de la résidence (clé)';
comment on column public.residences.nom is 'Nom anonymisé (Résidence A à H)';
comment on column public.residences.localisation is 'Zone géographique volontairement imprécise';
comment on column public.residences.annee_construction is 'Année de construction';
comment on column public.residences.nb_batiments is 'Nombre de bâtiments / cages';
comment on column public.residences.nb_logements is 'Nombre de logements';
comment on column public.residences.surface_habitable_totale_m2 is 'Somme des surfaces habitables';
comment on column public.residences.ascenseur is 'Au moins un ascenseur dans la résidence';
comment on column public.residences.energie_chauffage is 'Énergie principale de chauffage';
comment on column public.residences.type_chauffage is 'Individuel ou collectif';
comment on column public.residences.generateur_chauffage is 'Type de générateur';
comment on column public.residences.production_ecs is 'Mode de production d’eau chaude sanitaire';
comment on column public.residences.ventilation is 'Type de ventilation';
comment on column public.residences.etiquette_dpe_majoritaire is 'Étiquette DPE globale la plus fréquente';
comment on column public.residences.conso_ep_moyenne_kwh_m2_an is 'Consommation moyenne en énergie primaire';
comment on column public.residences.ges_moyen_kgco2_m2_an is 'Émissions moyennes de gaz à effet de serre';
comment on column public.batiments.batiment_id is 'Identifiant du bâtiment (clé)';
comment on column public.batiments.residence_id is 'Résidence de rattachement';
comment on column public.batiments.nb_niveaux is 'Nombre de niveaux (RDC inclus)';
comment on column public.batiments.nb_logements is 'Logements desservis';
comment on column public.batiments.ascenseur is 'Présence d’un ascenseur';
comment on column public.logements.logement_id is 'Identifiant du logement (clé). Pseudonyme sans lien avec un numéro réel';
comment on column public.logements.batiment_id is 'Colonne batiment_id du CSV 03_logements.';
comment on column public.logements.residence_id is 'Colonne residence_id du CSV 03_logements.';
comment on column public.logements.typologie is 'Nombre de pièces';
comment on column public.logements.surface_habitable_m2 is 'Surface habitable';
comment on column public.logements.etage is 'Étage (0 = rez-de-chaussée)';
comment on column public.logements.dpe_methode is 'Ancien DPE (avant 07/2021, non comparable) ou nouveau DPE 3CL 2021';
comment on column public.logements.dpe_date is 'Date d’établissement du DPE';
comment on column public.logements.dpe_conso_ep_kwh_m2_an is 'Consommation en énergie primaire';
comment on column public.logements.dpe_ges_kgco2_m2_an is 'Émissions de GES';
comment on column public.logements.dpe_etiquette_energie is 'Colonne dpe_etiquette_energie du CSV 03_logements.';
comment on column public.logements.dpe_etiquette_ges is 'Colonne dpe_etiquette_ges du CSV 03_logements.';
comment on column public.logements.dpe_etiquette_globale is 'Colonne dpe_etiquette_globale du CSV 03_logements.';
comment on column public.logements.nb_changements_locataire_2018_2025 is 'Nombre de rotations de locataires sur la période';
comment on column public.logements.date_entree_locataire_actuel is 'Date d’entrée du locataire actuel (ou « Avant 2018 »)';
comment on column public.logements.statut_occupation is 'Occupé / Vacant au 31/12/2025';
comment on column public.equipements.equipement_id is 'Identifiant de l’emplacement fonctionnel (clé). Un remplacement garde le même identifiant, la date de pose change';
comment on column public.equipements.famille is 'Colonne famille du CSV 04_equipements.';
comment on column public.equipements.libelle_famille is 'Colonne libelle_famille du CSV 04_equipements.';
comment on column public.equipements.niveau_rattachement is 'Logement ou Bâtiment (parties communes)';
comment on column public.equipements.residence_id is 'Colonne residence_id du CSV 04_equipements.';
comment on column public.equipements.batiment_id is 'Colonne batiment_id du CSV 04_equipements.';
comment on column public.equipements.logement_id is 'Colonne logement_id du CSV 04_equipements.';
comment on column public.equipements.date_pose is 'Date de pose de l’équipement en place au 31/12/2025';
comment on column public.equipements.origine_date_pose is 'Niveau de preuve de la date : fait réel transposé, remplacement tracé, ou hypothèse';
comment on column public.equipements.date_pose_precedente is 'Date de pose de l’équipement précédent (si remplacé depuis 2018)';
comment on column public.equipements.nb_remplacements_2018_2025 is 'Nombre de remplacements sur la période';
comment on column public.equipements.duree_vie_reference_ans is 'Durée de vie de référence de la famille (hypothèse métier)';
comment on column public.equipements.sous_contrat_entretien is 'Couvert par un contrat (dépannages sans bon de commande)';
comment on column public.equipements.visite_annuelle_prevue is 'Entretien préventif annuel prévu';
comment on column public.equipements.code_metier is 'Code métier prestataire (voir 10_ref_codes_metiers)';
comment on column public.equipements.prestataire_id is 'Prestataire en charge';
comment on column public.equipements.dans_perimetre_prediction is 'Équipement à scorer pour le défi « détection précoce de panne »';
comment on column public.demandes.demande_id is 'Identifiant de la demande (clé)';
comment on column public.demandes.date_creation is 'Colonne date_creation du CSV 05_demandes_locataires.';
comment on column public.demandes.date_cloture is 'Colonne date_cloture du CSV 05_demandes_locataires.';
comment on column public.demandes.logement_id is 'Colonne logement_id du CSV 05_demandes_locataires.';
comment on column public.demandes.batiment_id is 'Colonne batiment_id du CSV 05_demandes_locataires.';
comment on column public.demandes.residence_id is 'Colonne residence_id du CSV 05_demandes_locataires.';
comment on column public.demandes.parties is 'Privatives ou Communes';
comment on column public.demandes.canal is 'Canal d’entrée';
comment on column public.demandes.motif is 'Motif normalisé (liste réelle de l’outil)';
comment on column public.demandes.objet is 'Objet court saisi';
comment on column public.demandes.texte_demande is 'Texte de la demande — ENTIÈREMENT FICTIF, sans nom ni coordonnée';
comment on column public.demandes.priorite is 'Niveau de priorité';
comment on column public.demandes.nb_echanges is 'Nombre d’échanges avec le locataire';
comment on column public.demandes.demande_reouverte is 'La demande a été rouverte';
comment on column public.demandes.delai_resolution_h is 'Délai de résolution en heures';
comment on column public.interventions.intervention_id is 'Identifiant (clé)';
comment on column public.interventions.date_intervention is 'Date du passage';
comment on column public.interventions.residence_id is 'Colonne residence_id du CSV 06_interventions.';
comment on column public.interventions.batiment_id is 'Colonne batiment_id du CSV 06_interventions.';
comment on column public.interventions.logement_id is 'Colonne logement_id du CSV 06_interventions.';
comment on column public.interventions.equipement_id is 'Équipement concerné (clé vers 04_equipements)';
comment on column public.interventions.type_intervention is 'Entretien préventif, Dépannage ou Remplacement';
comment on column public.interventions.code_metier is 'Code métier du contrat';
comment on column public.interventions.prestataire_id is 'Prestataire';
comment on column public.interventions.symptome is 'Symptôme constaté (dépannages)';
comment on column public.interventions.gravite is 'Gêne mineure / Fonctionnement dégradé / Arrêt total';
comment on column public.interventions.resultat is 'Issue du passage (réparé, absent, anomalie constatée, remplacement nécessaire…)';
comment on column public.interventions.commentaire_technicien is 'Commentaire court (fictif). Contient des signaux faibles';
comment on column public.interventions.demande_id_liee is 'Demande locataire à l’origine du dépannage, si identifiée';
comment on column public.commandes.commande_id is 'Identifiant (clé)';
comment on column public.commandes.date_commande is 'Date d’enregistrement';
comment on column public.commandes.residence_id is 'Colonne residence_id du CSV 07_commandes.';
comment on column public.commandes.logement_id is 'Colonne logement_id du CSV 07_commandes.';
comment on column public.commandes.libelle is 'Libellé de la commande';
comment on column public.commandes.type_commande is 'Type (ENTRETIEN PPV H/EDL, TRV PPV REMONTE EN GAMME, ENTRETIEN PCO…)';
comment on column public.commandes.nature is 'Nature de dépense (PLOMBERIE, ELECTRICITE…)';
comment on column public.commandes.corps_etat is 'Code corps d’état';
comment on column public.commandes.prestataire_id is 'Prestataire';
comment on column public.commandes.montant_ttc is 'Montant commandé (€ TTC)';
comment on column public.commandes.date_facture is 'Colonne date_facture du CSV 07_commandes.';
comment on column public.commandes.montant_facture_ttc is 'Colonne montant_facture_ttc du CSV 07_commandes.';
comment on column public.commandes.statut is 'Soldée ou En cours';
comment on column public.investissements.operation_id is 'Identifiant (clé)';
comment on column public.investissements.residence_id is 'Résidence concernée';
comment on column public.investissements.type_operation is 'Nature de l’opération';
comment on column public.investissements.perimetre is 'Périmètre (résidence, bâtiments, lot de logements)';
comment on column public.investissements.annee_souhaitee is 'Année souhaitée par le demandeur';
comment on column public.investissements.cout_estime_ttc is 'Coût estimé (€ TTC) — hypothèse';
comment on column public.investissements.gain_conso_ep_estime_kwh_m2_an is 'Gain estimé de consommation (énergie primaire) — hypothèse';
comment on column public.investissements.nb_logements_concernes is 'Logements impactés';
comment on column public.investissements.date_inscription_demande is 'Date à laquelle la demande a été inscrite';
comment on column public.investissements.origine_demande is 'Motif de la demande';
comment on column public.investissements.statut is 'Proposé (hypothétique)';
comment on column public.investissements.rang_actuel_chronologique is 'Rang si l’on traite « premier inscrit, premier servi » (pratique actuelle)';
comment on column public.prestataires.prestataire_id is 'Identifiant (clé)';
comment on column public.prestataires.nom is 'Nom fictif';
comment on column public.prestataires.domaine is 'Domaine d’intervention';
comment on column public.prestataires.type_contrat is 'Contrat ou marché';
comment on column public.metiers.code_metier is 'Colonne code_metier du CSV 10_ref_codes_metiers.';
comment on column public.metiers.libelle is 'Colonne libelle du CSV 10_ref_codes_metiers.';
comment on column public.familles.famille is 'Colonne famille du CSV 10_ref_familles_equipements.';
comment on column public.familles.libelle is 'Colonne libelle du CSV 10_ref_familles_equipements.';
comment on column public.familles.niveau is 'Colonne niveau du CSV 10_ref_familles_equipements.';
comment on column public.familles.code_metier is 'Colonne code_metier du CSV 10_ref_familles_equipements.';
comment on column public.familles.duree_vie_reference_ans is 'Colonne duree_vie_reference_ans du CSV 10_ref_familles_equipements.';
comment on column public.familles.sous_contrat_entretien is 'Colonne sous_contrat_entretien du CSV 10_ref_familles_equipements.';
comment on column public.familles.visite_annuelle is 'Colonne visite_annuelle du CSV 10_ref_familles_equipements.';
comment on column public.familles.cout_remplacement_min_ttc is 'Colonne cout_remplacement_min_ttc du CSV 10_ref_familles_equipements.';
comment on column public.familles.cout_remplacement_max_ttc is 'Colonne cout_remplacement_max_ttc du CSV 10_ref_familles_equipements.';
comment on column public.familles.dans_perimetre_prediction is 'Colonne dans_perimetre_prediction du CSV 10_ref_familles_equipements.';
comment on column public.motifs.motif is 'Colonne motif du CSV 10_ref_motifs_demandes.';
comment on column public.motifs.parties is 'Colonne parties du CSV 10_ref_motifs_demandes.';
comment on column public.motifs.nb_demandes_2019_2025 is 'Colonne nb_demandes_2019_2025 du CSV 10_ref_motifs_demandes.';
comment on column public.seuils_dpe.classe is 'Colonne classe du CSV 10_ref_seuils_dpe.';
comment on column public.seuils_dpe.energie_primaire_kwh_m2_an is 'Colonne energie_primaire_kwh_m2_an du CSV 10_ref_seuils_dpe.';
comment on column public.seuils_dpe.ges_kgco2_m2_an is 'Colonne ges_kgco2_m2_an du CSV 10_ref_seuils_dpe.';
comment on column public.dictionnaire.table_source is 'Colonne table_source du CSV dictionnaire.';
comment on column public.dictionnaire.colonne is 'Colonne colonne du CSV dictionnaire.';
comment on column public.dictionnaire.type is 'Colonne type du CSV dictionnaire.';
comment on column public.dictionnaire.description is 'Colonne description du CSV dictionnaire.';
comment on column public.dictionnaire.equivalent_reel is 'Colonne equivalent_reel du CSV dictionnaire.';
comment on column public.hypotheses.numero_ligne is 'Colonne numero_ligne du CSV hypotheses.';
comment on column public.hypotheses.theme is 'Colonne theme du CSV hypotheses.';
comment on column public.hypotheses.regle is 'Colonne regle du CSV hypotheses.';
comment on column public.hypotheses.niveau_preuve is 'Colonne niveau_preuve du CSV hypotheses.';
comment on column public.hypotheses.source is 'Colonne source du CSV hypotheses.';
comment on column public.documentation.numero_ligne is 'Colonne numero_ligne du CSV documentation.';
comment on column public.documentation.colonne_1 is 'Colonne colonne_1 du CSV documentation.';
comment on column public.documentation.colonne_2 is 'Colonne colonne_2 du CSV documentation.';
comment on column public.documentation.colonne_3 is 'Colonne colonne_3 du CSV documentation.';
comment on column public.documentation.colonne_4 is 'Colonne colonne_4 du CSV documentation.';
comment on column public.documentation.colonne_5 is 'Colonne colonne_5 du CSV documentation.';
comment on column public.documentation.colonne_6 is 'Colonne colonne_6 du CSV documentation.';
