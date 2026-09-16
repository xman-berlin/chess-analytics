import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Api, MoveIssue } from '../../core/api';

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
  readonly issues = signal<MoveIssue[]>([]);
  readonly loading = signal(true);

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) return;
    this.api.getGame(id).subscribe({
      next: (res) => {
        this.game.set(res.game);
        this.issues.set(res.issues);
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
