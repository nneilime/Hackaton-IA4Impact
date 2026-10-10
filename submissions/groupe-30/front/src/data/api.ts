import {
  createClient,
  type Session,
  type SupabaseClient,
} from "@supabase/supabase-js";
let token = "";
let client: Promise<SupabaseClient> | null = null;
export function setSession(session: Session | null) {
  token = session?.access_token || "";
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, { ...init, headers });
  const value = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : "La requête a échoué. Réessayez.",
    );
  return value as T;
}
export function authClient() {
  if (!client)
    client = api<{ url: string; publishableKey: string }>("/config")
      .then((config) => {
        if (!config.url || !config.publishableKey)
          throw new Error("Supabase Auth doit être configuré sur le serveur.");
        return createClient(config.url, config.publishableKey);
      })
      .catch((error) => {
        client = null;
        throw error;
      });
  return client;
}
