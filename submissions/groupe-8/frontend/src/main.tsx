import { createRoot } from 'react-dom/client';
import '@fontsource-variable/outfit';
import '@fontsource-variable/public-sans';
import '@fontsource-variable/sora';
import './styles/tokens.css';
import './styles/app.css';
import './styles/shell.css';
import './styles/pro.css';
import './styles/live.css';
import { App } from './App';

if (import.meta.env.DEV) import('./dev/capture');

// No <StrictMode>: its dev-only double mount re-adds the same deck.gl MapboxOverlay after removing it, which leaves
// an orphan overlay canvas (the one drawn) and a live 300×150 one without layers (the one receiving the mouse):
// hover and click on the map then hit nothing.
createRoot(document.getElementById('root')!).render(<App />);
