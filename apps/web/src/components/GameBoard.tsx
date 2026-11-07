import { useMemo, useState } from "react";
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

export function GameBoard({ fen, moves, orientation = "white", disabled = false, onMoveAttempt }: GameBoardProps) {
  const [selectedSquare, setSelectedSquare] = useState<Square | null>(null);
  const [pendingPromotion, setPendingPromotion] = useState<{ from: Square; to: Square } | null>(null);
  const [uciInput, setUciInput] = useState("");
  const chess = useMemo(() => new Chess(fen), [fen]);
  const legalMoves = useMemo(() => selectedSquare ? chess.moves({ square: selectedSquare, verbose: true }) : [], [chess, selectedSquare]);
  const highlightedSquares = useMemo(() => Object.fromEntries(legalMoves.map((move) => [move.to, { boxShadow: "inset 0 0 0 4px rgba(28, 91, 134, 0.5)" }])), [legalMoves]);

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
      if (chess.get(square)) setSelectedSquare(square);
      return;
    }
    const matchingMoves = legalMoves.filter((move) => move.to === square);
    if (matchingMoves.length === 0) {
      setSelectedSquare(chess.get(square) ? square : null);
      return;
    }
    const move = matchingMoves[0];
    if (move.promotion) {
      setPendingPromotion({ from: move.from, to: move.to });
      return;
    }
    attempt(moveToUci(move));
  };

  const handleDrop = ({ sourceSquare, targetSquare }: { sourceSquare: string; targetSquare: string | null }) => {
    if (!isSquare(sourceSquare) || !isSquare(targetSquare) || disabled) return false;
    const matchingMoves = chess.moves({ square: sourceSquare, verbose: true }).filter((move) => move.to === targetSquare);
    if (matchingMoves.length === 0) return false;
    const move = matchingMoves[0];
    if (move.promotion) {
      setPendingPromotion({ from: move.from, to: move.to });
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
          position: fen,
          boardOrientation: orientation,
          allowDragging: !disabled,
          canDragPiece: ({ square }) => !disabled && isSquare(square) && Boolean(chess.get(square)),
          squareStyles: highlightedSquares,
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
      <div className="board-controls">
        <label htmlFor="uci-input">UCI move</label>
        <input id="uci-input" value={uciInput} onChange={(event) => setUciInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") submitUci(); }} placeholder="e2e4" disabled={disabled} />
        <button type="button" onClick={submitUci} disabled={disabled || !isUci(uciInput)}>Submit</button>
      </div>
      <div className="move-history" aria-label="Move history">
        <h3>Move history</h3>
        {moves.length === 0 ? <p>No moves yet.</p> : <ol>{moves.map((move) => <li key={move.ply}>{move.san}</li>)}</ol>}
        <details><summary>PGN</summary><pre>{moves.map((move, index) => `${index % 2 === 0 ? `${Math.floor(index / 2) + 1}. ` : ""}${move.san}`).join(" ")}</pre></details>
      </div>
    </section>
  );
}
