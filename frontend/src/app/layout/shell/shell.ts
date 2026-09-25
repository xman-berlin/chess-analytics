import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Shell {
  readonly links = [
    { path: '/', label: 'Dashboard', exact: true },
    { path: '/quiz', label: 'Üben', exact: false },
    { path: '/plan', label: 'Trainingsplan', exact: false },
    { path: '/curriculum', label: 'Lehrplan', exact: false },
    { path: '/games', label: 'Partien', exact: false },
    { path: '/settings', label: 'Einstellungen', exact: false },
  ];
}
