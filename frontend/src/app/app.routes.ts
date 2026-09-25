import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./layout/shell/shell').then((m) => m.Shell),
    children: [
      {
        path: '',
        loadComponent: () => import('./pages/dashboard/dashboard').then((m) => m.Dashboard),
      },
      {
        path: 'plan',
        loadComponent: () => import('./pages/plan/plan').then((m) => m.Plan),
      },
      {
        path: 'curriculum',
        loadComponent: () =>
          import('./pages/curriculum/curriculum').then((m) => m.CurriculumPage),
      },
      {
        path: 'quiz',
        loadComponent: () => import('./pages/quiz/quiz').then((m) => m.Quiz),
      },
      {
        path: 'games',
        loadComponent: () => import('./pages/games/games').then((m) => m.Games),
      },
      {
        path: 'games/:id',
        loadComponent: () =>
          import('./pages/game-detail/game-detail').then((m) => m.GameDetail),
      },
      {
        path: 'settings',
        loadComponent: () => import('./pages/settings/settings').then((m) => m.Settings),
      },
    ],
  },
];
