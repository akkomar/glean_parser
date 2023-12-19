# -*- coding: utf-8 -*-

# Any copyright is dedicated to the Public Domain.
# http://creativecommons.org/publicdomain/zero/1.0/

from pathlib import Path

import glean_parser
from glean_parser import translate

ROOT = Path(__file__).parent


def test_parser_go_server_ping_no_metrics(tmpdir, capsys):
    """Test that no files are generated if only ping definitions
    are provided without any metrics."""
    tmpdir = Path(str(tmpdir))

    translate.translate(
        ROOT / "data" / "server_pings.yaml",
        "go_server",
        tmpdir,
    )
    assert all(False for _ in tmpdir.iterdir())


def test_parser_go_server_ping_file(tmpdir, capsys):
    """Test that no files are generated if ping definitions
    are provided."""
    tmpdir = Path(str(tmpdir))

    translate.translate(
        [
            ROOT / "data" / "server_metrics_with_event.yaml",
            ROOT / "data" / "server_pings.yaml",
        ],
        "go_server",
        tmpdir,
    )
    assert all(False for _ in tmpdir.iterdir())


def test_parser_go_server_metrics_no_ping(tmpdir, capsys):
    """Test that no files are generated if only metric definitions
    are provided without any events metrics."""
    tmpdir = Path(str(tmpdir))

    translate.translate(
        ROOT / "data" / "server_metrics_no_events_no_pings.yaml",
        "go_server",
        tmpdir,
    )

    captured = capsys.readouterr()
    assert all(False for _ in tmpdir.iterdir())
    assert (
        "No event metrics found...at least one event metric is required" in captured.out
    )


def test_parser_go_server_metrics_unsupported_type(tmpdir, capsys):
    """Test that no files are generated with unsupported metric types."""
    tmpdir = Path(str(tmpdir))

    translate.translate(
        [
            ROOT / "data" / "go_server_metrics_unsupported.yaml",
        ],
        "go_server",
        tmpdir,
    )
    captured = capsys.readouterr()
    assert "Ignoring unsupported metric type" in captured.out
    unsupported_types = [
        "boolean",
        "labeled_boolean",
        "labeled_string",
        "string_list",
        "timespan",
        "uuid",
        "url",
        "datetime",
    ]
    for t in unsupported_types:
        assert t in captured.out


def test_parser_go_server(tmpdir):
    """Test that parser works"""
    tmpdir = Path(str(tmpdir))

    translate.translate(
        ROOT / "data" / "go_server_metrics.yaml",
        "go_server",
        tmpdir,
    )

    assert set(x.name for x in tmpdir.iterdir()) == set(["server_events.go"])

    # Make sure generated file matches expected
    with (tmpdir / "server_events.go").open("r", encoding="utf-8") as fd:
        content = fd.read()
        with (ROOT / "data" / "server_events_compare.go").open(
            "r", encoding="utf-8"
        ) as cd:
            compare_raw = cd.read()

    glean_version = f"glean_parser v{glean_parser.__version__}"
    # use replace instead of format since Go uses { }
    compare = compare_raw.replace("{current_version}", glean_version)
    assert content == compare
