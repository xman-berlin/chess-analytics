import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

const API = 'http://localhost:8000/api';

export interface AppStatus {
  username: string;
  time_classes: string[];
  sync: {
    last_sync_at: string | null;
    last_analysis_at: string | null;
    games_synced: number;
    games_analyzed: number;
    status: string;
    message: string | null;
  } | null;
  job_running: boolean;
  totals: { games: number; analyzed: number };
  player: { avatar?: string; name?: string; url?: string };
  rating: {
    daily?: number;
    daily_best?: number;
    record?: { win: number; loss: number; draw: number; timeout_percent?: number };
  };
  tactics?: { highest?: { rating: number }; lowest?: { rating: number } };
}

export interface Insights {
  window: number;
  games_count: number;
  top_weaknesses: Array<{
    id: string;
    title: string;
    severity: string;
    metric: string;
    why: string;
  }>;
  by_phase: Record<
    string,
    {
      avg_acpl: number | null;
      blunders: number;
      mistakes: number;
      inaccuracies: number;
      issue_count: number;
    }
  >;
  openings: Array<{
    name: string;
    eco: string | null;
    games: number;
    wins: number;
    losses: number;
    draws: number;
    score: number;
    avg_acpl: number | null;
  }>;
  motifs: Array<{ motif: string; count: number }>;
  record: { win: number; loss: number; draw: number };
  avg_acpl: number | null;
  critical_positions: Array<{
    game_id: string;
    game_url: string | null;
    ply: number;
    move_san: string;
    best_move_san: string | null;
    cpl: number;
    phase: string;
    motif: string | null;
    fen_before: string;
  }>;
  avg_blunders_per_game: number;
}

export interface PlanTaskLink {
  label: string;
  url: string;
  hint?: string;
}

export interface PlanTask {
  text: string;
  links?: PlanTaskLink[];
}

export interface PlanItem {
  id: string;
  priority: number;
  title: string;
  why: string;
  metric: string;
  severity: string;
  tasks: Array<string | PlanTask>;
  completed: boolean;
  critical_refs?: Array<{ game_id: string; ply: number; fen: string; url: string | null }>;
  openings?: Array<{ name: string; games: number; score: number }>;
}

export interface TrainingPlan {
  generated_at: string | null;
  window_size?: number;
  items: PlanItem[];
  insights_summary?: Record<string, unknown>;
  message?: string;
}

export interface GameListItem {
  id: string;
  url: string;
  time_class: string;
  white_username: string;
  black_username: string;
  white_rating: number;
  black_rating: number;
  user_color: string;
  user_result: string;
  opening_eco: string | null;
  opening_name: string | null;
  end_time: number;
  analyzed: number;
  acpl: number | null;
  blunders: number | null;
  mistakes: number | null;
  inaccuracies: number | null;
}

export interface LeakBucket {
  games: number;
  thrown_wins: number;
  thrown_draws: number;
  lost_early: number;
  other: number;
}

export interface LeakReport {
  target_rating: number;
  window: number;
  recent: LeakBucket;
  prior: LeakBucket;
  focus: 'thrown_win' | 'thrown_draw' | 'lost_early' | null;
  focus_label: string | null;
  focus_why: string | null;
  prompt: string | null;
}

export interface QuizPosition {
  game_id: string;
  ply: number;
  fen: string;
  opening_name: string | null;
  user_result: string | null;
  phase: string | null;
  eval_before: number;
  cpl: number | null;
  url: string | null;
}

export interface QuizPayload {
  target_rating: number;
  focus: LeakReport['focus'];
  focus_label: string | null;
  focus_why: string | null;
  prompt: string | null;
  available: number;
  solved: number;
  positions: QuizPosition[];
}

export interface GameReview {
  category: string;
  label: string | null;
  opponent: string | null;
  result: string | null;
  result_word: string;
  ply: number | null;
  move_san: string | null;
  best_move_san: string | null;
  opening_name: string | null;
  headline: string;
  detail: string;
  game_id?: string;
  url?: string | null;
}

export interface CoachTask {
  kind: 'practice' | 'game' | 'review';
  text: string;
}

export interface CurriculumSession {
  label: string;
  minutes: number;
  text: string;
  route?: string;
  url?: string;
  url_label?: string;
}

export interface CurriculumArea {
  id: string;
  title: string;
  summary: string;
  emphasis: boolean;
  sessions: CurriculumSession[];
}

export interface CurriculumDay {
  day: string;
  area: string;
  title: string;
  minutes: number;
  detail: string;
  steps: string[];
  emphasis: boolean;
}

export interface Curriculum {
  intro: string;
  guidelines: string[];
  areas: CurriculumArea[];
  week: CurriculumDay[];
  emphasis: string[];
  focus_label: string | null;
}

export interface CoachPlan {
  target_rating: number;
  rating: number | null;
  best_rating: number | null;
  level_label: string;
  level_principle: string;
  diagnosis: string;
  progress: string | null;
  focus: LeakReport['focus'];
  focus_label: string | null;
  assignment_title: string;
  tasks: CoachTask[];
  withheld: string[];
  practice: { available: number; solved: number };
  latest_game: GameReview | null;
  recent: LeakBucket;
  prior: LeakBucket;
  curriculum: Curriculum;
}

export interface QuizAttemptResult {
  correct: boolean;
  best_san: string;
  played_san: string | null;
  attempt_san: string;
  why: string;
}

export interface MoveIssue {
  id: number;
  game_id: string;
  ply: number;
  move_san: string;
  severity: string;
  phase: string;
  cpl: number;
  eval_before: number;
  eval_after: number;
  best_move_san: string | null;
  motif: string | null;
  fen_before: string;
}

@Injectable({ providedIn: 'root' })
export class Api {
  private readonly http = inject(HttpClient);

  getStatus(): Observable<AppStatus> {
    return this.http.get<AppStatus>(`${API}/status`);
  }

  triggerSync(full = false): Observable<{ status: string; message?: string }> {
    const params = new HttpParams().set('full', String(full)).set('background', 'true');
    return this.http.post<{ status: string; message?: string }>(`${API}/sync`, null, { params });
  }

  getCoach(): Observable<CoachPlan> {
    return this.http.get<CoachPlan>(`${API}/coach`);
  }

  getLeaks(window = 20): Observable<LeakReport> {
    return this.http.get<LeakReport>(`${API}/leaks`, {
      params: new HttpParams().set('window', window),
    });
  }

  getQuiz(window = 20): Observable<QuizPayload> {
    return this.http.get<QuizPayload>(`${API}/quiz`, {
      params: new HttpParams().set('window', window),
    });
  }

  checkQuiz(body: { game_id: string; ply: number; uci: string }): Observable<QuizAttemptResult> {
    return this.http.post<QuizAttemptResult>(`${API}/quiz/attempts`, body);
  }

  resetQuiz(): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(`${API}/quiz/reset`, null);
  }

  getInsights(window = 40): Observable<Insights> {
    return this.http.get<Insights>(`${API}/insights`, {
      params: new HttpParams().set('window', window),
    });
  }

  getPlan(): Observable<TrainingPlan> {
    return this.http.get<TrainingPlan>(`${API}/plan`);
  }

  refreshPlan(): Observable<TrainingPlan> {
    return this.http.post<TrainingPlan>(`${API}/plan/refresh`, null);
  }

  updatePlanItem(itemId: string, completed: boolean): Observable<{ id: string; completed: boolean }> {
    return this.http.patch<{ id: string; completed: boolean }>(`${API}/plan/items/${itemId}`, {
      completed,
    });
  }

  getGames(opts: {
    analyzedOnly?: boolean;
    result?: string;
    limit?: number;
    offset?: number;
  } = {}): Observable<{ total: number; items: GameListItem[] }> {
    let params = new HttpParams()
      .set('limit', String(opts.limit ?? 50))
      .set('offset', String(opts.offset ?? 0));
    if (opts.analyzedOnly) {
      params = params.set('analyzed_only', 'true');
    }
    if (opts.result) {
      params = params.set('result', opts.result);
    }
    return this.http.get<{ total: number; items: GameListItem[] }>(`${API}/games`, { params });
  }

  getGame(id: string): Observable<{
    game: GameListItem & Record<string, unknown>;
    issues: MoveIssue[];
    review: GameReview;
  }> {
    return this.http.get<{
      game: GameListItem & Record<string, unknown>;
      issues: MoveIssue[];
      review: GameReview;
    }>(`${API}/games/${id}`);
  }

  getSettings(): Observable<Record<string, unknown>> {
    return this.http.get<Record<string, unknown>>(`${API}/settings`);
  }
}
