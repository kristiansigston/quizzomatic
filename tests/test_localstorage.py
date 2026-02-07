import socket
import subprocess
import sys
import time
from contextlib import closing

from playwright.sync_api import expect, sync_playwright


def _port_open(host, port):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def _wait_for_port(host, port, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if _port_open(host, port):
            return True
        time.sleep(0.1)
    return False


def test_username_saved_and_restored_from_localstorage():
    host = "127.0.0.1"
    port = 9145
    started_server = False
    server_proc = None

    if not _port_open(host, port):
        server_proc = subprocess.Popen([sys.executable, "app.py"])
        started_server = True
        assert _wait_for_port(host, port), "Server did not start on port 9145"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://{host}:{port}", wait_until="domcontentloaded")

            page.fill("#username-input", "Alice")
            page.click("#btn-confirm-join")

            stored = page.evaluate("() => localStorage.getItem('triviaUsername')")
            assert stored == "Alice"

            page.reload(wait_until="domcontentloaded")
            value = page.input_value("#username-input")
            assert value == "Alice"

            browser.close()
    finally:
        if started_server and server_proc:
            server_proc.terminate()
            server_proc.wait(timeout=5)


def test_player_timer_stops_after_answer():
    host = "127.0.0.1"
    port = 9145
    started_server = False
    server_proc = None

    if not _port_open(host, port):
        server_proc = subprocess.Popen([sys.executable, "app.py"])
        started_server = True
        assert _wait_for_port(host, port), "Server did not start on port 9145"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            host_page = browser.new_page()
            player_page = browser.new_page()

            host_page.goto(f"http://{host}:{port}", wait_until="domcontentloaded")
            player_page.goto(f"http://{host}:{port}", wait_until="domcontentloaded")

            player_page.fill("#username-input", "Player1")
            player_page.click("#btn-confirm-join")
            expect(player_page.locator("#player-view")).to_be_visible()

            host_page.click("#btn-start")

            player_page.wait_for_selector(".answer-btn")
            expect(player_page.locator("#player-timer")).to_be_visible()

            player_page.locator(".answer-btn").first.click()
            expect(player_page.locator("#player-timer")).to_be_hidden()

            browser.close()
    finally:
        if started_server and server_proc:
            server_proc.terminate()
            server_proc.wait(timeout=5)
