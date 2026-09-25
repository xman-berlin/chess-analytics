import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api, OpeningReport } from '../../core/api';

@Component({
  selector: 'app-openings',
  imports: [RouterLink],
  templateUrl: './openings.html',
  styleUrl: './openings.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OpeningsPage implements OnInit {
  private readonly api = inject(Api);

  readonly report = signal<OpeningReport | null>(null);
  readonly loading = signal(true);
  readonly message = signal<string | null>(null);
  readonly openKey = signal<string | null>(null);
  readonly days = signal(90);
  readonly windows = [
    { days: 90, label: '90 Tage' },
    { days: 180, label: '180 Tage' },
    { days: 0, label: 'Alles' },
  ];

  toggle(color: string, name: string): void {
    const key = `${color}:${name}`;
    this.openKey.set(this.openKey() === key ? null : key);
  }

  isOpen(color: string, name: string): boolean {
    return this.openKey() === `${color}:${name}`;
  }

  setDays(days: number): void {
    this.days.set(days);
    this.openKey.set(null);
    this.load();
  }

  mark(color: string, name: string, trained: boolean): void {
    this.message.set(null);
    this.api.setOpeningTrained({ color, name, trained, days: this.days() }).subscribe({
      next: (report) => this.report.set(report),
      error: () => this.message.set('Die Markierung konnte nicht gespeichert werden.'),
    });
  }

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.api.getOpenings(this.days()).subscribe({
      next: (report) => {
        this.report.set(report);
        this.loading.set(false);
      },
      error: () => {
        this.message.set('Eröffnungen konnten nicht geladen werden. Läuft die API auf Port 8000?');
        this.loading.set(false);
      },
    });
  }
}
