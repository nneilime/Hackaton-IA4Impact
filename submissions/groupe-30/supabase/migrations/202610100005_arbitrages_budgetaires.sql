-- Plans de travail partagés, sans émission de commande ni modification du plan source.
create table public.budgets (
  annee integer primary key check (annee between 2000 and 2100),
  renovation numeric(14,2) not null check (renovation >= 0),
  maintenance numeric(14,2) check (maintenance >= 0),
  version integer not null default 1,
  auteur uuid references public.membres(user_id),
  modifie_le timestamptz not null default now()
);
comment on table public.budgets is 'Enveloppes annuelles de simulation partagées. Rénovation et maintenance sont séparées ; aucun engagement de dépense.';
comment on column public.budgets.maintenance is 'Enveloppe maintenance saisie par l’équipe, inconnue si NULL. Elle ne provient pas du budget hypothétique de rénovation du kit.';
create table public.operations_retenues (
  annee integer not null references public.budgets(annee) on delete cascade,
  operation_id text not null references public.investissements(operation_id),
  primary key (annee, operation_id)
);
comment on table public.operations_retenues is 'Sélection proposée pour arbitrage, jamais une commande. Le coût reste celui du CSV investissements.';
alter table public.budgets enable row level security;
alter table public.operations_retenues enable row level security;
grant select on public.budgets,public.operations_retenues to authenticated,batia_api;
grant insert,update,delete on public.budgets,public.operations_retenues to batia_api;
create policy lecture_equipe on public.budgets for select to authenticated,batia_api using(prive.est_membre());
create policy lecture_equipe on public.operations_retenues for select to authenticated,batia_api using(prive.est_membre());
create policy ecriture_api on public.budgets for all to batia_api using(prive.est_membre()) with check(prive.est_membre());
create policy ecriture_api on public.operations_retenues for all to batia_api using(prive.est_membre()) with check(prive.est_membre());
