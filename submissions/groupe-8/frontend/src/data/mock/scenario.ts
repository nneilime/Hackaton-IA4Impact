// Shape of the generated mock scenario (public/mock/<crisis>/scenario.json).
// This is the raw input of the mock engine, not part of the engine/frontend contract.
import type { Site } from '../contract';

export type ScenarioIncident = {
  id: string;
  posteId: string;
  lon: number;
  lat: number;
  commune: string;
  departement: string;
  clients: number;
  sensitive: boolean;
  cause: string;
  repairHours: number;
  reportedMin: number; // minutes after scenario start
};

export type ScenarioTeam = {
  id: string;
  label: string;
  siteId: string;
  siteName: string;
  lon: number;
  lat: number;
  initialShiftHours: number; // hours left in the current shift at scenario start
  initialRestHours: number; // > 0: team starts off duty, back on shift after this many hours
};

export type Scenario = {
  crisisId: string;
  startMs: number; // UTC epoch ms of step 0
  stepMinutes: number;
  sites: Site[];
  teams: ScenarioTeam[];
  incidents: ScenarioIncident[];
};
