"""Neon themed chess game for Pythonista 3.

This module uses Pythonista's ``scene`` framework to render a brightly
colored chess board and allow touch-based play that follows the standard
rules of chess (with automatic promotion to a queen).  The script is
self-contained and can be copied directly into Pythonista on iOS.  Run the
module to launch the interactive game.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:  # Pythonista supplies ``scene`` and ``ui``.
    from scene import Action, Color, LabelNode, Node, Scene, ShapeNode, run
    import ui
except ImportError as exc:  # pragma: no cover - makes local linting friendlier.
    raise SystemExit(
        "This module must be executed inside Pythonista 3, which provides the"
        " 'scene' and 'ui' modules."
    ) from exc


# ---------------------------------------------------------------------------
# Chess engine
# ---------------------------------------------------------------------------

FILES = "abcdefgh"
RANKS = "12345678"


@dataclass(frozen=True)
class Piece:
    color: str  # 'w' or 'b'
    kind: str   # 'K', 'Q', 'R', 'B', 'N', 'P'

    def symbol(self) -> str:
        return self.kind if self.color == "w" else self.kind.lower()


@dataclass(frozen=True)
class Move:
    from_sq: int
    to_sq: int
    promotion: Optional[str] = None
    is_en_passant: bool = False
    is_castle: Optional[str] = None  # 'K' or 'Q'

    def __str__(self) -> str:
        promo = f"={self.promotion}" if self.promotion else ""
        return f"{square_name(self.from_sq)}{square_name(self.to_sq)}{promo}"


def square(file_index: int, rank_index: int) -> int:
    return rank_index * 8 + file_index


def square_name(index: int) -> str:
    return f"{FILES[index % 8]}{RANKS[index // 8]}"


START_PIECES: Sequence[Optional[Piece]] = (
    Piece("w", "R"), Piece("w", "N"), Piece("w", "B"), Piece("w", "Q"),
    Piece("w", "K"), Piece("w", "B"), Piece("w", "N"), Piece("w", "R"),
    *(Piece("w", "P") for _ in range(8)),
    *(None for _ in range(32)),
    *(Piece("b", "P") for _ in range(8)),
    Piece("b", "R"), Piece("b", "N"), Piece("b", "B"), Piece("b", "Q"),
    Piece("b", "K"), Piece("b", "B"), Piece("b", "N"), Piece("b", "R"),
)


class Board:
    """A minimal chess rules implementation suitable for casual play."""

    def __init__(
        self,
        pieces: Optional[Sequence[Optional[Piece]]] = None,
        to_move: str = "w",
        castling: Optional[Iterable[str]] = None,
        en_passant: Optional[int] = None,
        halfmove_clock: int = 0,
        fullmove_number: int = 1,
    ) -> None:
        self.pieces: List[Optional[Piece]] = list(pieces or START_PIECES)
        self.to_move = to_move
        self.castling = set(castling or "KQkq")
        self.en_passant = en_passant
        self.halfmove_clock = halfmove_clock
        self.fullmove_number = fullmove_number

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def copy(self) -> "Board":
        return Board(
            pieces=list(self.pieces),
            to_move=self.to_move,
            castling=set(self.castling),
            en_passant=self.en_passant,
            halfmove_clock=self.halfmove_clock,
            fullmove_number=self.fullmove_number,
        )

    def piece_at(self, index: int) -> Optional[Piece]:
        return self.pieces[index]

    def locate_king(self, color: str) -> int:
        for i, piece in enumerate(self.pieces):
            if piece and piece.color == color and piece.kind == "K":
                return i
        raise ValueError(f"King for {color} not found")

    # ------------------------------------------------------------------
    # Move generation
    # ------------------------------------------------------------------
    def generate_legal_moves(self) -> List[Move]:
        moves = []
        for move in self.generate_pseudo_legal_moves():
            temp = self.copy()
            temp.apply_move(move)
            if not temp.is_in_check(opposite(temp.to_move)):
                moves.append(move)
        return moves

    def generate_pseudo_legal_moves(self) -> Iterable[Move]:
        for index, piece in enumerate(self.pieces):
            if not piece or piece.color != self.to_move:
                continue
            if piece.kind == "P":
                yield from self._pawn_moves(index, piece)
            elif piece.kind == "N":
                yield from self._knight_moves(index, piece)
            elif piece.kind == "B":
                yield from self._slider_moves(index, piece, ((1, 1), (1, -1), (-1, 1), (-1, -1)))
            elif piece.kind == "R":
                yield from self._slider_moves(index, piece, ((1, 0), (-1, 0), (0, 1), (0, -1)))
            elif piece.kind == "Q":
                yield from self._slider_moves(index, piece, (
                    (1, 0), (-1, 0), (0, 1), (0, -1),
                    (1, 1), (1, -1), (-1, 1), (-1, -1),
                ))
            elif piece.kind == "K":
                yield from self._king_moves(index, piece)

    def _pawn_moves(self, index: int, piece: Piece) -> Iterable[Move]:
        direction = 1 if piece.color == "w" else -1
        rank = index // 8
        file = index % 8
        start_rank = 1 if piece.color == "w" else 6
        promotion_rank = 7 if piece.color == "w" else 0

        forward = index + direction * 8
        if in_bounds_square(forward) and not self.piece_at(forward):
            if forward // 8 == promotion_rank:
                for promo in "QRBN":
                    yield Move(index, forward, promotion=promo)
            else:
                yield Move(index, forward)
            # double push
            if rank == start_rank:
                double_forward = index + direction * 16
                if in_bounds_square(double_forward) and not self.piece_at(double_forward):
                    yield Move(index, double_forward)

        # captures
        for df in (-1, 1):
            file_target = file + df
            if not 0 <= file_target < 8:
                continue
            target = forward + df
            if not in_bounds_square(target):
                continue
            target_piece = self.piece_at(target)
            if target_piece and target_piece.color != piece.color:
                if target // 8 == promotion_rank:
                    for promo in "QRBN":
                        yield Move(index, target, promotion=promo)
                else:
                    yield Move(index, target)

        # en passant
        if self.en_passant is not None:
            ep_rank = self.en_passant // 8
            if ep_rank == (5 if piece.color == "w" else 2) and abs((self.en_passant % 8) - file) == 1:
                yield Move(index, self.en_passant, is_en_passant=True)

    def _knight_moves(self, index: int, piece: Piece) -> Iterable[Move]:
        rank = index // 8
        file = index % 8
        for dr, df in ((2, 1), (1, 2), (-1, 2), (-2, 1), (-2, -1), (-1, -2), (1, -2), (2, -1)):
            r = rank + dr
            f = file + df
            if not (0 <= r < 8 and 0 <= f < 8):
                continue
            target = square(f, r)
            target_piece = self.piece_at(target)
            if not target_piece or target_piece.color != piece.color:
                yield Move(index, target)

    def _slider_moves(self, index: int, piece: Piece, directions: Sequence[Tuple[int, int]]) -> Iterable[Move]:
        rank = index // 8
        file = index % 8
        for df, dr in directions:
            r = rank + dr
            f = file + df
            while 0 <= r < 8 and 0 <= f < 8:
                target = square(f, r)
                target_piece = self.piece_at(target)
                if not target_piece:
                    yield Move(index, target)
                else:
                    if target_piece.color != piece.color:
                        yield Move(index, target)
                    break
                r += dr
                f += df

    def _king_moves(self, index: int, piece: Piece) -> Iterable[Move]:
        rank = index // 8
        file = index % 8
        for dr in (-1, 0, 1):
            for df in (-1, 0, 1):
                if dr == df == 0:
                    continue
                r = rank + dr
                f = file + df
                if not (0 <= r < 8 and 0 <= f < 8):
                    continue
                target = square(f, r)
                target_piece = self.piece_at(target)
                if not target_piece or target_piece.color != piece.color:
                    yield Move(index, target)

        # castling
        if piece.color == "w":
            back_rank = 0
            king_side = "K"
            queen_side = "Q"
            rook_king_square = square(7, 0)
            rook_queen_square = square(0, 0)
        else:
            back_rank = 7
            king_side = "k"
            queen_side = "q"
            rook_king_square = square(7, 7)
            rook_queen_square = square(0, 7)

        if king_side in self.castling:
            if all(
                self.piece_at(square(f, back_rank)) is None
                for f in (5, 6)
            ) and not self._castle_through_check(piece.color, (square(5, back_rank), square(6, back_rank))):
                rook_piece = self.piece_at(rook_king_square)
                if rook_piece and rook_piece.kind == "R" and rook_piece.color == piece.color:
                    yield Move(index, square(6, back_rank), is_castle="K")

        if queen_side in self.castling:
            if all(
                self.piece_at(square(f, back_rank)) is None
                for f in (1, 2, 3)
            ) and not self._castle_through_check(piece.color, (square(2, back_rank), square(3, back_rank))):
                rook_piece = self.piece_at(rook_queen_square)
                if rook_piece and rook_piece.kind == "R" and rook_piece.color == piece.color:
                    yield Move(index, square(2, back_rank), is_castle="Q")

    def _castle_through_check(self, color: str, squares_to_check: Sequence[int]) -> bool:
        king_square = self.locate_king(color)
        if self.is_square_attacked(king_square, opposite(color)):
            return True
        for sq in squares_to_check:
            temp = self.copy()
            temp.apply_move(Move(king_square, sq))
            if temp.is_in_check(color):
                return True
        return False

    # ------------------------------------------------------------------
    def apply_move(self, move: Move) -> None:
        moving_piece = self.pieces[move.from_sq]
        if not moving_piece:
            raise ValueError("No piece to move")

        captured_piece = self.pieces[move.to_sq]
        is_pawn_move = moving_piece.kind == "P"

        if move.is_en_passant:
            direction = 1 if moving_piece.color == "w" else -1
            captured_square = move.to_sq - direction * 8
            captured_piece = self.pieces[captured_square]
            self.pieces[captured_square] = None

        self.pieces[move.from_sq] = None
        self.pieces[move.to_sq] = moving_piece

        # promotion
        if move.promotion:
            self.pieces[move.to_sq] = Piece(moving_piece.color, move.promotion)

        # castling rook move
        if move.is_castle:
            if moving_piece.color == "w":
                rank = 0
            else:
                rank = 7
            if move.is_castle == "K":
                rook_from = square(7, rank)
                rook_to = square(5, rank)
            else:
                rook_from = square(0, rank)
                rook_to = square(3, rank)
            self.pieces[rook_to] = self.pieces[rook_from]
            self.pieces[rook_from] = None

        # update castling rights
        if moving_piece.kind == "K":
            for flag in ("K", "Q") if moving_piece.color == "w" else ("k", "q"):
                self.castling.discard(flag)
        if moving_piece.kind == "R":
            self._remove_rook_castling_right(move.from_sq)
        if captured_piece and captured_piece.kind == "R":
            self._remove_rook_castling_right(move.to_sq)

        # en passant target square
        if is_pawn_move and abs(move.to_sq - move.from_sq) == 16:
            self.en_passant = (move.from_sq + move.to_sq) // 2
        else:
            self.en_passant = None

        self.halfmove_clock = 0 if is_pawn_move or captured_piece else self.halfmove_clock + 1
        if moving_piece.color == "b":
            self.fullmove_number += 1

        self.to_move = opposite(self.to_move)

    def _remove_rook_castling_right(self, square_index: int) -> None:
        if square_index == square(0, 0):
            self.castling.discard("Q")
        elif square_index == square(7, 0):
            self.castling.discard("K")
        elif square_index == square(0, 7):
            self.castling.discard("q")
        elif square_index == square(7, 7):
            self.castling.discard("k")

    # ------------------------------------------------------------------
    def is_in_check(self, color: str) -> bool:
        king_square = self.locate_king(color)
        return self.is_square_attacked(king_square, opposite(color))

    def is_square_attacked(self, square_index: int, by_color: str) -> bool:
        rank = square_index // 8
        file = square_index % 8

        # pawns
        pawn_direction = 1 if by_color == "w" else -1
        for df in (-1, 1):
            r = rank + pawn_direction
            f = file + df
            if 0 <= r < 8 and 0 <= f < 8:
                piece = self.piece_at(square(f, r))
                if piece and piece.color == by_color and piece.kind == "P":
                    return True

        # knights
        for dr, df in ((2, 1), (1, 2), (-1, 2), (-2, 1), (-2, -1), (-1, -2), (1, -2), (2, -1)):
            r = rank + dr
            f = file + df
            if 0 <= r < 8 and 0 <= f < 8:
                piece = self.piece_at(square(f, r))
                if piece and piece.color == by_color and piece.kind == "N":
                    return True

        # sliders
        for df, dr, kinds in (
            (1, 0, ("R", "Q")), (-1, 0, ("R", "Q")), (0, 1, ("R", "Q")), (0, -1, ("R", "Q")),
            (1, 1, ("B", "Q")), (1, -1, ("B", "Q")), (-1, 1, ("B", "Q")), (-1, -1, ("B", "Q")),
        ):
            r = rank + dr
            f = file + df
            while 0 <= r < 8 and 0 <= f < 8:
                piece = self.piece_at(square(f, r))
                if piece:
                    if piece.color == by_color and piece.kind in kinds:
                        return True
                    break
                r += dr
                f += df

        # king
        for dr in (-1, 0, 1):
            for df in (-1, 0, 1):
                if dr == df == 0:
                    continue
                r = rank + dr
                f = file + df
                if 0 <= r < 8 and 0 <= f < 8:
                    piece = self.piece_at(square(f, r))
                    if piece and piece.color == by_color and piece.kind == "K":
                        return True
        return False

    # ------------------------------------------------------------------
    def result(self) -> Optional[str]:
        legal_moves = list(self.generate_legal_moves())
        if legal_moves:
            return None
        if self.is_in_check(self.to_move):
            return "0-1" if self.to_move == "w" else "1-0"
        return "1/2-1/2"


def in_bounds_square(index: int) -> bool:
    return 0 <= index < 64


def opposite(color: str) -> str:
    return "b" if color == "w" else "w"


UNICODE_PIECES = {
    ("w", "K"): "♔",
    ("w", "Q"): "♕",
    ("w", "R"): "♖",
    ("w", "B"): "♗",
    ("w", "N"): "♘",
    ("w", "P"): "♙",
    ("b", "K"): "♚",
    ("b", "Q"): "♛",
    ("b", "R"): "♜",
    ("b", "B"): "♝",
    ("b", "N"): "♞",
    ("b", "P"): "♟",
}


# ---------------------------------------------------------------------------
# Scene configuration
# ---------------------------------------------------------------------------

# Edit the palette below to create different neon experiences.


def color_rgba(*components: float) -> Color:
    """Return a :class:`Color` with a guaranteed alpha channel.

    Pythonista's ``Color`` requires four channels (RGBA).  To make the theme
    definition friendlier for customization, this helper accepts 3-tuples or
    four component values, automatically appending an alpha of ``1.0`` when it
    is omitted.
    """

    if len(components) == 1 and isinstance(components[0], (tuple, list)):
        components = tuple(components[0])
    else:
        components = tuple(components)

    if len(components) == 3:
        components = (*components, 1.0)

    if len(components) != 4:
        raise ValueError("Color expects 3 or 4 numeric components (r, g, b, a)")

    return Color(*components)


NEON_THEME = {
    "background": color_rgba(0.03, 0.0, 0.08, 1.0),
    "board_light": color_rgba(0.25, 0.0, 0.45, 1.0),
    "board_dark": color_rgba(0.0, 0.75, 0.65, 1.0),
    "outline": color_rgba(0.0, 0.9, 0.9, 1.0),
    "highlight": color_rgba(1.0, 0.2, 0.8, 0.45),
    "move_hint": color_rgba(0.95, 1.0, 0.3, 0.35),
    "white_piece": color_rgba(0.4, 1.0, 1.0, 1.0),
    "black_piece": color_rgba(1.0, 0.3, 0.8, 1.0),
    "text": color_rgba(0.8, 1.0, 1.0, 1.0),
}

FONT_NAME = "Futura"


class ButtonNode(Node):
    def __init__(self, title: str, action, *, font_size: float = 18.0) -> None:
        super().__init__()
        self.action = action
        padding = 12
        label = LabelNode(
            title,
            font=(FONT_NAME, font_size),
            color=NEON_THEME["text"],
            position=(0, 0),
        )
        background = ShapeNode(
            ui.Path.rounded_rect(0, 0, label.frame.w + padding, label.frame.h + padding, 8),
            fill_color=color_rgba(0.2, 0.0, 0.4, 0.85),
            stroke_color=NEON_THEME["outline"],
            position=(0, 0),
        )
        background.anchor_point = (0.5, 0.5)
        label.position = (0, 0)
        self.add_child(background)
        self.add_child(label)
        self.background = background
        self.label = label
        self.size = (background.frame.w, background.frame.h)

    def contains_point(self, point: Tuple[float, float]) -> bool:
        w, h = self.size
        return -w / 2 <= point[0] <= w / 2 and -h / 2 <= point[1] <= h / 2

    def trigger(self) -> None:
        if callable(self.action):
            self.run_action(Action.sequence(Action.scale_to(0.95, 0.05), Action.scale_to(1.0, 0.05)))
            self.action()


class ChessScene(Scene):
    def setup(self) -> None:
        self.background_color = NEON_THEME["background"]
        self.board = Board()
        self.board_node = Node(position=(self.size.w / 2, self.size.h / 2))
        self.add_child(self.board_node)
        self.square_size = min(self.size.w, self.size.h) * 0.85 / 8
        self.square_nodes: Dict[int, ShapeNode] = {}
        self.piece_nodes: Dict[int, LabelNode] = {}
        self.highlight_nodes: List[ShapeNode] = []
        self.move_hint_nodes: List[ShapeNode] = []
        self.selected_square: Optional[int] = None
        self.last_move: Optional[Move] = None

        self.status_label = LabelNode(
            "Neon Chess",
            position=(self.size.w / 2, self.size.h - 40),
            font=(FONT_NAME, 24),
            color=NEON_THEME["text"],
        )
        self.add_child(self.status_label)

        self.new_game_button = ButtonNode("New Game", self.reset_game)
        self.new_game_button.position = (self.size.w - 80, 50)
        self.add_child(self.new_game_button)

        self._create_board()
        self._sync_pieces()

    # ------------------------------------------------------------------
    def reset_game(self) -> None:
        self.board = Board()
        self.selected_square = None
        self.last_move = None
        self._sync_pieces(animated=False)
        self.update_status("Neon Chess - White to move")

    def update_status(self, text: str) -> None:
        self.status_label.text = text

    def _create_board(self) -> None:
        board_outline = ShapeNode(
            ui.Path.rounded_rect(
                -self.square_size * 4,
                -self.square_size * 4,
                self.square_size * 8,
                self.square_size * 8,
                12,
            ),
            stroke_color=NEON_THEME["outline"],
            fill_color=Color(0.05, 0.0, 0.15, 1.0),
            line_width=4,
        )
        board_outline.anchor_point = (0, 0)
        self.board_node.add_child(board_outline)

        for index in range(64):
            file = index % 8
            rank = index // 8
            color = NEON_THEME["board_light"] if (file + rank) % 2 == 0 else NEON_THEME["board_dark"]
            square_node = ShapeNode(
                ui.Path.rect(0, 0, self.square_size, self.square_size),
                fill_color=color,
                stroke_color=NEON_THEME["outline"],
                line_width=0.5,
            )
            square_node.anchor_point = (0, 0)
            square_node.position = (
                (file - 4) * self.square_size,
                (rank - 4) * self.square_size,
            )
            self.board_node.add_child(square_node)
            self.square_nodes[index] = square_node

    def _sync_pieces(self, *, animated: bool = True) -> None:
        # remove outdated nodes
        for index in list(self.piece_nodes.keys()):
            if not self.board.piece_at(index):
                node = self.piece_nodes.pop(index)
                node.remove_from_parent()

        for index, piece in enumerate(self.board.pieces):
            position = self._square_center(index)
            if not piece:
                continue
            node = self.piece_nodes.get(index)
            text = UNICODE_PIECES[(piece.color, piece.kind)]
            color = NEON_THEME["white_piece"] if piece.color == "w" else NEON_THEME["black_piece"]
            if node is None:
                node = LabelNode(
                    text,
                    font=(FONT_NAME, int(self.square_size * 0.8)),
                    color=color,
                    position=position,
                )
                node.z_position = 5
                self.board_node.add_child(node)
                self.piece_nodes[index] = node
            else:
                node.color = color
                node.text = text
                if animated:
                    node.run_action(Action.move_to(position[0], position[1], 0.1))
                else:
                    node.position = position

        self._update_highlights()
        self._update_move_hints()

        result = self.board.result()
        if result:
            if result in ("1-0", "0-1"):
                winner = "White" if result == "1-0" else "Black"
                self.update_status(f"{winner} wins by checkmate")
            else:
                self.update_status("Drawn game")
        else:
            side = "White" if self.board.to_move == "w" else "Black"
            self.update_status(f"{side} to move")

    def _update_highlights(self) -> None:
        for node in self.highlight_nodes:
            node.remove_from_parent()
        self.highlight_nodes.clear()

        if self.last_move:
            for sq in (self.last_move.from_sq, self.last_move.to_sq):
                highlight = self._make_highlight_node(sq, NEON_THEME["highlight"])
                self.board_node.add_child(highlight)
                self.highlight_nodes.append(highlight)

        if self.selected_square is not None:
            highlight = self._make_highlight_node(self.selected_square, NEON_THEME["highlight"])
            self.board_node.add_child(highlight)
            self.highlight_nodes.append(highlight)

    def _update_move_hints(self, moves: Optional[Iterable[Move]] = None) -> None:
        for node in self.move_hint_nodes:
            node.remove_from_parent()
        self.move_hint_nodes.clear()

        if moves is None and self.selected_square is not None:
            moves = [
                m for m in self.board.generate_legal_moves()
                if m.from_sq == self.selected_square
            ]
        if moves:
            unique_by_target: Dict[int, Move] = {}
            for move in moves:
                unique_by_target.setdefault(move.to_sq, move)
            moves = unique_by_target.values()
        if not moves:
            return
        for move in moves:
            dot = self._make_highlight_node(move.to_sq, NEON_THEME["move_hint"], radius=0.25)
            self.board_node.add_child(dot)
            self.move_hint_nodes.append(dot)

    def _make_highlight_node(self, square_index: int, color: Color, radius: float = 1.0) -> ShapeNode:
        size = self.square_size * radius
        path = ui.Path.oval(0, 0, size, size)
        node = ShapeNode(
            path,
            fill_color=color,
            stroke_color=color_rgba(0, 0, 0, 0),
        )
        node.position = (
            self._square_center(square_index)[0] - size / 2,
            self._square_center(square_index)[1] - size / 2,
        )
        node.z_position = 3
        node.anchor_point = (0, 0)
        return node

    def _square_center(self, index: int) -> Tuple[float, float]:
        file = index % 8
        rank = index // 8
        return (
            (file - 3.5) * self.square_size,
            (rank - 3.5) * self.square_size,
        )

    # ------------------------------------------------------------------
    def touch_ended(self, touch) -> None:
        location = touch.location
        local_point = self.board_node.point_from_scene(location)
        square_index = self._point_to_square(local_point)

        # new game button
        button_point = self.new_game_button.point_from_scene(location)
        if self.new_game_button.contains_point(button_point):
            self.new_game_button.trigger()
            return

        if square_index is None:
            self.selected_square = None
            self._update_highlights()
            self._update_move_hints([])
            return

        piece = self.board.piece_at(square_index)
        if self.selected_square is None:
            if piece and piece.color == self.board.to_move:
                self.selected_square = square_index
                self._update_highlights()
                self._update_move_hints()
        else:
            attempted = [m for m in self.board.generate_legal_moves() if m.from_sq == self.selected_square and m.to_sq == square_index]
            if len(attempted) == 1:
                move = attempted[0]
            else:
                move = next((m for m in attempted if m.promotion == "Q"), attempted[0]) if attempted else None
            if move:
                self.board.apply_move(move)
                self.last_move = move
                self.selected_square = None
                self._sync_pieces()
            elif piece and piece.color == self.board.to_move:
                self.selected_square = square_index
                self._update_highlights()
                self._update_move_hints()
            else:
                self.selected_square = None
                self._update_highlights()
                self._update_move_hints([])

    def _point_to_square(self, point: Tuple[float, float]) -> Optional[int]:
        size = self.square_size * 8
        if not (-size / 2 <= point[0] <= size / 2 and -size / 2 <= point[1] <= size / 2):
            return None
        file = int((point[0] + size / 2) // self.square_size)
        rank = int((point[1] + size / 2) // self.square_size)
        if 0 <= file < 8 and 0 <= rank < 8:
            return square(file, rank)
        return None


if __name__ == "__main__":
    scene_view = ChessScene()
    scene_view.name = "Neon Chess"
    run(scene_view, show_fps=False)
