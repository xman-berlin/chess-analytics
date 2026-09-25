import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api, Curriculum } from '../../core/api';

@Component({
  selector: 'app-curriculum',
  imports: [RouterLink],
  templateUrl: './curriculum.html',
  styleUrl: './curriculum.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CurriculumPage implements OnInit {
  private readonly api = inject(Api);

  readonly curriculum = signal<Curriculum | null>(null);
  readonly loading = signal(true);
  readonly message = signal<string | null>(null);

  ngOnInit(): void {
    this.api.getCoach().subscribe({
      next: (coach) => {
        this.curriculum.set(coach.curriculum);
        this.loading.set(false);
      },
      error: () => {
        this.message.set('Lehrplan konnte nicht geladen werden.');
        this.loading.set(false);
      },
    });
  }
}
