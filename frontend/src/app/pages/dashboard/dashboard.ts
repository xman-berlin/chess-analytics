import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api, AppStatus, CoachPlan } from '../../core/api';

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Dashboard implements OnInit, OnDestroy {
  private readonly api = inject(Api);
  private pollTimer: ReturnType<typeof setInterval> | null = null;

  readonly status = signal<AppStatus | null>(null);
  readonly coach = signal<CoachPlan | null>(null);
  readonly loading = signal(true);
  readonly syncing = signal(false);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.refresh();
    this.pollTimer = setInterval(() => {
      if (this.syncing() || this.status()?.job_running) {
        this.refresh(false);
      }
    }, 4000);
  }

  ngOnDestroy(): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
    }
  }

  refresh(showLoading = true): void {
    if (showLoading) {
      this.loading.set(true);
    }
    this.error.set(null);
    this.api.getStatus().subscribe({
      next: (s) => {
        this.status.set(s);
        this.syncing.set(s.job_running);
      },
      error: () => this.error.set('Backend nicht erreichbar. Läuft die API auf Port 8000?'),
    });
    this.api.getCoach().subscribe({
      next: (coach) => {
        this.coach.set(coach);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  syncNow(): void {
    this.syncing.set(true);
    this.api.triggerSync().subscribe({
      next: () => this.refresh(false),
      error: (err) => {
        this.syncing.set(false);
        this.error.set(err?.error?.detail || 'Sync fehlgeschlagen');
      },
    });
  }

}
