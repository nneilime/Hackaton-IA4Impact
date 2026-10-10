-- !!! EFFACE TOUTES LES DONNÉES – NE JAMAIS LANCER SUR LE SERVEUR PARTAGÉ !!!
-- !!! ATTENTION : CE FICHIER SUPPRIME TOUTES LES TABLES ET TOUTES LES DONNÉES !!!
-- Usage réservé à une base locale jetable (docker-compose) pour repartir de zéro.
-- Ensuite, relancer db/schema.sql pour recréer les tables vides.

DROP VIEW  IF EXISTS v_comparison;
DROP TABLE IF EXISTS field_evidence, collection_runs,
                     uses, registrations, product_aliases,
                     product_name_mapping, active_entity_mapping,
                     eppo_crop_mapping, eppo_pest_mapping,
                     products, source_registry CASCADE;
