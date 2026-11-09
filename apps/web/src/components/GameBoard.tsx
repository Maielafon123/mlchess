import { useId, useMemo, useState, type CSSProperties } from "react";
import { Chess, type Move, type Square } from "chess.js";
import { Chessboard } from "react-chessboard";

export type MoveRecord = {
  ply: number;
  san: string;
  uci: string;
};

type PromotionPiece = "q" | "r" | "b" | "n";

export type GameBoardProps = {
  fen: string;
  moves: MoveRecord[];
  orientation?: "white" | "black";
  disabled?: boolean;
  showHistory?: boolean;
  lastMove?: string | null;
  feedback?: { uci: string; tone: "good" | "bad" };
  onMoveAttempt: (uci: string) => void;
};

const promotionPieces: Array<{ value: PromotionPiece; label: string }> = [
  { value: "q", label: "Queen" },
  { value: "r", label: "Rook" },
  { value: "b", label: "Bishop" },
  { value: "n", label: "Knight" },
];

function isSquare(value: string | null): value is Square {
  return value !== null && /^[a-h][1-8]$/.test(value);
}

function isUci(value: string) {
  return /^[a-h][1-8][a-h][1-8][qrbn]?$/.test(value.trim());
}

function moveToUci(move: Move) {
  return `${move.from}${move.to}${move.promotion ?? ""}`;
}

export function GameBoard({ fen, moves, orientation = "white", disabled = false, showHistory = true, lastMove = moves.at(-1)?.uci, feedback, onMoveAttempt }: GameBoardProps) {
  const inputId = useId();
  const boardId = `board-${inputId.replace(/[^\w-]/g, "")}`;
  const [selection, setSelection] = useState<{ fen: string; square: Square } | null>(null);
  const selectedSquare = !disabled && selection?.fen === fen ? selection.square : null;
  const setSelectedSquare = (square: Square | null) => setSelection(square ? { fen, square } : null);
  const [promotion, setPendingPromotion] = useState<{ fen: string; from: Square; to: Square } | null>(null);
  const pendingPromotion = !disabled && promotion?.fen === fen ? promotion : null;
  const [uciInput, setUciInput] = useState("");
  const chess = useMemo(() => new Chess(fen), [fen]);
  const legalMoves = useMemo(() => selectedSquare ? chess.moves({ square: selectedSquare, verbose: true }) : [], [chess, selectedSquare]);
  const squareStyles: Record<string, CSSProperties> = {};
  const mark = (uci: string, color: string) => {
    for (const square of [uci.slice(0, 2), uci.slice(2, 4)]) {
      squareStyles[square] = { boxShadow: `inset 0 0 0 3px ${color}` };
    }
  };
  if (lastMove) mark(lastMove, "var(--color-accent-strong)");
  if (feedback) mark(feedback.uci, feedback.tone === "good" ? "var(--color-success)" : "var(--color-danger)");
  if (selectedSquare) squareStyles[selectedSquare] = { boxShadow: "inset 0 0 0 4px var(--color-accent-strong)" };
  for (const move of legalMoves) {
    squareStyles[move.to] = { ...squareStyles[move.to], backgroundImage: move.captured
      ? "radial-gradient(circle, transparent 57%, #25231e80 60%, #25231e80 67%, transparent 70%)"
      : "radial-gradient(circle, #25231e80 0 16%, transparent 18%)" };
  }
  const selectable = (square: Square) => chess.get(square)?.color === chess.turn();

  const attempt = (uci: string) => {
    if (disabled || !isUci(uci)) return false;
    const probe = new Chess(fen);
    try {
      probe.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] as PromotionPiece | undefined });
    } catch {
      return false;
    }
    onMoveAttempt(uci);
    setSelectedSquare(null);
    setPendingPromotion(null);
    return true;
  };

  const selectSquare = (square: string) => {
    if (disabled) return;
    if (!isSquare(square)) return;
    if (selectedSquare === null) {
      if (selectable(square)) setSelectedSquare(square);
      return;
    }
    const matchingMoves = legalMoves.filter((move) => move.to === square);
    if (matchingMoves.length === 0) {
      setSelectedSquare(square !== selectedSquare && selectable(square) ? square : null);
      return;
    }
    const move = matchingMoves[0];
    if (move.promotion) {
      setPendingPromotion({ fen, from: move.from, to: move.to });
      return;
    }
    attempt(moveToUci(move));
  };

  const handleDrop = ({ sourceSquare, targetSquare }: { sourceSquare: string; targetSquare: string | null }) => {
    if (!isSquare(sourceSquare) || !isSquare(targetSquare) || disabled) {
      setSelectedSquare(null);
      return false;
    }
    const matchingMoves = chess.moves({ square: sourceSquare, verbose: true }).filter((move) => move.to === targetSquare);
    if (matchingMoves.length === 0) {
      setSelectedSquare(null);
      return false;
    }
    const move = matchingMoves[0];
    if (move.promotion) {
      setPendingPromotion({ fen, from: move.from, to: move.to });
      return false;
    }
    return attempt(moveToUci(move));
  };

  const submitUci = () => {
    const value = uciInput.trim().toLowerCase();
    if (attempt(value)) setUciInput("");
  };

  return (
    <section className="game-board" aria-label="Game board">
      <div className="board-frame">
        <Chessboard options={{
          id: boardId,
          position: fen,
          boardOrientation: orientation,
          darkSquareStyle: { backgroundColor: "var(--color-board-dark)" },
          lightSquareStyle: { backgroundColor: "var(--color-board-light)" },
          allowDragging: !disabled,
          dragActivationDistance: 6,
          animationDurationInMs: 150,
          canDragPiece: ({ square }) => !disabled && isSquare(square) && selectable(square),
          onPieceDrag: ({ square }) => { if (isSquare(square)) setSelectedSquare(square); },
          onPieceDragCancel: () => setSelectedSquare(null),
          squareStyles,
          onSquareClick: ({ square }) => selectSquare(square),
          onPieceDrop: handleDrop,
        }} />
      </div>
      {pendingPromotion && (
        <div className="promotion-picker" role="group" aria-label="Choose promotion piece">
          {promotionPieces.map((piece) => (
            <button key={piece.value} type="button" onClick={() => attempt(`${pendingPromotion.from}${pendingPromotion.to}${piece.value}`)}>{piece.label}</button>
          ))}
        </div>
      )}
      <details className="board-input"><summary>Ввести ход с клавиатуры</summary><div className="board-controls">
        <label htmlFor={inputId}>UCI move</label>
        <input id={inputId} value={uciInput} onChange={(event) => setUciInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") submitUci(); }} placeholder="e2e4" disabled={disabled} />
        <button type="button" onClick={submitUci} disabled={disabled || !isUci(uciInput)}>Submit</button>
      </div></details>
      {showHistory && <div className="move-history" aria-label="Move history">
        <h3>Move history</h3>
        {moves.length === 0 ? <p>No moves yet.</p> : <ol>{moves.map((move) => <li key={move.ply}><span className="move-number">{move.ply % 2 ? Math.ceil(move.ply / 2) + ". " : "… "}</span><span>{move.san}</span></li>)}</ol>}
        <details><summary>PGN</summary><pre>{moves.map((move, index) => `${index % 2 === 0 ? `${Math.floor(index / 2) + 1}. ` : ""}${move.san}`).join(" ")}</pre></details>
      </div>}
    </section>
  );
}
