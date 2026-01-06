"""Neon chessboard renderer for Pythonista.

This script uses Pythonista's built-in ``scene`` framework to draw a neon
styled chessboard. Colours can be customised either by editing the
``NeonChessboardConfig`` values directly or by instantiating the
``NeonChessboardScene`` with your preferred colour choices.

Usage inside Pythonista::

    from neon_chessboard import NeonChessboardConfig, NeonChessboardScene, run

    custom = NeonChessboardConfig(
        light_color="#00ffc8",
        dark_color="#8a2be2",
        glow_color="#ffffff",
        background_color="#05010a",
    )
    run(NeonChessboardScene, config=custom)

Alternatively, just run this script directly to view the default chessboard.

The script focuses on clarity and avoids Pythonista-specific global state, so
you can import and reuse the scene in other projects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple, Union

try:
    import ui
    from scene import Color, LabelNode, Node, Scene, ShapeNode, run as scene_run
except ImportError as exc:  # pragma: no cover - Pythonista specific import
    raise RuntimeError(
        "This module requires Pythonista's 'scene' and 'ui' modules."
    ) from exc


ColorInput = Union[
    str,
    Tuple[float, float, float],
    Tuple[float, float, float, float],
    Color,
]


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _hex_to_rgb(color: str) -> Tuple[float, float, float]:
    color = color.lstrip("#")
    if len(color) not in (3, 6):
        raise ValueError(f"Hex colours must be #RGB or #RRGGBB, got '{color}'.")

    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)

    r, g, b = (int(color[i : i + 2], 16) for i in (0, 2, 4))
    return r / 255.0, g / 255.0, b / 255.0


def _normalize_color(color: ColorInput) -> Color:
    """Convert strings or tuples into a Pythonista ``Color`` instance."""

    if isinstance(color, Color):  # type: ignore[unreachable]
        return color

    if isinstance(color, str):
        rgb = _hex_to_rgb(color)
        return Color(*rgb)

    if isinstance(color, Iterable):
        values = tuple(color)  # type: ignore[arg-type]
        if len(values) not in (3, 4):
            raise ValueError(
                "Colour tuples must contain 3 (RGB) or 4 (RGBA) floats in the "
                "range 0.0-1.0"
            )
        if len(values) == 3:
            r, g, b = values
            a = 1.0
        else:
            r, g, b, a = values
        return Color(_clamp(r), _clamp(g), _clamp(b), _clamp(a))

    raise TypeError("Unsupported colour format. Use hex strings or RGB(A) tuples.")


@dataclass(frozen=True)
class NeonChessboardConfig:
    board_size: int = 8
    square_size: int = 80
    light_color: ColorInput = "#21ffd4"
    dark_color: ColorInput = "#ff2fb5"
    background_color: ColorInput = "#030009"
    glow_color: ColorInput = "#6cf9ff"
    label_color: ColorInput = "#f8f8ff"
    glow_radius: float = 18.0
    neon_line_width: float = 4.5
    show_rank_file_labels: bool = True


class NeonChessboardScene(Scene):
    """Scene responsible for drawing the neon chessboard."""

    def __init__(self, config: NeonChessboardConfig | None = None) -> None:
        super().__init__()
        self.config = config or NeonChessboardConfig()
        self.board_root: Node | None = None

    def setup(self) -> None:
        self.background_color = _normalize_color(self.config.background_color)
        self._build_board()

    def did_change_size(self) -> None:
        self._build_board()

    # --- Construction helpers -------------------------------------------------
    def _build_board(self) -> None:
        if self.board_root is not None:
            self.board_root.remove_from_parent()

        cfg = self.config
        board_pixel = cfg.board_size * cfg.square_size
        offset_x = (self.size.w - board_pixel) / 2
        offset_y = (self.size.h - board_pixel) / 2

        root = Node()
        root.position = (0, 0)

        light = _normalize_color(cfg.light_color)
        dark = _normalize_color(cfg.dark_color)
        glow = _normalize_color(cfg.glow_color)

        label_color = _normalize_color(cfg.label_color)

        for rank in range(cfg.board_size):
            for file in range(cfg.board_size):
                color = light if (rank + file) % 2 == 0 else dark
                square_path = ui.Path.rect(0, 0, cfg.square_size, cfg.square_size)
                square = ShapeNode(
                    square_path,
                    position=(
                        offset_x + file * cfg.square_size + cfg.square_size / 2,
                        offset_y + rank * cfg.square_size + cfg.square_size / 2,
                    ),
                    fill_color=color,
                    stroke_color=glow,
                    line_width=cfg.neon_line_width,
                )
                try:
                    square.shadow = (glow, 0, 0, cfg.glow_radius)
                except Exception:
                    pass
                square.blend_mode = "add"
                root.add_child(square)

        if cfg.show_rank_file_labels:
            self._add_rank_file_labels(root, offset_x, offset_y, label_color)

        self.board_root = root
        self.add_child(root)

    def _add_rank_file_labels(
        self,
        root: Node,
        offset_x: float,
        offset_y: float,
        label_color: Color,
    ) -> None:
        cfg = self.config
        size = cfg.square_size
        for index in range(cfg.board_size):
            file_label = LabelNode(
                text=chr(ord("a") + index),
                position=(offset_x + index * size + size / 2, offset_y - size * 0.35),
                color=label_color,
                font=("AvenirNext-Heavy", size * 0.35),
            )
            rank_label = LabelNode(
                text=str(cfg.board_size - index),
                position=(offset_x - size * 0.35, offset_y + index * size + size / 2),
                color=label_color,
                font=("AvenirNext-Heavy", size * 0.35),
            )
            file_label.blend_mode = "add"
            rank_label.blend_mode = "add"
            root.add_child(file_label)
            root.add_child(rank_label)


def run(scene_cls: type[NeonChessboardScene] = NeonChessboardScene, *, config: NeonChessboardConfig | None = None) -> None:
    """Convenience helper mirroring ``scene.run`` with config injection."""

    if config is None:
        scene_run(scene_cls())
    else:
        scene_run(scene_cls(config=config))


if __name__ == "__main__":
    run()
