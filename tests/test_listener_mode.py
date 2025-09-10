import pytest

from communication_manager import ListenerMode


def test_split_messages_basic():
    buffer = "msg1ENDmsg2\rmsg3\n"
    messages, remaining = ListenerMode._split_messages(buffer)
    assert messages == ["msg1", "msg2", "msg3"]
    assert remaining == ""


def test_split_messages_partial():
    buffer = "helloEN"
    messages, remaining = ListenerMode._split_messages(buffer)
    assert messages == []
    assert remaining == "helloEN"
    buffer = remaining + "DworldEND"
    messages, remaining = ListenerMode._split_messages(buffer)
    assert messages == ["hello", "world"]
    assert remaining == ""


def test_split_messages_mixed_terminators():
    buffer = "a\nb\rcENDd"
    messages, remaining = ListenerMode._split_messages(buffer)
    assert messages == ["a", "b", "c"]
    assert remaining == "d"
