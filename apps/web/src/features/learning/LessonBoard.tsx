import { Chess, DEFAULT_POSITION } from "chess.js";
import { useState } from "react";
import type { Language } from "../../api/learningApi";
import { GameBoard, type MoveRecord } from "../../components/GameBoard";

const examples: Record<string, { fen: string; line: string[] }> = {
  "opening-center": { fen: DEFAULT_POSITION, line: ["e2e4", "e7e5", "g1f3"] },
  "king-safety": { fen: "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 2 4", line: ["e1g1"] },
  "forcing-moves": { fen: "4k3/4r3/8/8/8/8/4R3/4K3 w - - 0 1", line: ["e2e7", "e8e7"] },
  "back-rank": { fen: "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1", line: ["d1d8"] },
  "knight-checks": { fen: "6rk/6pp/8/4N3/8/8/8/6K1 w - - 0 1", line: ["e5f7"] },
  promotion: { fen: "8/4P1k1/8/8/8/8/8/6K1 w - - 0 1", line: ["e7e8q"] },
  "en-passant": { fen: "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2", line: ["e5d6"] },
  draws: { fen: "7k/8/5KQ1/8/8/8/8/8 w - - 0 1", line: ["g6f7"] },
};

export function LessonBoard({ lessonId, language }: { lessonId: string; language: Language }) {
  const example = Object.hasOwn(examples, lessonId) ? examples[lessonId] : { fen: DEFAULT_POSITION, line: [] };
  const [position, setPosition] = useState({ fen: example.fen, moves: [] as MoveRecord[] });
  const [boardKey, setBoardKey] = useState(0);
  const ru = language === "ru";

  const play = (fen: string, previous: MoveRecord[], line: string[]) => {
    const chess = new Chess(fen);
    const moves = [...previous];
    for (const uci of line) {
      const move = chess.move(uci);
      moves.push({ ply: moves.length + 1, san: move.san, uci });
    }
    setPosition({ fen: chess.fen(), moves });
  };

  return <section aria-label={ru ? "Практика на доске" : "Board practice"}>
    <p>{ru ? "Попробуйте сделать ход или посмотрите пример к уроку." : "Try a move or play through the lesson example."}</p>
    <div className="game-actions lesson-board-actions">
      {example.line.length > 0 && <button type="button" className="button button-secondary" onClick={() => { play(example.fen, [], example.line); setBoardKey((key) => key + 1); }}>{ru ? "Показать пример" : "Show example"}</button>}
      <button type="button" className="button button-secondary" disabled={position.moves.length === 0} onClick={() => { setPosition({ fen: example.fen, moves: [] }); setBoardKey((key) => key + 1); }}>{ru ? "Сбросить позицию" : "Reset position"}</button>
    </div>
    <GameBoard key={boardKey} fen={position.fen} moves={position.moves} onMoveAttempt={(uci) => play(position.fen, position.moves, [uci])} />
  </section>;
}
