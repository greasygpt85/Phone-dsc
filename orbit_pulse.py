"""
Orbit Pulse — a touch-friendly, lane-switching arcade for Pythonista.

Copy/paste this file into Pythonista (or keep it in Files) and run it. The
prototype uses only the built-in `scene` module, so no extra installs are
needed.

How to play
===========
- You control a small runner that rides two concentric orbits.
- Tap anywhere to hop between the inner and outer lane.
- Double-tap when the surge meter is full to trigger "Pulse Surge" (slow-mo +
  shield refresh).
- Collect energy shards (cyan) to increase your score and streak multiplier.
- Grab pulse orbs (yellow) to charge the surge meter.
- Avoid void spikes (magenta). A shield can absorb one hit, otherwise you lose
  a heart. Lose all hearts and it's game over.
- Difficulty ramps up over time with higher rotation speed and tighter spawns.

Tips
====
- Staying alive with a long streak increases your multiplier automatically.
- Use Surge just before a dense wave of spikes to keep your streak alive.
- If you miss three shards in a row your streak decays—keep the rhythm.

The code is intentionally compact and self contained so you can hack on it in
Pythonista. Feel free to tweak COLORS, radii, and tuning constants.
"""
from __future__ import annotations

import math
import random
import time
from typing import Dict, List

from scene import Action, Color, LabelNode, Node, Path, Scene, ShapeNode, run


# Visual palette tuned for OLED devices.
COLORS = {
    "bg": Color(0.02, 0.01, 0.08),
    "lane": Color(0.28, 0.12, 0.45, 0.3),
    "lane_glow": Color(0.8, 0.35, 0.95, 0.3),
    "player": Color(0.35, 1.0, 0.95),
    "player_shadow": Color(0.0, 0.0, 0.0, 0.3),
    "shard": Color(0.25, 0.9, 1.0),
    "pulse": Color(1.0, 0.9, 0.35),
    "spike": Color(0.95, 0.2, 0.85),
    "text": Color(0.9, 0.92, 1.0),
}

LANES = [180, 240]
PLAYER_ANGLE = math.pi / 2  # lock player to the top of the circle


class OrbitPulse(Scene):
    def setup(self) -> None:
        random.seed()
        self.background_color = COLORS["bg"]
        self.anchor_point = (0.5, 0.5)
        self.player_lane = 0
        self.items: List[Dict] = []
        self.spawn_timer = 0.0
        self.base_spawn_delay = 1.2
        self.rotation_speed = 0.8
        self.time_alive = 0.0
        self.score = 0
        self.misses = 0
        self.streak = 0
        self.multiplier = 1
        self.shield = 1
        self.hearts = 3
        self.pulse_meter = 0
        self.game_over = False
        self.surge_active = False
        self.surge_time = 0.0

        self.root = Node(parent=self)
        self.ring_layer = Node(parent=self.root)
        self.item_layer = Node(parent=self.root)
        self.ui_layer = Node(parent=self.root)

        self._build_lanes()
        self._build_player()
        self._build_hud()

        self.last_spawn = time.time()
        self._update_hud()

    def _build_lanes(self) -> None:
        for radius in LANES:
            lane = ShapeNode(
                Path.oval(0, 0, radius * 2, radius * 2),
                stroke_color=COLORS["lane"],
                fill_color=Color(0, 0, 0, 0),
                position=(0, 0),
                parent=self.ring_layer,
            )
            lane.line_width = 6
            glow = ShapeNode(
                Path.oval(0, 0, (radius + 10) * 2, (radius + 10) * 2),
                stroke_color=COLORS["lane_glow"],
                fill_color=Color(0, 0, 0, 0),
                position=(0, 0),
                parent=self.ring_layer,
            )
            glow.line_width = 2
            glow.alpha = 0.6

    def _build_player(self) -> None:
        self.player = ShapeNode(
            Path.oval(0, 0, 40, 40),
            fill_color=COLORS["player"],
            stroke_color=Color(0, 0, 0, 0),
            parent=self.root,
        )
        shadow = ShapeNode(
            Path.oval(0, 0, 60, 60),
            fill_color=COLORS["player_shadow"],
            stroke_color=Color(0, 0, 0, 0),
            parent=self.root,
        )
        shadow.z_position = -1
        self.player_shadow = shadow
        self._update_player_position()

    def _build_hud(self) -> None:
        self.score_label = LabelNode("0", position=(-self.size.w / 2 + 20, self.size.h / 2 - 40),
                                    anchor_point=(0, 0.5), color=COLORS["text"], parent=self.ui_layer)
        self.meta_label = LabelNode("", position=(0, self.size.h / 2 - 40),
                                   anchor_point=(0.5, 0.5), color=COLORS["text"], parent=self.ui_layer)
        self.state_label = LabelNode("Tap to swap lanes", position=(0, -self.size.h / 2 + 40),
                                    anchor_point=(0.5, 0.5), color=COLORS["text"], parent=self.ui_layer)

    def _update_player_position(self) -> None:
        radius = LANES[self.player_lane]
        x = math.cos(PLAYER_ANGLE) * radius
        y = math.sin(PLAYER_ANGLE) * radius
        self.player.position = (x, y)
        self.player_shadow.position = (x, y - 10)

    def _update_hud(self) -> None:
        heart_text = "❤" * self.hearts
        shield_text = "⛨" if self.shield > 0 else ""
        surge_text = f"SURGE {self.pulse_meter}/5" if self.pulse_meter < 5 else "SURGE READY"
        if self.surge_active:
            surge_text = "SURGE ACTIVE"
        self.score_label.text = f"{self.score}  ×{self.multiplier}  {heart_text} {shield_text}"
        self.meta_label.text = surge_text

    def _spawn_item(self) -> None:
        lane = random.choice([0, 1])
        kind = random.choices(["shard", "spike", "pulse"], weights=[6, 3, 2])[0]
        radius = LANES[lane]
        angle = math.pi * 2 + random.random() * 0.8  # spawn above the player
        node = self._make_item_node(kind)
        node.position = (math.cos(angle) * radius, math.sin(angle) * radius)
        node.z_position = 1
        node.parent = self.item_layer
        self.items.append({"node": node, "angle": angle, "radius": radius, "kind": kind, "lane": lane})

    def _make_item_node(self, kind: str) -> ShapeNode:
        if kind == "spike":
            path = Path()
            path.move_to(0, 0)
            path.line_to(24, 54)
            path.line_to(-24, 54)
            path.close()
            return ShapeNode(path, fill_color=COLORS["spike"], stroke_color=Color(0, 0, 0, 0))
        radius = 26 if kind == "pulse" else 20
        color = COLORS["pulse"] if kind == "pulse" else COLORS["shard"]
        return ShapeNode(Path.oval(0, 0, radius, radius), fill_color=color, stroke_color=Color(0, 0, 0, 0))

    def _decay_streak(self) -> None:
        if self.streak > 0:
            self.streak = max(0, self.streak - 1)
            self.multiplier = 1 + self.streak // 4

    def _hit_shard(self) -> None:
        self.score += 1 * self.multiplier
        self.streak += 1
        self.misses = 0
        if self.streak % 4 == 0:
            self.multiplier += 1
        self._flash_player()

    def _hit_pulse(self) -> None:
        self.pulse_meter = min(5, self.pulse_meter + 1)
        self.score += 2 * self.multiplier
        self._flash_player(stronger=True)

    def _hit_spike(self) -> None:
        if self.shield > 0:
            self.shield -= 1
        else:
            self.hearts -= 1
        self.streak = 0
        self.multiplier = 1
        if self.hearts <= 0:
            self._trigger_game_over()
        else:
            self._shake_scene()

    def _flash_player(self, stronger: bool = False) -> None:
        factor = 1.2 if stronger else 1.05
        self.player.run_action(Action.sequence(Action.scale_by(factor, 0.08), Action.scale_to(1.0, 0.12)))

    def _shake_scene(self) -> None:
        self.root.run_action(
            Action.sequence(
                Action.move_by(8, 0, 0.04),
                Action.move_by(-16, 0, 0.08),
                Action.move_by(8, 0, 0.04),
                Action.move_to(0, 0, 0.05),
            )
        )

    def _trigger_game_over(self) -> None:
        self.game_over = True
        self.state_label.text = "Game Over — tap to restart"

    def _trigger_surge(self) -> None:
        if self.pulse_meter < 5 or self.surge_active or self.game_over:
            return
        self.surge_active = True
        self.surge_time = 2.4
        self.pulse_meter = 0
        self.shield = 1
        self.rotation_speed *= 0.55
        self.state_label.text = "SURGE!" \
            "+ slow-mo + shield refreshed"

    def update(self) -> None:
        if self.game_over:
            return

        dt = min(self.dt, 1 / 30)
        self.time_alive += dt

        # Adaptive difficulty.
        self.rotation_speed = min(2.2, 0.8 + self.time_alive * 0.05)
        self.base_spawn_delay = max(0.4, 1.2 - self.time_alive * 0.04)

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self._spawn_item()
            self.spawn_timer = self.base_spawn_delay * (0.5 + random.random() * 0.8)

        self._update_items(dt)
        self._update_hud()

        if self.surge_active:
            self.surge_time -= dt
            if self.surge_time <= 0:
                self.surge_active = False
                self.rotation_speed = min(1.2 + self.time_alive * 0.05, 2.2)
                self.state_label.text = "Tap to swap lanes"

    def _update_items(self, dt: float) -> None:
        player_radius = LANES[self.player_lane]
        speed = self.rotation_speed * (0.35 if self.surge_active else 1.0)
        for item in list(self.items):
            item["angle"] -= speed * dt
            angle = item["angle"]
            radius = item["radius"]
            node = item["node"]
            node.position = (math.cos(angle) * radius, math.sin(angle) * radius)

            # Remove when far past player.
            if angle < -math.pi / 2:
                self.items.remove(item)
                if item["kind"] == "shard":
                    self.misses += 1
                    if self.misses >= 3:
                        self._decay_streak()
                        self.misses = 0
                continue

            # Collision window.
            if abs(angle - PLAYER_ANGLE) < 0.2 and radius == player_radius:
                self.items.remove(item)
                kind = item["kind"]
                if kind == "shard":
                    self._hit_shard()
                elif kind == "pulse":
                    self._hit_pulse()
                else:
                    self._hit_spike()

    def touches_ended(self, touches) -> None:
        touch = list(touches.values())[0]
        if self.game_over:
            self._reset_game()
            return
        if touch.tap_count >= 2:
            self._trigger_surge()
        else:
            self.player_lane = 1 - self.player_lane
            self._update_player_position()
            self.state_label.text = "Lane switched"

    def _reset_game(self) -> None:
        self.items.clear()
        self.score = 0
        self.misses = 0
        self.streak = 0
        self.multiplier = 1
        self.shield = 1
        self.hearts = 3
        self.pulse_meter = 0
        self.player_lane = 0
        self.time_alive = 0.0
        self.rotation_speed = 0.8
        self.base_spawn_delay = 1.2
        self.surge_active = False
        self.surge_time = 0.0
        self.game_over = False
        self.state_label.text = "Tap to swap lanes"
        self._update_player_position()
        self._update_hud()


if __name__ == "__main__":
    run(OrbitPulse(), show_fps=True)
