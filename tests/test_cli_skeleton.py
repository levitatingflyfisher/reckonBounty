"""The rb entry point: help, version, usage-on-no-args."""

import pytest

from reckonbounty import cli


def test_help_exits_zero_and_lists_all_subcommands(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for sub in ("ask", "answer", "score", "validate"):
        assert sub in out


def test_version_flag_reports_package_version(capsys):
    from reckonbounty import __version__

    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_args_prints_usage_and_returns_2(capsys):
    assert cli.main([]) == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_module_is_runnable_as_python_m():
    import reckonbounty.__main__  # noqa: F401 -- importable = wired
