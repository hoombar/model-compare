from model_compare import cli, tui


def test_no_arguments_launches_tui(monkeypatch) -> None:
    launched = False

    def fake_run_tui() -> None:
        nonlocal launched
        launched = True

    monkeypatch.setattr(tui, "run_tui", fake_run_tui)

    assert cli.main([]) == 0
    assert launched
