import { Chess, DEFAULT_POSITION } from "chess.js";
import { useRef, useState } from "react";
import type { Language } from "../../api/learningApi";
import { GameBoard, type MoveRecord } from "../../components/GameBoard";
import { CoachAvatar } from "../../components/CoachAvatar";

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

export function LessonBoard({ lessonId, language, onComplete, completed = false, disabled = false }: { lessonId: string; language: Language; onComplete?: () => void; completed?: boolean; disabled?: boolean }) {
  const example = Object.hasOwn(examples, lessonId) ? examples[lessonId] : { fen: DEFAULT_POSITION, line: [] };
  const [position, setPosition] = useState({ fen: example.fen, moves: [] as MoveRecord[] });
  const [boardKey, setBoardKey] = useState(0);
  const [feedback, setFeedback] = useState<{ uci: string; expected: boolean; scored: boolean } | null>(null);
  const [solved, setSolved] = useState(false);
  const completionSent = useRef(completed);
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
  const attempt = (uci: string) => {
    const first = position.moves.length === 0;
    const expected = first && uci === example.line[0];
    const objective = first && ["back-rank", "knight-checks"].includes(lessonId);
    const board = new Chess(position.fen);
    board.move(uci);
    const correct = objective ? board.isCheckmate() : expected;
    setFeedback({ uci, expected: correct, scored: objective || expected });
    if (correct) {
      setSolved(true);
      // The curated line is legal and gives the student the opponent's forced reply.
      play(example.fen, [], example.line);
      if (!completionSent.current) {
        completionSent.current = true;
        onComplete?.();
      }
    } else {
      play(position.fen, position.moves, [uci]);
    }
  };

  const coachMessage = completed || solved
    ? (ru ? "Урок завершён. Можно повторить вариант на доске." : "Lesson complete. You can replay the variation on the board.")
    : feedback?.expected
    ? (ru ? "Верное решение. Урок завершён, прогресс сохранён." : "Correct solution. Lesson complete and progress saved.")
    : feedback?.scored
      ? (ru ? "Ошибка в решении: этот ход не достигает цели упражнения. Попробуйте ещё раз." : "That move does not solve the exercise. Reset the position and try again.")
      : feedback
        ? (ru ? "Ход легален. Сравните его с целью урока." : "The move is legal. Compare it with the lesson goal.")
        : (ru ? "Сделайте ход на доске — я проверю решение." : "Play a move on the board and I’ll check the exercise.");
  return <section aria-label={ru ? "Практика на доске" : "Board practice"} className="lesson-practice">
    <div className="lesson-practice-layout">
      <div className="lesson-board-column">
        <div className="game-actions lesson-board-actions">
          {example.line.length > 0 && <button type="button" className="button button-secondary" disabled={disabled || completed || solved} onClick={() => { setFeedback(null); play(example.fen, [], example.line); setBoardKey((key) => key + 1); }}>{ru ? "Показать пример" : "Show example"}</button>}
          <button type="button" className="button button-secondary" disabled={disabled || completed || solved || position.moves.length === 0} onClick={() => { setFeedback(null); setPosition({ fen: example.fen, moves: [] }); setBoardKey((key) => key + 1); }}>{ru ? "Сбросить позицию" : "Reset position"}</button>
        </div>
        <GameBoard key={boardKey} fen={position.fen} moves={position.moves} disabled={disabled || completed || solved} onMoveAttempt={attempt}
          feedback={feedback?.scored ? { uci: feedback.uci, tone: feedback.expected ? "good" : "bad" } : undefined} />
      </div>
      <aside className="lesson-coach" aria-live="polite"><CoachAvatar title={ru ? "ИИ-тренер" : "AI coach"}>{coachMessage}</CoachAvatar>
      </aside>
    </div>
  </section>;
}
