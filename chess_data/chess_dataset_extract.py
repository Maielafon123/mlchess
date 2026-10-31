import chess
import chess.pgn
import numpy as np


def board_to_tensor(board):
    tensor = np.zeros((12, 8, 8))