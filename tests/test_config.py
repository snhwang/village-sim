"""A run's record never holds a key (hearthwick/config.py)."""

import pytest

from hearthwick.config import SimConfig


def test_a_run_record_says_a_key_was_set_but_not_what_it_is(tmp_path):
    config = SimConfig(llm_api_key="sk-secret", embed_api_key="emb-secret", runs_dir=tmp_path)
    record = config.to_dict()
    assert record["llm_api_key"] == "(set)" and record["embed_api_key"] == "(set)"
    assert "secret" not in str(record)
    assert config.llm_api_key == "sk-secret"          # the running config keeps it


def test_a_resume_takes_keys_from_the_machine_not_the_record(tmp_path):
    saved = SimConfig(llm_api_key="sk-secret", runs_dir=tmp_path).to_dict()
    current = SimConfig(llm_api_key="sk-today", runs_dir=tmp_path)
    assert SimConfig.from_saved(saved, current).llm_api_key == "sk-today"


def test_no_key_is_recorded_as_none(tmp_path):
    assert SimConfig(runs_dir=tmp_path).to_dict()["llm_api_key"] is None


def test_a_key_named_by_llm_key_env_is_read_from_the_environment(monkeypatch):
    import argparse

    from hearthwick.__main__ import _llm_key
    monkeypatch.setenv("HW_TEST_GATEWAY_KEY", "gw-secret")
    args = argparse.Namespace(llm_key_env="HW_TEST_GATEWAY_KEY", llm_api_key=None)
    assert _llm_key(args) == "gw-secret"
    assert _llm_key(argparse.Namespace(llm_key_env=None, llm_api_key="direct")) == "direct"


def test_a_missing_key_variable_stops_the_run_and_names_only_the_variable(monkeypatch):
    import argparse

    import pytest

    from hearthwick.__main__ import _llm_key
    monkeypatch.delenv("HW_TEST_NO_SUCH_KEY", raising=False)
    with pytest.raises(SystemExit, match="HW_TEST_NO_SUCH_KEY"):
        _llm_key(argparse.Namespace(llm_key_env="HW_TEST_NO_SUCH_KEY", llm_api_key=None))


def test_a_mechanic_left_out_of_this_edition_is_refused():
    with pytest.raises(ValueError, match="wants is not in this edition"):
        SimConfig(wants=True)
    # An archived run records the switch, off, and its record still loads.
    assert SimConfig(wants=False, leisure=False, practice_reinforcement=0.0).wants is False
