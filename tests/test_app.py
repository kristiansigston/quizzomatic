import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module


class DummyTimer:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.started = False
        self.canceled = False

    def start(self):
        self.started = True

    def cancel(self):
        self.canceled = True


def test_reset_all_initializes_game_state_and_questions(monkeypatch):
    monkeypatch.setattr(app_module.random, "shuffle", lambda seq: None)

    app_module.reset_all()

    game_state = app_module.game_state
    assert game_state["players"] == {}
    assert game_state["current_question_index"] == -1
    assert game_state["current_answers"] == {}
    assert len(app_module.questions) == 5

    for question in app_module.questions:
        assert 0 <= question["correct"] < len(question["answers"])


def test_join_adds_player_and_emits_joined(monkeypatch):
    monkeypatch.setattr(app_module.random, "shuffle", lambda seq: None)

    app_module.reset_all()

    client = app_module.socketio.test_client(app_module.app)
    client.emit("join", {"username": "alice"})

    received = client.get_received()
    joined_events = [item for item in received if item["name"] == "joined"]

    assert joined_events
    assert joined_events[0]["args"][0]["username"] == "alice"
    assert "alice" in app_module.game_state["players"]

    client.disconnect()


def test_answer_scores_points_for_correct_answer(monkeypatch):
    monkeypatch.setattr(app_module.threading, "Timer", DummyTimer)
    monkeypatch.setattr(app_module.time, "time", lambda: 1000.0)

    app_module.reset_all()

    app_module.questions = [
        {
            "question": "Q",
            "answers": ["A", "B", "C", "D"],
            "correct": 0,
        }
    ]

    game_state = app_module.game_state
    game_state["current_question_index"] = 0
    game_state["current_answers"] = {}
    game_state["end_time"] = 1030.0
    game_state["timer_thread"] = DummyTimer()

    client = app_module.socketio.test_client(app_module.app)
    client.emit("join", {"username": "alice"})
    client.get_received()

    client.emit("answer", {"username": "alice", "answer_index": 0})

    assert game_state["players"]["alice"]["score"] == 130

    received = client.get_received()
    player_list_events = [item for item in received if item["name"] == "player_list"]
    assert player_list_events
    last_player_list = player_list_events[-1]["args"][0]["players"]
    assert last_player_list["alice"]["score"] == game_state["players"]["alice"]["score"]

    client.disconnect()


def test_incorrect_answers_do_not_gain_points_with_three_players(monkeypatch):
    monkeypatch.setattr(app_module.threading, "Timer", DummyTimer)
    monkeypatch.setattr(app_module.time, "time", lambda: 1000.0)

    app_module.reset_all()

    app_module.questions = [
        {
            "question": "Q",
            "answers": ["A", "B", "C", "D"],
            "correct": 0,
        }
    ]

    game_state = app_module.game_state
    game_state["current_question_index"] = 0
    game_state["current_answers"] = {}
    game_state["end_time"] = 1030.0
    game_state["timer_thread"] = DummyTimer()

    clients = [
        app_module.socketio.test_client(app_module.app),
        app_module.socketio.test_client(app_module.app),
        app_module.socketio.test_client(app_module.app),
    ]

    for idx, client in enumerate(clients, start=1):
        client.emit("join", {"username": f"p{idx}"})
        client.get_received()

    clients[0].emit("answer", {"username": "p1", "answer_index": 0})
    clients[1].emit("answer", {"username": "p2", "answer_index": 1})
    clients[2].emit("answer", {"username": "p3", "answer_index": 2})

    assert game_state["players"]["p1"]["score"] == 130
    assert game_state["players"]["p2"]["score"] == 0
    assert game_state["players"]["p3"]["score"] == 0

    for client in clients:
        client.disconnect()
