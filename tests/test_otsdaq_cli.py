"""End-to-end CLI tests using the fake otsdaq server."""

import json

from fake_otsdaq import FakeOtsdaq
from mu2edaq_commandline_tools import cli


def write_config(path, fake, verify_tls=True):
    path.write_text(
        "otsdaq:\n"
        "  default_instance: test\n"
        "  verify_tls: %s\n"
        "  instances:\n"
        "    test:\n"
        "      gateway_url: %s\n"
        "      slow_controls_url: %s\n"
        "      tfm_url: %s\n"
        % (
            str(verify_tls).lower(),
            fake.origin("gateway"),
            fake.origin("slow-controls"),
            fake.origin("tfm"),
        ),
        encoding="utf-8",
    )


def test_state_json_and_watch_ndjson(tmp_path, capsys):
    with FakeOtsdaq() as fake:
        fake.add(
            "gateway",
            "getCurrentState",
            '<ROOT><DATA state="Running"/></ROOT>',
            repeat=2,
        )
        config = tmp_path / "tools.yaml"
        write_config(config, fake)
        status = cli.main(
            [
                "--config",
                str(config),
                "otsdaq",
                "state",
                "--json",
                "--watch",
                "--count",
                "2",
                "--interval",
                "0.001",
            ]
        )
    assert status == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["data"]["state"] == "Running" for line in lines)


def test_raw_json_and_warning(tmp_path, capsys):
    body = '<ROOT><DATA><value value="ok"/></DATA></ROOT>'
    with FakeOtsdaq() as fake:
        fake.add("gateway", "ExpertRead", body)
        config = tmp_path / "tools.yaml"
        write_config(config, fake)
        status = cli.main(
            [
                "--config",
                str(config),
                "otsdaq",
                "raw",
                "ExpertRead",
                "--query",
                "a=b",
                "--form",
                "c=d",
            ]
        )
        request = fake.requests[0]
    captured = capsys.readouterr()
    assert status == 0
    assert json.loads(captured.out)["ROOT"]["DATA"]["value"]["@attributes"]["value"] == "ok"
    assert "unrestricted" in captured.err
    assert request.query["a"] == ["b"]
    assert request.form["c"] == ["d"]


def test_raw_xml_is_exact(tmp_path, capsys):
    body = '<ROOT><DATA answer="42"/></ROOT>'
    with FakeOtsdaq() as fake:
        fake.add("gateway", "Exact", body)
        config = tmp_path / "tools.yaml"
        write_config(config, fake)
        status = cli.main(
            ["--config", str(config), "otsdaq", "raw", "Exact", "--xml"]
        )
    assert status == 0
    assert capsys.readouterr().out == body


def test_insecure_warning_stays_on_stderr(tmp_path, capsys):
    with FakeOtsdaq() as fake:
        fake.add("gateway", "getCurrentState", '<ROOT><DATA state="Idle"/></ROOT>')
        config = tmp_path / "tools.yaml"
        write_config(config, fake, verify_tls=False)
        status = cli.main(
            ["--config", str(config), "otsdaq", "state", "--json"]
        )
    captured = capsys.readouterr()
    assert status == 0
    assert json.loads(captured.out)["data"]["state"] == "Idle"
    assert "verification is disabled" in captured.err


def test_console_watch_advances_server_cursor(tmp_path, capsys):
    with FakeOtsdaq() as fake:
        fake.add(
            "gateway",
            "GetConsoleMsgs",
            '<ROOT><DATA lcount="7"><message value="first"/></DATA></ROOT>',
        )
        fake.add(
            "gateway",
            "GetConsoleMsgs",
            '<ROOT><DATA lcount="9"><message value="second"/></DATA></ROOT>',
        )
        config = tmp_path / "tools.yaml"
        write_config(config, fake)
        status = cli.main(
            [
                "--config",
                str(config),
                "otsdaq",
                "console",
                "--lcount",
                "3",
                "--watch",
                "--count",
                "2",
                "--interval",
                "0.001",
                "--json",
            ]
        )
        counts = [request.form["lcount"] for request in fake.requests]
    assert status == 0
    assert counts == [["3"], ["7"]]
    assert len(capsys.readouterr().out.splitlines()) == 2


def test_cli_reports_connection_and_argument_errors(tmp_path, capsys):
    missing = tmp_path / "missing.yaml"
    missing.write_text("otsdaq:\n  instances: {}\n", encoding="utf-8")
    assert cli.main(["--config", str(missing), "otsdaq", "state"]) == 1
    assert "no otsdaq instance" in capsys.readouterr().err

    with FakeOtsdaq() as fake:
        config = tmp_path / "tools.yaml"
        write_config(config, fake)
        assert (
            cli.main(
                [
                    "--config",
                    str(config),
                    "otsdaq",
                    "state",
                    "--count",
                    "2",
                ]
            )
            == 2
        )
    assert "--count requires --watch" in capsys.readouterr().err
