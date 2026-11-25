from pathlib import Path

from cross_account_iam.cli import main

ROOT = Path(__file__).parents[1]


def test_cli_validate_config_is_offline(capsys):
    assert main(["validate-config", "--config", str(ROOT / "config/config.example.yaml")]) == 0
    assert '"valid": true' in capsys.readouterr().out


def test_cli_validate_policy(capsys):
    args = ["validate-policy"]
    for key, fixture in [
        ("--trust-policy", "trust-policy"),
        ("--source-policy", "source-policy"),
        ("--target-policy", "target-policy"),
    ]:
        args += [key, str(ROOT / f"examples/{fixture}.example.json")]
    assert main(args) == 0
    assert '"valid": true' in capsys.readouterr().out


def test_cli_writes_redacted_report(tmp_path, capsys):
    output = tmp_path / "report.json"
    assert (
        main(
            [
                "report",
                "--config",
                str(ROOT / "config/config.example.yaml"),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert "redacted" in output.read_text()
    assert "AWS_CROSS_ACCOUNT_EXTERNAL_ID" not in output.read_text()
