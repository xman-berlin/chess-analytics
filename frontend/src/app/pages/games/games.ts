import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api, GameListItem } from '../../core/api';

@Component({
  selector: 'app-games',
  imports: [RouterLink],
  templateUrl: './games.html',
  styleUrl: './games.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Games implements OnInit {
  private readonly api = inject(Api);

  readonly items = signal<GameListItem[]>([]);
  readonly total = signal(0);
  readonly filter = signal<string>('');
  readonly analyzedOnly = signal(true);
  readonly loading = signal(true);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api
      .getGames({
        analyzedOnly: this.analyzedOnly(),
        result: this.filter() || undefined,
        limit: 50,
      })
      .subscribe({
        next: (res) => {
          this.items.set(res.items);
          this.total.set(res.total);
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
  }

  setFilter(value: string): void {
    this.filter.set(value);
    this.load();
  }

  setAnalyzedOnly(value: boolean): void {
    this.analyzedOnly.set(value);
    this.load();
  }

  formatDate(endTime: number): string {
    if (!endTime) return '—';
    return new Date(endTime * 1000).toLocaleDateString('de-AT');
  }

  resultLabel(r: string): string {
    return { win: 'Sieg', loss: 'Niederlage', draw: 'Remis' }[r] || r;
  }
}
