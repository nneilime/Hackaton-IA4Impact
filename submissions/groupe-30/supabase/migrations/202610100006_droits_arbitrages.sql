-- Supabase peut attribuer des droits par défaut aux nouvelles tables.
-- La lecture exige un membre ; toutes les écritures passent par l'API validée.
revoke all on public.budgets,public.operations_retenues from anon,authenticated;
grant select on public.budgets,public.operations_retenues to authenticated;
