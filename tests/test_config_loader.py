import pytest

from tools.config_loader import load_yaml_with_env


def test_substitutes_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("FOO", "bar")
    p = tmp_path / "c.yaml"
    p.write_text("key: ${FOO}\n")
    assert load_yaml_with_env(str(p)) == {"key": "bar"}


def test_raises_when_env_var_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("MISSING_VAR", raising=False)
    p = tmp_path / "c.yaml"
    p.write_text("key: ${MISSING_VAR}\n")
    with pytest.raises(KeyError, match="MISSING_VAR"):
        load_yaml_with_env(str(p))


def test_passthrough_without_interpolation(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("a: 1\nb:\n  - x\n  - y\n")
    assert load_yaml_with_env(str(p)) == {"a": 1, "b": ["x", "y"]}


def test_multiple_vars_in_one_file(tmp_path, monkeypatch):
    monkeypatch.setenv("USER_X", "alice")
    monkeypatch.setenv("PWD_X", "s3cret")
    p = tmp_path / "c.yaml"
    p.write_text("user: ${USER_X}\npassword: ${PWD_X}\n")
    assert load_yaml_with_env(str(p)) == {"user": "alice", "password": "s3cret"}
