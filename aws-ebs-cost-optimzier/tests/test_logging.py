from __future__ import annotations

import json
import logging

from ebs_optimizer.logging_config import JsonFormatter, configure_logging


def test_json_log_includes_structured_fields_and_does_not_add_secrets():
    record = logging.LogRecord("test", logging.INFO, "", 0, "inventory scanned", (), None)
    record.fields = {"accounts": 3, "regions": 4}
    output = json.loads(JsonFormatter().format(record))
    assert output["event"] == "inventory scanned"
    assert output["accounts"] == 3
    assert "secret" not in output


def test_configure_logging_sets_json_handler():
    logger = configure_logging("DEBUG")
    assert logger.level == logging.DEBUG
    assert isinstance(logger.handlers[0].formatter, JsonFormatter)
