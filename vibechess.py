from __future__ import annotations
import math
import random
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

try:
    from scene import (
        Action,
        Color,
        LabelNode,
        Node,
        Scene,
        ShapeNode,
        TIMING_EASE_IN,
        TIMING_EASE_OUT,
        PORTRAIT,
        run,
    )
    import sound
    import ui
except Exception as exc:
    raise SystemExit("Run this in Pythonista 3 on iOS.") from exc

FILES = "abcdefgh"
RANKS = "12345678"

# Unicode piece glyphs (works on iOS)
GLYPHS = {
    "K": "♔",
    "Q": "♕",
    "R": "♖",
    "B": "♗",
    "N": "♘",
    "P": "♙",
    "k": "♚",
    "q": "♛",
    "r": "♜",
    "b": "♝",
    "n": "♞",
    "p": "♟",
}

# Starting position (FEN rows)
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"

# A small set of neon themes; double-tap to randomize
THEMES = [
    dict(
        bg=(0.02, 0.02, 0.06),
        a=(0.08, 0.18, 0.25),
        b=(0.02, 0.06, 0.12),
        hi=(1.00, 0.40, 0.85),
        lo=(0.50, 0.90, 1.00),
    ),
    dict(
        bg=(0.02, 0.03, 0.02),
        a=(0.09, 0.20, 0.09),
        b=(0.04, 0.10, 0.04),
        hi=(1.00, 0.85, 0.35),
        lo=(0.35, 1.00, 0.60),
    ),
    dict(
        bg=(0.03, 0.02, 0.02),
        a=(0.20, 0.09, 0.09),
        b=(0.10, 0.04, 0.04),
        hi=(1.00, 0.55, 0.55),
        lo=(0.85, 0.85, 1.00),
    ),
    dict(
        bg=(0.02, 0.02, 0.06),
        a=(0.10, 0.04, 0.18),
        b=(0.05, 0.02, 0.10),
        hi=(0.80, 0.70, 1.00),
        lo=(0.40, 1.00, 0.90),
    ),
]


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp3(c1, c2, t):
    return tuple(lerp(c1[i], c2[i], t) for i in range(3))


def color_tuple(rgb, a=1.0):
    return Color(*rgb, a)


@dataclass
class Piece:
    kind: str  # 'P', 'k', etc (uppercase = white, lowercase = black)
    node: LabelNode
    glow: LabelNode


class VibeChess(Scene):
    def setup(self):
        self.grid = 8
        self.margin = 20
        self.side_to_move = "white"
        self.drag_piece: Optional[Piece] = None
        self.drag_start_sq: Optional[Tuple[int, int]] = None
        self.squares: Dict[Tuple[int, int], ShapeNode] = {}
        self.board: Dict[Tuple[int, int], Piece] = {}
        self.theme = random.choice(THEMES)
        self.t0 = time.time()

        # Board geometry
        self.board_size = min(self.size.w, self.size.h) - 2 * self.margin
        self.square = self.board_size / self.grid
        self.board_origin = (
            self.size.w / 2 - self.board_size / 2,
            self.size.h / 2 - self.board_size / 2,
        )

        # Background
        self.bg = Node()
        self.add_child(self.bg)
        self.bg_rect = ShapeNode(
            ui.Path.rounded_rect(
                0, 0, self.size.w * 1.2, self.size.h * 1.2, 30
            ),
            fill_color=color_tuple(self.theme["bg"], 1.0),
            stroke_color=Color.clear(),
        )
        self.bg_rect.position = self.size / 2
        self.bg.add_child(self.bg_rect)

        # Title / turn label
        self.title = LabelNode(
            "VibeChess",
            font=("Avenir-Heavy", 20),
            position=(
                self.size.w / 2,
                self.board_origin[1] + self.board_size + 28,
            ),
            color=color_tuple(self.theme["lo"]),
        )
        self.add_child(self.title)
        self.turn_label = LabelNode(
            "White to move",
            font=("AvenirNext-Medium", 16),
            position=(self.size.w / 2, self.title.position.y - 20),
            color=color_tuple(self.theme["hi"]),
        )
        self.add_child(self.turn_label)

        # Build board squares
        self.board_layer = Node()
        self.add_child(self.board_layer)
        for r in range(8):
            for f in range(8):
                x, y = self.square_center((f, r))
                shade = self.theme["a"] if (f + r) % 2 == 0 else self.theme["b"]
                sq = ShapeNode(
                    ui.Path.rounded_rect(
                        0, 0, self.square * 0.98, self.square * 0.98, self.square * 0.08
                    ),
                    fill_color=color_tuple(shade, 1.0),
                    stroke_color=color_tuple(lerp3(shade, (1, 1, 1), 0.12), 0.25),
                    position=(x, y),
                )
                sq.shadow = (0, 0, self.square * 0.08, Color(0, 0, 0, 0.35))
                self.board_layer.add_child(sq)
                self.squares[(f, r)] = sq

        # Glow pulse overlay
        self.pulse_layer = Node()
        self.add_child(self.pulse_layer)

        # Pieces
        self.piece_layer = Node()
        self.add_child(self.piece_layer)
        self.load_fen(START_FEN)
        self.pulse_timer = 0.0

    # ---------- Board helpers ----------
    def square_center(self, sq: Tuple[int, int]) -> Tuple[float, float]:
        f, r = sq
        ox, oy = self.board_origin
        return (ox + (f + 0.5) * self.square, oy + (r + 0.5) * self.square)

    def point_to_square(self, p) -> Optional[Tuple[int, int]]:
        ox, oy = self.board_origin
        f = int((p.x - ox) // self.square)
        r = int((p.y - oy) // self.square)
        if 0 <= f < 8 and 0 <= r < 8:
            return (f, r)
        return None

    def square_contains_piece(self, sq) -> Optional[Piece]:
        return self.board.get(sq)

    def add_sparkles(self, pos, count=12):
        for _ in range(count):
            rad = random.uniform(2, 4)
            path = ui.Path.oval(0, 0, rad, rad)
            dot = ShapeNode(
                path,
                fill_color=color_tuple(self.theme["lo"]),
                stroke_color=Color.clear(),
                position=pos,
            )
            self.add_child(dot)
            ang = random.random() * 2 * math.pi
            dist = random.uniform(self.square * 0.15, self.square * 0.45)
            dx, dy = math.cos(ang) * dist, math.sin(ang) * dist
            seq = Action.sequence(
                Action.group(
                    Action.move_by(dx, dy, 0.25, TIMING_EASE_OUT),
                    Action.fade_to(0.0, 0.25),
                ),
                Action.remove(),
            )
            dot.run_action(seq)

    # ---------- Theme / Text ----------
    def set_turn_text(self):
        self.turn_label.text = (
            "White to move" if self.side_to_move == "white" else "Black to move"
        )

    def randomize_theme(self):
        self.theme = random.choice(THEMES)
        self.bg_rect.fill_color = color_tuple(self.theme["bg"], 1.0)
        for (f, r), sq in self.squares.items():
            shade = self.theme["a"] if (f + r) % 2 == 0 else self.theme["b"]
            sq.fill_color = color_tuple(shade, 1.0)
            sq.stroke_color = color_tuple(lerp3(shade, (1, 1, 1), 0.12), 0.25)
        for piece in self.board.values():
            self.apply_piece_colors(piece)

    # ---------- Pieces ----------
    def make_piece(self, kind: str, sq: Tuple[int, int]) -> Piece:
        is_white = kind.isupper()
        base_color = self.theme["lo"] if is_white else self.theme["hi"]

        glow = LabelNode(GLYPHS[kind], font=("AvenirNext-Heavy", int(self.square * 0.9)))
        glow.color = color_tuple(base_color, 0.25)
        glow.scale = 1.1

        node = LabelNode(GLYPHS[kind], font=("AvenirNext-Heavy", int(self.square * 0.9)))
        node.color = color_tuple(base_color, 1.0)

        g = Node()
        g.add_child(glow)
        g.add_child(node)
        g.position = self.square_center(sq)
        g.name = "piece"

        self.piece_layer.add_child(g)
        self.apply_glow_shadow(g)

        return Piece(kind=kind, node=node, glow=glow)

    def apply_glow_shadow(self, container: Node):
        # Soft outer glow using label's shadow (fake bloom)
        for ch in container.children:
            if isinstance(ch, LabelNode):
                ch.shadow = (0, 0, self.square * 0.18, Color(0, 0, 0, 0.6))

    def apply_piece_colors(self, piece: Piece):
        is_white = piece.kind.isupper()
        base_color = self.theme["lo"] if is_white else self.theme["hi"]
        piece.node.color = color_tuple(base_color, 1.0)
        piece.glow.color = color_tuple(base_color, 0.25)

    def load_fen(self, fen: str):
        # Clear current pieces
        for n in list(self.piece_layer.children):
            n.remove_from_parent()
        self.board.clear()

        rows = fen.split("/")[0:8]
        for r, row in enumerate(reversed(rows)):  # FEN top row is rank 8
            file_idx = 0
            for ch in row:
                if ch.isdigit():
                    file_idx += int(ch)
                else:
                    sq = (file_idx, r)
                    p = self.make_piece(ch, sq)
                    self.board[sq] = p
                    file_idx += 1

        self.side_to_move = "white"
        self.set_turn_text()

    def piece_container_for(self, p: Piece) -> Node:
        # Piece nodes are inside a 2-label container; return that parent
        return p.node.parent

    # ---------- Touch handling (drag / drop with snap & capture) ----------
    def touch_began(self, touch):
        # Double-tap: randomize theme
        if touch.tap_count == 2:
            self.randomize_theme()
            try:
                sound.play_effect("ui:click1")
            except Exception:
                pass
            return
        # Two-finger tap: reset
        if len(self.touches) >= 2 and touch.tap_count == 1:
            self.load_fen(START_FEN)
            try:
                sound.play_effect("ui:switch18")
            except Exception:
                pass
            return

        sq = self.point_to_square(touch.location)
        if not sq:
            return
        piece = self.square_contains_piece(sq)
        if not piece:
            return

        is_white = piece.kind.isupper()
        if (self.side_to_move == "white" and not is_white) or (
            self.side_to_move == "black" and is_white
        ):
            # Not your turn; little bounce
            container = self.piece_container_for(piece)
            container.run_action(
                Action.sequence(
                    Action.scale_to(1.08, 0.06),
                    Action.scale_to(1.0, 0.06),
                )
            )
            try:
                sound.play_effect("ui:click3")
            except Exception:
                pass
            return

        self.drag_piece = piece
        self.drag_start_sq = sq
        container = self.piece_container_for(piece)
        container.z_position = 50
        container.run_action(Action.scale_to(1.08, 0.08))

    def touch_moved(self, touch):
        if not self.drag_piece:
            return
        container = self.piece_container_for(self.drag_piece)
        container.position = touch.location

    def touch_ended(self, touch):
        if not self.drag_piece:
            return
        piece = self.drag_piece
        start_sq = self.drag_start_sq
        container = self.piece_container_for(piece)

        target_sq = self.point_to_square(touch.location)
        valid = target_sq is not None
        if valid:
            occupant = self.board.get(target_sq)
            # Allow any move inside board; if same-color occupant, reject.
            if occupant and (occupant.kind.isupper() == piece.kind.isupper()):
                valid = False

        if not valid:
            # Snap back
            container.run_action(
                Action.sequence(
                    Action.move_to(
                        *self.square_center(start_sq),
                        0.12,
                        TIMING_EASE_OUT,
                    ),
                    Action.scale_to(1.0, 0.06),
                )
            )
            try:
                sound.play_effect("ui:click2")
            except Exception:
                pass
        else:
            # Capture if present
            if target_sq in self.board:
                occ = self.board[target_sq]
                self.piece_container_for(occ).run_action(
                    Action.sequence(
                        Action.group(
                            Action.scale_to(0.01, 0.18, TIMING_EASE_IN),
                            Action.fade_to(0.0, 0.18),
                        ),
                        Action.remove(),
                    )
                )
                try:
                    sound.play_effect("arcade:Explosion_1")
                except Exception:
                    pass
            # Update board
            if start_sq in self.board:
                del self.board[start_sq]
            self.board[target_sq] = piece
            # Snap into place with sparkle
            end_pos = self.square_center(target_sq)
            container.run_action(
                Action.sequence(
                    Action.move_to(*end_pos, 0.10, TIMING_EASE_OUT),
                    Action.scale_to(1.0, 0.06),
                )
            )
            self.add_sparkles(end_pos, 10)
            try:
                sound.play_effect("ui:click1")
            except Exception:
                pass
            # Swap turn
            self.side_to_move = (
                "black" if self.side_to_move == "white" else "white"
            )
            self.set_turn_text()

        container.z_position = 10
        self.drag_piece = None
        self.drag_start_sq = None

    # ---------- Update loop: subtle board pulse ----------
    def update(self):
        t = (time.time() - self.t0) * 0.35
        pulse = (math.sin(t) * 0.5 + 0.5) * 0.22  # 0..~0.22
        for (f, r), sq in self.squares.items():
            base = self.theme["a"] if (f + r) % 2 == 0 else self.theme["b"]
            bright = lerp3(base, (1.0, 1.0, 1.0), pulse * 0.08)
            sq.fill_color = color_tuple(bright, 1.0)

        # Soft title glow pulse
        a = 0.5 + 0.5 * math.sin(t * 2.0)
        self.title.color = color_tuple(self.theme["lo"], 0.65 + 0.35 * a)
        self.turn_label.color = color_tuple(
            self.theme["hi"], 0.65 + 0.35 * (1 - a)
        )


if __name__ == "__main__":
    run(VibeChess(), PORTRAIT, show_fps=False)
