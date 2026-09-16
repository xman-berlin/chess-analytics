import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api, PlanTask, PlanTaskLink, TrainingPlan } from '../../core/api';

@Component({
  selector: 'app-plan',
  imports: [RouterLink],
  templateUrl: './plan.html',
  styleUrl: './plan.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Plan implements OnInit {
  private readonly api = inject(Api);

  readonly plan = signal<TrainingPlan | null>(null);
  readonly loading = signal(true);
  readonly message = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api.getPlan().subscribe({
      next: (p) => {
        this.plan.set(p);
        this.loading.set(false);
      },
      error: () => {
        this.message.set('Plan konnte nicht geladen werden.');
        this.loading.set(false);
      },
    });
  }

  refresh(): void {
    this.api.refreshPlan().subscribe({
      next: (p) => {
        this.plan.set(p);
        this.message.set('Plan aktualisiert.');
      },
      error: () => this.message.set('Aktualisierung fehlgeschlagen.'),
    });
  }

  toggle(itemId: string, completed: boolean): void {
    this.api.updatePlanItem(itemId, completed).subscribe({
      next: () => {
        const current = this.plan();
        if (!current) return;
        this.plan.set({
          ...current,
          items: current.items.map((i) => (i.id === itemId ? { ...i, completed } : i)),
        });
      },
    });
  }

  taskText(task: string | PlanTask): string {
    return typeof task === 'string' ? task : task.text;
  }

  taskLinks(task: string | PlanTask): PlanTaskLink[] {
    if (typeof task === 'string') return [];
    return task.links ?? [];
  }
}
