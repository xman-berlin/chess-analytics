import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api, QuizAttemptResult, QuizPayload, QuizPosition } from '../../core/api';
import { QuizBoard } from './board';

@Component({
  selector: 'app-quiz',
  imports: [RouterLink, QuizBoard],
  templateUrl: './quiz.html',
  styleUrl: './quiz.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Quiz implements OnInit {
  private readonly api = inject(Api);

  readonly payload = signal<QuizPayload | null>(null);
  readonly positions = signal<QuizPosition[]>([]);
  readonly feedback = signal<QuizAttemptResult | null>(null);
  readonly loading = signal(true);
  readonly checking = signal(false);
  readonly error = signal<string | null>(null);
  readonly revision = signal(0);
  readonly sessionSolved = signal(0);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.feedback.set(null);
    this.api.getQuiz().subscribe({
      next: (payload) => {
        this.payload.set(payload);
        this.positions.set(payload.positions);
        this.sessionSolved.set(0);
        this.revision.update((n) => n + 1);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Übungen konnten nicht geladen werden. Läuft die API auf Port 8000?');
        this.loading.set(false);
      },
    });
  }

  current(): QuizPosition | null {
    return this.positions()[0] ?? null;
  }

  onPlayed(move: { uci: string; san: string }): void {
    const position = this.current();
    if (!position || this.feedback() || this.checking()) return;
    this.checking.set(true);
    this.error.set(null);
    this.api
      .checkQuiz({ game_id: position.game_id, ply: position.ply, uci: move.uci })
      .subscribe({
        next: (result) => {
          this.feedback.set(result);
          this.checking.set(false);
        },
        error: () => {
          this.checking.set(false);
          this.error.set('Zug konnte nicht geprüft werden.');
          this.revision.update((n) => n + 1);
        },
      });
  }

  next(): void {
    const result = this.feedback();
    const queue = this.positions();
    if (!result || !queue.length) return;
    const [current, ...rest] = queue;
    if (result.correct) {
      this.positions.set(rest);
      this.sessionSolved.update((n) => n + 1);
    } else {
      this.positions.set([...rest, current]);
    }
    this.feedback.set(null);
    this.revision.update((n) => n + 1);
    if (result.correct && rest.length === 0) {
      this.loadMore();
    }
  }

  private loadMore(): void {
    this.api.getQuiz().subscribe({
      next: (payload) => {
        this.payload.set(payload);
        this.positions.set(payload.positions);
        this.revision.update((n) => n + 1);
      },
    });
  }

  reset(): void {
    this.api.resetQuiz().subscribe({
      next: () => this.load(),
      error: () => this.error.set('Zurücksetzen fehlgeschlagen.'),
    });
  }

  formatEval(cp: number | null): string {
    if (cp === null || cp === undefined) return '—';
    if (Math.abs(cp) >= 90000) {
      return cp > 0 ? 'Mattgewinn' : 'Mattverlust';
    }
    const pawns = cp / 100;
    const sign = pawns > 0 ? '+' : '';
    return `${sign}${pawns.toFixed(1)}`;
  }
}
