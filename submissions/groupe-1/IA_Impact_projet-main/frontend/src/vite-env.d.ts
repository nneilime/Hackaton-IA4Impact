/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Clé Google Maps (API Street View Static), restreinte au domaine du site — voir README
  readonly VITE_GOOGLE_MAPS_KEY?: string;
}
