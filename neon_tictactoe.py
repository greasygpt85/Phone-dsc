"""Simple neon-themed Tic-Tac-Toe game.

Run the script to play a local two-player Tic-Tac-Toe game in the
terminal.  Use the ``--color`` flag to pick a custom neon glow colour for
all of the board decorations and marks.  Colours are accepted as
``#RRGGBB`` hex strings or comma-separated RGB values (``0-255``).
"""
from __future__ import annotations

import argparse
import itertools
import sys
import re
from typing import Iterable, Tuple

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


class NeonStyler:
    """Apply a neon-like glow to text using ANSI escape sequences."""

    def __init__(self, rgb: Tuple[int, int, int]) -> None:
        self.rgb = rgb
        self.outer_glow = tuple(max(min(c + 35, 255), 0) for c in rgb)
        self._ansi_pattern = re.compile(r"\033\[[0-9;]*m")

    def colorize(self, text: str, *, bold: bool = True) -> str:
        """Wrap ``text`` with ANSI codes that tint it with the neon colour."""

        fg = f"\033[38;2;{self.rgb[0]};{self.rgb[1]};{self.rgb[2]}m"
        bg = (
            f"\033[48;2;{self.outer_glow[0]};{self.outer_glow[1]};{self.outer_glow[2]}m"
        )
        weight = BOLD if bold else DIM
        return f"{bg}{fg}{weight}{text}{RESET}"

    def _strip_ansi(self, text: str) -> str:
        return self._ansi_pattern.sub("", text)

    def panel(self, lines: Iterable[str]) -> str:
        """Create a neon-bordered panel around ``lines``."""

        content = list(lines)
        width = max(len(self._strip_ansi(line)) for line in content)
        border = self.colorize("╔" + "═" * (width + 2) + "╗")
        inner = []
        for line in content:
            plain_length = len(self._strip_ansi(line))
            padding = ""
            if plain_length < width:
                padding = self.colorize(" " * (width - plain_length), bold=False)
            inner.append(
                self.colorize("║", bold=False)
                + " "
                + line
                + padding
                + " "
                + self.colorize("║", bold=False)
            )
        bottom = self.colorize("╚" + "═" * (width + 2) + "╝")
        return "\n".join([border, *inner, bottom])


def parse_color(value: str) -> Tuple[int, int, int]:
    """Parse a colour string into an RGB tuple."""

    value = value.strip()
    if value.startswith("#"):
        value = value[1:]
        if len(value) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in value):
            raise argparse.ArgumentTypeError("Hex colours must be in #RRGGBB format")
        return tuple(int(value[i : i + 2], 16) for i in range(0, 6, 2))

    parts = value.replace(" ", "").split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "RGB colours must contain three comma-separated numbers"
        )
    try:
        rgb = tuple(int(part) for part in parts)
    except ValueError as exc:  # pragma: no cover - defensive parsing
        raise argparse.ArgumentTypeError("RGB components must be integers") from exc

    if not all(0 <= component <= 255 for component in rgb):
        raise argparse.ArgumentTypeError("RGB components must be between 0 and 255")

    return rgb  # type: ignore[return-value]


def display_board(board: Tuple[str, ...], styler: NeonStyler) -> None:
    """Render the game board."""

    def render_cell(index: int, value: str) -> str:
        if value == " ":
            return styler.colorize(str(index + 1).center(3), bold=False)
        return styler.colorize(value.center(3))

    cells = [render_cell(idx, cell) for idx, cell in enumerate(board)]
    rows = [" │ ".join(cells[i : i + 3]) for i in range(0, 9, 3)]
    separator = styler.colorize("───┼───┼───", bold=False)
    print(styler.panel([rows[0], separator, rows[1], separator, rows[2]]))


def check_winner(board: Tuple[str, ...]) -> str | None:
    """Return the symbol of the winning player, or ``None`` if there isn't one."""

    wins = [
        (0, 1, 2),
        (3, 4, 5),
        (6, 7, 8),
        (0, 3, 6),
        (1, 4, 7),
        (2, 5, 8),
        (0, 4, 8),
        (2, 4, 6),
    ]
    for a, b, c in wins:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    return None


def get_move(player: str, board: Tuple[str, ...]) -> int:
    """Prompt the current player for a move."""

    while True:
        try:
            choice = input(f"Player {player}, choose an empty square (1-9): ").strip()
        except EOFError:  # pragma: no cover - interactive guard
            print("\nThanks for playing!")
            sys.exit(0)
        if not choice.isdigit():
            print("Please enter the number of an empty square.")
            continue
        position = int(choice) - 1
        if position not in range(9):
            print("Numbers must be between 1 and 9.")
            continue
        if board[position] != " ":
            print("That square is already taken. Try another one.")
            continue
        return position


def play_game(styler: NeonStyler) -> None:
    """Run a full game loop until the players choose to stop."""

    print(styler.panel(["Welcome to Neon Tic-Tac-Toe!"]))

    while True:
        board = tuple(" " for _ in range(9))
        current_board = list(board)
        players = itertools.cycle(["X", "O"])
        for turn in range(9):
            player = next(players)
            display_board(tuple(current_board), styler)
            move = get_move(player, tuple(current_board))
            current_board[move] = player
            winner = check_winner(tuple(current_board))
            if winner:
                display_board(tuple(current_board), styler)
                print(styler.panel([f"Player {winner} wins!"]))
                break
        else:
            display_board(tuple(current_board), styler)
            print(styler.panel(["It's a draw!"]))

        again = input("Play again? (y/n): ").strip().lower()
        if again not in {"y", "yes"}:
            print(styler.panel(["Thanks for playing!"]))
            return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Play a neon-themed Tic-Tac-Toe game")
    parser.add_argument(
        "--color",
        default="#39ff14",
        type=parse_color,
        help=(
            "Neon glow colour in #RRGGBB or R,G,B form (default: classic neon green)."
        ),
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    styler = NeonStyler(args.color)
    play_game(styler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
