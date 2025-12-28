"""
Pythonista-friendly launcher for the Solar System Gravity Well Sandbox.

Run this inside Pythonista to open a fullscreen WebView with the sandbox.
The script reads index.html from the same directory, so keep the files together.
"""

import os
import ui


def main():
    here = os.path.abspath(os.path.dirname(__file__))
    html_path = os.path.join(here, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    view = ui.WebView()
    view.load_html(html)
    view.flex = "WH"
    view.scales_page_to_fit = True
    view.present(style="fullscreen", orientations=["portrait", "landscape"])


if __name__ == "__main__":
    main()
