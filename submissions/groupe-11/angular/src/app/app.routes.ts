import { Routes } from '@angular/router';
import { AgentComponent } from './agent/agent';
import { DashboardComponent } from './dashboard/dashboard';

export const routes: Routes = [
  { path: '', component: AgentComponent },
  { path: 'dashboard', component: DashboardComponent },
];
