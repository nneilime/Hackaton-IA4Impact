"""Génère une migration versionnée à partir du contrat CSV explicite."""

from scripts.schema import ROOT, TABLES, source_ddl

APP_DDL = """
create table public.membres (
 user_id uuid primary key references auth.users(id) on delete cascade,
 role text not null check(role in ('membre','admin')), nom text not null default ''
);
create function public.est_membre() returns boolean language sql stable security definer set search_path='' as $$ select exists(select 1 from public.membres where user_id=auth.uid()) $$;
create function public.est_admin() returns boolean language sql stable security definer set search_path='' as $$ select exists(select 1 from public.membres where user_id=auth.uid() and role='admin') $$;
revoke all on function public.est_membre(), public.est_admin() from public, anon;
grant execute on function public.est_membre(), public.est_admin() to authenticated;
create table public.imports (
 id bigint generated always as identity primary key, auteur uuid references auth.users(id),
 date_import timestamptz not null default now(), statut text not null default 'applique' check(statut in ('preparation','applique')),
 nb_ajouts integer not null default 0, nb_modifications integer not null default 0,
 modifie_modele boolean not null default false, details jsonb not null default '{}'
);
create table public.calculs (
 id uuid primary key default gen_random_uuid(), auteur uuid references auth.users(id),
 date_reference date not null, revision bigint not null, version_modele text not null,
 statut text not null check(statut in ('en_attente','en_cours','termine','depasse','echec')),
 progression integer not null default 0 check(progression between 0 and 100),
 nb_equipements integer not null default 0, erreur text,
 cree_le timestamptz not null default now(), termine_le timestamptz
);
create unique index calcul_unique_en_cours on public.calculs(date_reference,revision,version_modele) where statut in ('en_attente','en_cours');
create table public.predictions (
 calcul_id uuid not null references public.calculs(id) on delete cascade,
 equipement_id text not null references public.equipements(equipement_id),
 horizon_jours integer not null check(horizon_jours in (90,180,365,730)),
 score double precision not null check(score between 0 and 1), seuil double precision not null check(seuil between 0 and 1),
 alerte boolean not null, niveau_risque text not null, action_recommandee text not null,
 primary key(calcul_id,equipement_id,horizon_jours)
);
create table public.inspections (
 id text primary key, equipement_id text not null references public.equipements(equipement_id),
 statut text not null check(statut in ('preparing','planned','completed','closed','review')),
 responsable text not null check(length(trim(responsable))>0), prestataire_id text references public.prestataires(prestataire_id),
 objectif text not null check(length(trim(objectif))>0), date_souhaitee date, date_confirmee date, date_reexamen date, date_visite date,
 resultat text not null default '', note text not null default '', conclusion text not null default '', reference_externe text not null default '',
 debut_cycle timestamp, version_score text not null default '', version integer not null default 1,
 cree_le timestamptz not null default now(), modifie_le timestamptz not null default now(), auteur uuid references auth.users(id),
 check(statut<>'planned' or date_confirmee is not null),
 check(statut not in ('completed','closed') or (date_visite is not null and length(trim(resultat))>0)),
 check(statut<>'closed' or length(trim(conclusion))>0),
 check(statut<>'review' or date_reexamen is not null)
);
create unique index inspection_ouverte_unique on public.inspections(equipement_id) where statut<>'closed';
create table public.historique_inspections (
 id bigint generated always as identity primary key, inspection_id text not null references public.inspections(id) on delete cascade,
 date_evenement timestamptz not null default now(), libelle text not null, note text not null default '', statut text, resultat text, auteur uuid references auth.users(id)
);
create index on public.historique_inspections(inspection_id,date_evenement,id);
create table public.signalements (
 id text primary key, equipement_id text not null references public.equipements(equipement_id),
 sujet text not null check(length(trim(sujet))>0), commentaire text not null check(length(trim(commentaire))>0),
 auteur_nom text not null check(length(trim(auteur_nom))>0), auteur uuid references auth.users(id), cree_le timestamptz not null default now()
);
create table public.observations (
 id text primary key, equipement_id text not null references public.equipements(equipement_id),
 trimestre integer not null, annee integer not null default 2025, page integer, texte text not null, url text not null
);
do $$ begin if not exists(select 1 from pg_roles where rolname='batia_api') then create role batia_api nologin; end if; end $$;
grant usage on schema public,auth to batia_api;
grant execute on function auth.uid(), public.est_membre(),public.est_admin() to batia_api;
grant select on public.membres to batia_api;
alter table public.membres enable row level security;
create policy membre_propre on public.membres for select to authenticated,batia_api using(user_id=auth.uid());
grant select on public.membres to authenticated;
"""


def migration_sql():
    parts = [source_ddl(), APP_DDL]
    tables = list(TABLES) + [
        "imports",
        "calculs",
        "predictions",
        "inspections",
        "historique_inspections",
        "signalements",
        "observations",
    ]
    for table in tables:
        parts += [
            f"alter table public.{table} enable row level security;",
            f"revoke all on public.{table} from anon;",
            f"grant select on public.{table} to authenticated,batia_api;",
            f"create policy lecture_equipe on public.{table} for select to authenticated,batia_api using(public.est_membre());",
        ]
    # Les résultats du modèle sont publiés uniquement par le serveur, jamais par le navigateur.
    for table in ("calculs", "predictions"):
        parts += [
            f"grant insert,update,delete on public.{table} to batia_api;",
            f"create policy serveur_calcul on public.{table} for all to batia_api using(true) with check(true);",
        ]
    for table in ("inspections", "historique_inspections", "signalements"):
        parts += [
            f"grant insert,update,delete on public.{table} to batia_api;",
            f"create policy ecriture_equipe on public.{table} for all to batia_api using(public.est_membre()) with check(public.est_membre());",
        ]
    parts += ["grant usage,select on all sequences in schema public to batia_api;"]
    keys_sql = ",".join(
        "'" + t + "',array[" + ",".join("'" + k + "'" for k in keys) + "]"
        for t, (keys, _) in TABLES.items()
    )
    # SQL construit exclusivement depuis TABLES, jamais depuis un nom fourni par le client.
    branches = []
    for table, (keys, cols) in TABLES.items():
        key_join = " and ".join(f"d.{k}=s.{k}" for k in keys)
        compare = " or ".join(
            f"d.{c} is distinct from s.{c}" for c in cols if c not in keys
        )
        assignments = ",".join(f"{c}=excluded.{c}" for c in cols if c not in keys)
        different = " or ".join(
            f"{table}.{c} is distinct from excluded.{c}" for c in cols if c not in keys
        )
        branches.append(f"""
 if p_lot ? '{table}' then
  select count(*) filter(where d.{keys[0]} is null),count(*) filter(where d.{keys[0]} is not null and ({compare}))
  into ajouts,modifications from jsonb_populate_recordset(null::public.{table},p_lot->'{table}') s left join public.{table} d on {key_join};
  insert into public.{table}({','.join(cols)}) select {','.join(cols)} from jsonb_populate_recordset(null::public.{table},p_lot->'{table}')
  on conflict({','.join(keys)}) do update set {assignments} where {different};
  total_ajouts:=total_ajouts+ajouts; total_modifications:=total_modifications+modifications;
  if '{table}' in ('equipements','interventions','demandes') and ajouts+modifications>0 then modele:=true; end if;
  bilan:=bilan || jsonb_build_object('{table}',jsonb_build_object('added',ajouts,'updated',modifications));
 end if;
""")
    parts += [f"""
create function public.importer_lot(p_lot jsonb,p_revision bigint,p_fichiers jsonb default '[]') returns jsonb
language plpgsql security definer set search_path=public,pg_temp as $$
declare ajouts integer; modifications integer; total_ajouts integer:=0; total_modifications integer:=0;
 modele boolean:=false; bilan jsonb:='{{}}'; nouvelle_revision bigint; ancien bigint;
begin
 if auth.uid() is null then
  if session_user not in ('postgres','supabase_admin') then raise exception 'Accès administrateur requis'; end if;
 elsif not public.est_admin() then raise exception 'Accès administrateur requis'; end if;
 if exists(select 1 from jsonb_object_keys(p_lot) k where k not in ({','.join(repr(t) for t in TABLES)})) then raise exception 'Table inconnue'; end if;
 perform pg_advisory_xact_lock(821906);
 select coalesce(max(id),0) into ancien from public.imports where statut='applique' and nb_ajouts+nb_modifications>0;
 if p_revision<>ancien then raise exception 'Aperçu périmé : vérifier à nouveau le lot' using errcode='40001'; end if;
 set constraints all deferred;
 {''.join(branches)}
 -- Les contraintes différées sont vérifiées avant d'inscrire le succès.
 set constraints all immediate;
 insert into public.imports(auteur,nb_ajouts,nb_modifications,modifie_modele,details)
 values(auth.uid(),total_ajouts,total_modifications,modele,jsonb_build_object('files',p_fichiers,'tables',bilan)) returning id into nouvelle_revision;
 return jsonb_build_object('importId',nouvelle_revision,'revision',case when total_ajouts+total_modifications=0 then ancien else nouvelle_revision end,'modelChanged',modele,'tables',bilan);
end $$;
revoke all on function public.importer_lot(jsonb,bigint,jsonb) from public,anon;
grant execute on function public.importer_lot(jsonb,bigint,jsonb) to authenticated,batia_api;
"""]
    return "\n".join(parts)


if __name__ == "__main__":
    target = ROOT / "supabase" / "migrations" / "202610100001_donnees_partagees.sql"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(migration_sql(), encoding="utf-8")
    print(target)
