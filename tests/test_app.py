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


def test_is_game_started_false_when_no_current_question(monkeypatch):
    monkeypatch.setattr(app_module.random, "shuffle", lambda seq: None)
    app_module.reset_all()

    assert app_module.is_game_started() is False


def test_is_game_started_true_when_index_in_range(monkeypatch):
    monkeypatch.setattr(app_module.random, "shuffle", lambda seq: None)
    app_module.reset_all()

    app_module.game_state["current_question_index"] = 0
    assert app_module.is_game_started() is True


def test_stop_timer_thread_cancels_existing_timer(monkeypatch):
    app_module.reset_all()
    timer = DummyTimer()
    app_module.game_state["timer_thread"] = timer

    app_module.stop_timer_thread()

    assert timer.canceled is True
    assert app_module.game_state["timer_thread"] is None


def test_add_scores_for_correct_answers_sets_intermission_and_scores(monkeypatch):
    monkeypatch.setattr(app_module.time, "time", lambda: 1000.0)

    app_module.reset_all()
    app_module.questions = [
        {"question": "Q", "answers": ["A", "B", "C", "D"], "correct": 0}
    ]
    game_state = app_module.game_state
    game_state["current_question_index"] = 0
    game_state["end_time"] = 1030.0
    game_state["players"] = {
        "p1": {"score": 0, "sid": "sid1", "ip": "127.0.0.1"}
    }
    game_state["current_answers"] = {
        "sid1": {"username": "p1", "answer_index": 0, "time": 1000.0}
    }

    app_module.add_scores_for_correct_answers()

    assert game_state["players"]["p1"]["score"] == 130
    assert game_state["intermission_duration"] == 5


def test_process_answers_marks_processed_and_starts_intermission(monkeypatch):
    monkeypatch.setattr(app_module.threading, "Timer", DummyTimer)
    monkeypatch.setattr(app_module.time, "time", lambda: 1000.0)

    app_module.reset_all()
    app_module.questions = [
        {"question": "Q", "answers": ["A", "B", "C", "D"], "correct": 0}
    ]
    game_state = app_module.game_state
    game_state["current_question_index"] = 0
    game_state["end_time"] = 1030.0
    game_state["players"] = {
        "p1": {"score": 0, "sid": "sid1", "ip": "127.0.0.1"},
        "p2": {"score": 0, "sid": "sid2", "ip": "127.0.0.1"},
    }
    game_state["current_answers"] = {
        "sid1": {"username": "p1", "answer_index": 0, "time": 1000.0},
        "sid2": {"username": "p2", "answer_index": 1, "time": 1000.0},
    }
    game_state["timer_thread"] = DummyTimer()

    app_module.process_answers()

    assert game_state["answers_processed"] is True
    assert game_state["current_answers"] == {}
    assert game_state["intermission_active"] is True
    assert isinstance(game_state["intermission_timer_thread"], DummyTimer)
    assert game_state["intermission_timer_thread"].started is True


def test_resolve_scores_orders_and_returns_winners(monkeypatch):
    app_module.reset_all()
    app_module.game_state["players"] = {
        "p1": {"score": 50, "sid": "sid1", "ip": "127.0.0.1"},
        "p2": {"score": 100, "sid": "sid2", "ip": "127.0.0.1"},
        "p3": {"score": 100, "sid": "sid3", "ip": "127.0.0.1"},
    }

    sorted_players, winners = app_module.resolve_scores()

    assert [name for name, _ in sorted_players][:2] == ["p2", "p3"]
    assert set(winners) == {"p2", "p3"}


def test_send_player_details_emits_sorted_scores(monkeypatch):
    emitted = {}

    def fake_emit(event, payload=None, **_kwargs):
        emitted["event"] = event
        emitted["payload"] = payload

    monkeypatch.setattr(app_module.socketio, "emit", fake_emit)

    app_module.reset_all()
    app_module.game_state["players"] = {
        "p1": {"score": 10, "sid": "sid1", "ip": "127.0.0.1"},
        "p2": {"score": 20, "sid": "sid2", "ip": "127.0.0.1"},
    }

    app_module.send_player_details()

    assert emitted["event"] == "player_list"
    assert list(emitted["payload"]["players"].keys()) == ["p2", "p1"]


def test_reset_game_zeroes_scores_and_sets_questions(monkeypatch):
    monkeypatch.setattr(app_module.random, "shuffle", lambda seq: None)

    app_module.reset_all()
    app_module.game_state["players"] = {
        "p1": {"score": 10, "sid": "sid1", "ip": "127.0.0.1"},
        "p2": {"score": 5, "sid": "sid2", "ip": "127.0.0.1"},
    }

    app_module.reset_game()

    assert app_module.game_state["current_question_index"] == -1
    assert app_module.game_state["current_answers"] == {}
    assert app_module.game_state["players"]["p1"]["score"] == 0
    assert app_module.game_state["players"]["p2"]["score"] == 0
    assert len(app_module.questions) == 5

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
    game_state["end_time"] = 1030.0
    game_state["players"] = {
        "alice": {"score": 0, "sid": "sid1", "ip": "127.0.0.1"}
    }
    game_state["current_answers"] = {
        "sid1": {"username": "alice", "answer_index": 0, "time": 1000.0}
    }

    app_module.add_scores_for_correct_answers()

    assert game_state["players"]["alice"]["score"] == 130


def test_incorrect_answers_do_not_gain_points_with_three_players(monkeypatch):
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
    game_state["end_time"] = 1030.0

    game_state["players"] = {
        "p1": {"score": 0, "sid": "sid1", "ip": "127.0.0.1"},
        "p2": {"score": 0, "sid": "sid2", "ip": "127.0.0.1"},
        "p3": {"score": 0, "sid": "sid3", "ip": "127.0.0.1"},
    }
    game_state["current_answers"] = {
        "sid1": {"username": "p1", "answer_index": 0, "time": 1000.0},
        "sid2": {"username": "p2", "answer_index": 1, "time": 1000.0},
        "sid3": {"username": "p3", "answer_index": 2, "time": 1000.0},
    }

    app_module.add_scores_for_correct_answers()

    assert game_state["players"]["p1"]["score"] == 130
    assert game_state["players"]["p2"]["score"] == 0
    assert game_state["players"]["p3"]["score"] == 0
