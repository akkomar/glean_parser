# -*- coding: utf-8 -*-

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Outputter to generate server Go code for collecting events.

This outputter is different from the rest of the outputters in that the code it
generates does not use the Glean SDK. It is meant to be used to collect events
in server-side environments. In these environments SDK assumptions to measurement
window and connectivity don't hold.
Generated code takes care of assembling pings with metrics, and serializing to messages
conforming to Glean schema.

Warning: this outputter supports limited set of metrics,
see `SUPPORTED_METRIC_TYPES` below.

The generated code creates the following:
* Two methods for logging an Event metric, one with and one without user request info specified
* Two methods for logging a custom ping, one with and one without user request info specified
"""
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Optional, List

from . import __version__
from . import metrics
from . import util

# Adding a metric here will require updating the `generate_metric_type` function
# and require adjustments to `metrics` variables the the template.
SUPPORTED_METRIC_TYPES = ["string", "quantity", "event"]


def generate_event_type_name(metric: metrics.Metric) -> str:
    return f"Event{util.Camelize(metric.category)}{util.Camelize(metric.name)}"


def generate_ping_type_name(ping_name: str) -> str:
    return f"Ping{util.Camelize(ping_name)}"


def generate_metric_name(metric: metrics.Metric) -> str:
    return f"{metric.category}.{metric.name}"


def generate_extra_name(extra: str) -> str:
    return util.Camelize(extra)


def generate_metric_argument_name(metric: metrics.Metric) -> str:
    return f"{util.Camelize(metric.category)}{util.Camelize(metric.name)}"


def generate_metric_type(metric_type: str) -> str:
    if metric_type == "quantity":
        return "int64"
    elif metric_type == "string":
        return "string"
    else:
        print("❌ Unable to generate Go type from metric type: " + metric.type)
        exit


def clean_string(s: str) -> str:
    return s.replace("\n", " ").rstrip()


def output_go(
    objs: metrics.ObjectTree,
    output_dir: Path,
    options: Optional[Dict[str, Any]]
) -> None:
    """
    Given a tree of objects, output Go code to `output_dir`.

    The output is a single file containing all the code for assembling pings with
    metrics, serializing, and submitting.

    :param objects: A tree of objects (metrics and pings) as returned from
        `parser.parse_objects`.
    :param output_dir: Path to an output directory to write to.
    """

    template = util.get_jinja2_template(
        "go_server.jinja2",
        filters=(
            ("event_type_name", generate_event_type_name),
            ("event_extra_name", generate_extra_name),
            ("ping_type_name", generate_ping_type_name),
            ("metric_name", generate_metric_name),
            ("metric_argument_name", generate_metric_argument_name),
            ("go_metric_type", generate_metric_type),
            ("clean_string", clean_string),
        ),
    )

    event_metric_exists = False

    # Go through all metrics in objs and build a map of
    # ping->list of metric categories->list of metrics
    # for easier processing in the template.
    ping_to_metrics: Dict[str, Dict[str, List[metrics.Metric]]] = defaultdict(dict)
    for _category_key, category_val in objs.items():
        for _metric_name, metric in category_val.items():
            if isinstance(metric, metrics.Metric):
                if metric.type not in SUPPORTED_METRIC_TYPES:
                    print(
                        "❌ Ignoring unsupported metric type: "
                        + f"{metric.type}:{metric.name}."
                        + " Reach out to Glean team to add support for this"
                        + " metric type."
                    )
                    continue
                if metric.type == "event":
                    # This is used in the template - generated code is slightly
                    # different when event metric type is used.
                    event_metric_exists = True
                for ping in metric.send_in_pings:
                    metrics_by_type = ping_to_metrics[ping]
                    metrics_list = metrics_by_type.setdefault(metric.type, [])
                    metrics_list.append(metric)

    PING_METRIC_ERROR_MSG = (
        " Server-side environment is simplified and this"
        + " parser doesn't generate individual metric files. Make sure to pass all"
        + " your ping and metric definitions in a single invocation of the parser."
    )
    if "pings" not in objs:
        # If events are meant to be sent in custom pings, we need to make sure they
        # are defined. Otherwise we won't have destination tables defined and
        # submissions won't pass validation at ingestion.
        if event_metric_exists:
            if "events" not in ping_to_metrics:
                # Event metrics can be sent in standard `events` ping
                # or in custom pings.
                print(
                    "❌ "
                    + PING_METRIC_ERROR_MSG
                    + "\n You need to either send your event metrics in standard"
                    + " `events` ping or define a custom one."
                )
                return
        else:
            print("❌ No ping definition found." + PING_METRIC_ERROR_MSG)
            return

    if not ping_to_metrics:
        print("❌ No pings with metrics found." + PING_METRIC_ERROR_MSG)
        return

    extension = ".go"
    filepath = output_dir / ("server_events" + extension)
    with filepath.open("w", encoding="utf-8") as fd:
        fd.write(
            template.render(
                parser_version=__version__,
                pings=ping_to_metrics,
                event_metric_exists=event_metric_exists
            )
        )
