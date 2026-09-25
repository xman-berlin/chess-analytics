import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Api, GameReview, MoveIssue } from '../../core/api';

@Component({
  selector: 'app-game-detail',
  imports: [RouterLink],
  templateUrl: './game-detail.html',
  styleUrl: './game-detail.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GameDetail implements OnInit {
  private readonly api = inject(Api);
  private readonly route = inject(ActivatedRoute);

  readonly game = signal<Record<string, unknown> | null>(null);
  readonly review = signal<GameReview | null>(null);
  readonly issues = signal<MoveIssue[]>([]);
  readonly loading = signal(true);
  readonly focusPly = signal<number | null>(null);

  ngOnInit(): void {
    const ply = this.route.snapshot.queryParamMap.get('ply');
    this.focusPly.set(ply ? Number(ply) : null);
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) return;
    this.api.getGame(id).subscribe({
      next: (res) => {
        this.game.set(res.game);
        this.review.set(res.review);
        this.issues.set(res.issues);
        if (this.focusPly() === null && res.review.ply) {
          this.focusPly.set(res.review.ply);
        }
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  evalWidth(cpl: number): number {
    return Math.min(100, Math.round((cpl / 400) * 100));
  }

  severityClass(s: string): string {
    return `severity-${s}`;
  }
}
