import { useEffect } from 'react';
import { CrisisTimeline } from './components/CrisisTimeline';
import { MapView } from './components/MapView';
import { ModalHost } from './components/Modals';
import { OverrideDrawer } from './components/OverrideDrawer';
import { SidePanel } from './components/SidePanel';
import { Toasts } from './components/Toasts';
import { Rail, TopBar } from './components/TopBar';
import { useClock } from './state/clock';
import { useStore } from './state/store';

export function App() {
  const status = useStore((s) => s.status);
  const error = useStore((s) => s.error);
  useEffect(() => {
    useStore.getState().init();
  }, []);
  useClock();

  if (status === 'loading') return <div className="splash">Chargement de la crise…</div>;
  if (status === 'error')
    return (
      <div className="splash error">
        <b>Impossible de charger la crise.</b>
        <span>{error}</span>
      </div>
    );

  return (
    <div className="app pro">
      <TopBar />
      <Rail />
      <div className="content">
        <main className="main">
          <MapView />
          <SidePanel />
        </main>
        <CrisisTimeline />
      </div>
      <OverrideDrawer />
      <ModalHost />
      <Toasts />
    </div>
  );
}
