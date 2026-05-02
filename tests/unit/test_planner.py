import json
from unittest.mock import patch

from graph.nodes.planner import planner
from tools.llm import StreamResult

STATE = {
    "intent": ["tasks"],
    "detected_skills": ["reminder"],
    "engineered_message": "add milk to my list",
    "user_id": "u1",
    "message_id": "m1",
}


def _make_result(json_str):
    return StreamResult(model="any", tokens=iter([json_str]))


def test_valid_step_list():
    steps_json = json.dumps([{
        "id": "add_milk",
        "intent": "tasks",
        "skill_name": None,
        "description": "Add milk to the task list",
        "depends_on": [],
    }])
    with patch("graph.nodes.planner.stream_chat") as mock_stream_chat:
        mock_stream_chat.return_value = _make_result(steps_json)
        result = planner(STATE)
    assert "step_plan" in result
    plan = result["step_plan"]
    assert len(plan) == 1
    assert plan[0]["id"] == "add_milk"
    assert plan[0]["intent"] == "tasks"
    assert plan[0]["skill_name"] is None
    assert plan[0]["description"] == "Add milk to the task list"
    assert plan[0]["depends_on"] == []
    assert plan[0]["prompt"] == ""


def test_stream_chat_raises_returns_inference_error():
    with patch("graph.nodes.planner.stream_chat") as mock_stream_chat:
        mock_stream_chat.side_effect = Exception("model down")
        result = planner(STATE)
    assert result == {"error": "PLANNER failed to produce a step plan"}


def test_invalid_json_returns_inference_error():
    with patch("graph.nodes.planner.stream_chat") as mock_stream_chat:
        mock_stream_chat.return_value = _make_result("not valid json {{{")
        result = planner(STATE)
    assert result == {"error": "PLANNER failed to produce a step plan"}


def test_missing_required_field_returns_malformed_error():
    steps_json = json.dumps([{
        "id": "add_milk",
        "intent": "tasks",
        # "description" deliberately omitted
        "depends_on": [],
    }])
    with patch("graph.nodes.planner.stream_chat") as mock_stream_chat:
        mock_stream_chat.return_value = _make_result(steps_json)
        result = planner(STATE)
    assert result == {"error": "PLANNER output was malformed"}


def test_depends_on_absent_defaults_to_empty_list():
    steps_json = json.dumps([{
        "id": "add_milk",
        "intent": "tasks",
        "skill_name": None,
        "description": "Add milk to the task list",
        # "depends_on" deliberately omitted
    }])
    with patch("graph.nodes.planner.stream_chat") as mock_stream_chat:
        mock_stream_chat.return_value = _make_result(steps_json)
        result = planner(STATE)
    assert result["step_plan"][0]["depends_on"] == []


def test_skill_name_absent_defaults_to_none():
    steps_json = json.dumps([{
        "id": "add_milk",
        "intent": "tasks",
        # "skill_name" deliberately omitted
        "description": "Add milk to the task list",
        "depends_on": [],
    }])
    with patch("graph.nodes.planner.stream_chat") as mock_stream_chat:
        mock_stream_chat.return_value = _make_result(steps_json)
        result = planner(STATE)
    assert result["step_plan"][0]["skill_name"] is None
