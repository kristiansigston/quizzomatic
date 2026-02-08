import os
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


def _get_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_server():
    host = "127.0.0.1"
    port = _get_free_port()
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["DEBUG"] = "0"
    env["USE_RELOADER"] = "0"
    server_proc = subprocess.Popen([sys.executable, "app.py"], env=env)
    assert _wait_for_port(host, port), "Server did not start on assigned port"
    return server_proc, host, port


def test_username_saved_and_restored_from_localstorage():
    server_proc, host, port = _start_server()

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
        server_proc.terminate()
        server_proc.wait(timeout=5)


def test_timer_counts_down():
    server_proc, host, port = _start_server()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            host_page = browser.new_page()

            host_page.goto(f"http://{host}:{port}", wait_until="domcontentloaded")
            host_page.click("#btn-start")

            expect(host_page.locator("#spectator-timer")).to_be_visible()

            def read_timer_seconds():
                return host_page.evaluate(
                    """() => {
                        const root = document.getElementById('spectator-time');
                        if (!root) return null;
                        const intEl = root.querySelector('.timer-int');
                        const decEl = root.querySelector('.timer-dec');
                        const intPart = intEl ? parseInt(intEl.textContent, 10) : 0;
                        const decText = decEl ? decEl.textContent.replace('.', '') : '0';
                        const decPart = parseInt(decText, 10) || 0;
                        return intPart + decPart / 10;
                    }"""
                )

            start_value = read_timer_seconds()
            assert start_value is not None

            host_page.wait_for_timeout(1200)
            end_value = read_timer_seconds()
            assert end_value is not None

            assert end_value < start_value

            browser.close()
    finally:
        server_proc.terminate()
        server_proc.wait(timeout=5)


def test_player_timer_counts_down():
    server_proc, host, port = _start_server()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            host_page = browser.new_page()
            player_page = browser.new_page()

            host_page.goto(f"http://{host}:{port}", wait_until="domcontentloaded")
            player_page.goto(f"http://{host}:{port}", wait_until="domcontentloaded")

            player_page.fill("#username-input", "PlayerTimer")
            player_page.click("#btn-confirm-join")
            expect(player_page.locator("#player-view")).to_be_visible()

            host_page.click("#btn-start")
            expect(player_page.locator("#player-timer")).to_be_visible()

            def read_player_timer_seconds():
                return player_page.evaluate(
                    """() => {
                        const root = document.getElementById('player-time');
                        if (!root) return null;
                        const intEl = root.querySelector('.timer-int');
                        const decEl = root.querySelector('.timer-dec');
                        const intPart = intEl ? parseInt(intEl.textContent, 10) : 0;
                        const decText = decEl ? decEl.textContent.replace('.', '') : '0';
                        const decPart = parseInt(decText, 10) || 0;
                        return intPart + decPart / 10;
                    }"""
                )

            start_value = read_player_timer_seconds()
            assert start_value is not None

            player_page.wait_for_timeout(1200)
            end_value = read_player_timer_seconds()
            assert end_value is not None

            assert end_value < start_value

            browser.close()
    finally:
        server_proc.terminate()
        server_proc.wait(timeout=5)


def test_player_score_includes_rank_for_three_players():
    server_proc, host, port = _start_server()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            p1 = browser.new_page()
            p2 = browser.new_page()
            p3 = browser.new_page()

            p1.goto(f"http://{host}:{port}", wait_until="domcontentloaded")
            p2.goto(f"http://{host}:{port}", wait_until="domcontentloaded")
            p3.goto(f"http://{host}:{port}", wait_until="domcontentloaded")

            p1.fill("#username-input", "Rank1")
            p1.click("#btn-confirm-join")
            expect(p1.locator("#player-view")).to_be_visible()

            p2.fill("#username-input", "Rank2")
            p2.click("#btn-confirm-join")
            expect(p2.locator("#player-view")).to_be_visible()

            p3.fill("#username-input", "Rank3")
            p3.click("#btn-confirm-join")
            expect(p3.locator("#player-view")).to_be_visible()

            expect(p1.locator("#my-player-name")).to_contain_text("#1")
            expect(p2.locator("#my-player-name")).to_contain_text("#2")
            expect(p3.locator("#my-player-name")).to_contain_text("#2")

            browser.close()
    finally:
        server_proc.terminate()
        server_proc.wait(timeout=5)


def test_timer_does_not_show_leading_zero_under_ten_seconds():
    server_proc, host, port = _start_server()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            host_page = browser.new_page()

            host_page.goto(f"http://{host}:{port}", wait_until="domcontentloaded")
            host_page.click("#btn-start")

            def read_timer_text():
                return host_page.evaluate(
                    """() => {
                        const root = document.getElementById('spectator-time');
                        if (!root) return '';
                        return root.textContent.trim();
                    }"""
                )

            host_page.wait_for_timeout(21000)
            text = read_timer_text()
            assert text
            assert not text.startswith("0")

            browser.close()
    finally:
        server_proc.terminate()
        server_proc.wait(timeout=5)


def test_late_join_timer_is_relative_to_remaining_time():
    server_proc, host, port = _start_server()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            host_page = browser.new_page()

            host_page.goto(f"http://{host}:{port}", wait_until="domcontentloaded")
            host_page.click("#btn-start")

            host_page.wait_for_timeout(4000)

            late_page = browser.new_page()
            late_page.goto(f"http://{host}:{port}", wait_until="domcontentloaded")

            def read_timer_seconds(page):
                return page.evaluate(
                    """() => {
                        const root = document.getElementById('spectator-time');
                        if (!root) return null;
                        const intEl = root.querySelector('.timer-int');
                        const decEl = root.querySelector('.timer-dec');
                        const intPart = intEl ? parseInt(intEl.textContent, 10) : 0;
                        const decText = decEl ? decEl.textContent.replace('.', '') : '0';
                        const decPart = parseInt(decText, 10) || 0;
                        return intPart + decPart / 10;
                    }"""
                )

            late_value = read_timer_seconds(late_page)
            assert late_value is not None
            assert late_value < 30

            browser.close()
    finally:
        server_proc.terminate()
        server_proc.wait(timeout=5)
