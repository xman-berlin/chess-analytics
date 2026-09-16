import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { Api } from '../../core/api';

@Component({
  selector: 'app-settings',
  templateUrl: './settings.html',
  styleUrl: './settings.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Settings implements OnInit {
  private readonly api = inject(Api);
  readonly settings = signal<Record<string, unknown> | null>(null);

  ngOnInit(): void {
    this.api.getSettings().subscribe({
      next: (s) => this.settings.set(s),
    });
  }
}
