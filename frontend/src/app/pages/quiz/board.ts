import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  input,
  output,
  signal,
} from '@angular/core';
import { Chess, type Square } from 'chess.js';

interface BoardSquare {
  square: Square;
  glyph: string | null;
  color: 'w' | 'b' | null;
  dark: boolean;
  selected: boolean;
  target: boolean;
  capture: boolean;
}

interface PromotionChoice {
  uci: string;
  glyph: string;
  label: string;
}

const GLYPH: Record<string, string> = {
  p: '♟',
  r: '♜',
  n: '♞',
  b: '♝',
  q: '♛',
  k: '♚',
};

@Component({
  selector: 'app-quiz-board',
  templateUrl: './board.html',
  styleUrl: './board.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class QuizBoard {
  readonly fen = input.required<string>();
  readonly revision = input(0);
  readonly locked = input(false);
  readonly played = output<{ uci: string; san: string }>();

  private readonly override = signal<Chess | null>(null);
  private readonly selected = signal<Square | null>(null);
  readonly promotion = signal<{ from: Square; to: Square } | null>(null);

  private live(): Chess {
    return this.override() ?? new Chess(this.fen());
  }

  readonly orientation = computed<'white' | 'black'>(() =>
    new Chess(this.fen()).turn() === 'w' ? 'white' : 'black',
  );

  readonly squares = computed<BoardSquare[]>(() => {
    const game = this.live();
    const selected = this.selected();
    const targets = new Map<string, boolean>();
    if (selected) {
      for (const move of game.moves({ square: selected, verbose: true })) {
        targets.set(move.to, Boolean(move.captured));
      }
    }
    const files = this.orientation() === 'white' ? 'abcdefgh' : 'hgfedcba';
    const ranks = this.orientation() === 'white' ? '87654321' : '12345678';
    const squares: BoardSquare[] = [];
    for (const rank of ranks) {
      for (const file of files) {
        const square = `${file}${rank}` as Square;
        const piece = game.get(square);
        squares.push({
          square,
          glyph: piece ? GLYPH[piece.type] : null,
          color: piece ? piece.color : null,
          dark: (file.charCodeAt(0) + Number(rank)) % 2 === 0,
          selected: selected === square,
          target: targets.has(square),
          capture: targets.get(square) === true,
        });
      }
    }
    return squares;
  });

  readonly promotionChoices = computed<PromotionChoice[]>(() => {
    const pending = this.promotion();
    if (!pending) return [];
    const pieces: Array<{ letter: string; glyph: string; label: string }> = [
      { letter: 'q', glyph: '♛', label: 'Dame' },
      { letter: 'r', glyph: '♜', label: 'Turm' },
      { letter: 'b', glyph: '♝', label: 'Läufer' },
      { letter: 'n', glyph: '♞', label: 'Springer' },
    ];
    return pieces.map((piece) => ({
      uci: `${pending.from}${pending.to}${piece.letter}`,
      glyph: piece.glyph,
      label: piece.label,
    }));
  });

  constructor() {
    effect(() => {
      this.fen();
      this.revision();
      this.override.set(null);
      this.selected.set(null);
      this.promotion.set(null);
    });
  }

  onSquare(square: Square): void {
    if (this.locked() || this.promotion()) return;
    const game = this.live();
    const selected = this.selected();
    if (!selected) {
      const piece = game.get(square);
      if (piece && piece.color === game.turn()) {
        this.selected.set(square);
      }
      return;
    }
    if (selected === square) {
      this.selected.set(null);
      return;
    }
    const piece = game.get(square);
    if (piece && piece.color === game.turn()) {
      this.selected.set(square);
      return;
    }
    const moving = game.get(selected);
    const rank = square[1];
    if (moving?.type === 'p' && (rank === '8' || rank === '1')) {
      this.promotion.set({ from: selected, to: square });
      return;
    }
    this.commit(`${selected}${square}`);
  }

  confirmPromotion(uci: string): void {
    this.promotion.set(null);
    this.commit(uci);
  }

  cancelPromotion(): void {
    this.promotion.set(null);
    this.selected.set(null);
  }

  private commit(uci: string): void {
    const game = new Chess(this.live().fen());
    const from = uci.slice(0, 2) as Square;
    const to = uci.slice(2, 4) as Square;
    const promotion = uci.length > 4 ? uci[4] : undefined;
    const move = game.move({ from, to, promotion });
    if (!move) return;
    this.override.set(game);
    this.selected.set(null);
    this.played.emit({ uci: move.from + move.to + (move.promotion ?? ''), san: move.san });
  }
}
