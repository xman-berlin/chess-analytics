import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api, QuizAttemptResult, TrainingWeek, WeekPosition } from '../../core/api';
import { QuizBoard } from '../quiz/board';

@Component({
  selector: 'app-plan',
  imports: [RouterLink, QuizBoard],
  templateUrl: './plan.html',
  styleUrl: './plan.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Plan implements OnInit {
  private readonly api = inject(Api);

  readonly week = signal<TrainingWeek | null>(null);
  readonly loading = signal(true);
  readonly message = signal<string | null>(null);
  readonly closing = signal(false);
  readonly checking = signal(false);
  readonly feedback = signal<QuizAttemptResult | null>(null);
  readonly selectedKey = signal<string | null>(null);
  readonly revision = signal(0);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.message.set(null);
    this.api.getWeek().subscribe({
      next: (week) => {
        this.week.set(week);
        this.loading.set(false);
        const current = this.selectedKey();
        const stillThere = week.positions.some((position) => position.key === current);
        if (!stillThere) {
          this.selectedKey.set(week.today_position_key);
        }
      },
      error: () => {
        this.message.set('Die Woche konnte nicht geladen werden. Läuft die API auf Port 8000?');
        this.loading.set(false);
      },
    });
  }

  active(): WeekPosition | null {
    const week = this.week();
    if (!week) return null;
    const key = this.selectedKey() ?? week.today_position_key;
    return week.positions.find((position) => position.key === key) ?? null;
  }

  choose(key: string): void {
    if (this.selectedKey() === key) return;
    this.selectedKey.set(key);
    this.feedback.set(null);
    this.revision.update((value) => value + 1);
  }

  onPlayed(move: { uci: string; san: string }): void {
    const position = this.active();
    if (!position || this.feedback() || this.checking()) return;
    this.checking.set(true);
    this.message.set(null);
    this.api.checkQuiz({ game_id: position.game_id, ply: position.ply, uci: move.uci }).subscribe({
      next: (result) => {
        this.feedback.set(result);
        this.checking.set(false);
        this.load();
      },
      error: () => {
        this.checking.set(false);
        this.message.set('Zug konnte nicht geprüft werden.');
        this.revision.update((value) => value + 1);
      },
    });
  }

  markLine(color: string, name: string, trained: boolean): void {
    this.message.set(null);
    this.api.setOpeningTrained({ color, name, trained, days: 90 }).subscribe({
      next: () => this.load(),
      error: () => this.message.set('Die Linie konnte nicht gespeichert werden.'),
    });
  }

  closeWeek(): void {
    this.closing.set(true);
    this.message.set(null);
    this.api.closeWeek().subscribe({
      next: (week) => {
        this.week.set(week);
        this.selectedKey.set(week.today_position_key);
        this.feedback.set(null);
        this.closing.set(false);
      },
      error: () => {
        this.closing.set(false);
        this.message.set('Der Check konnte nicht gespeichert werden.');
      },
    });
  }
}
