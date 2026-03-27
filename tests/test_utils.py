"""Tests for utils.py - validators, sanitizers, and utilities."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils import (
    validate_ticket_code,
    validate_email,
    validate_url,
    truncate_string,
    safe_get_dict,
    format_duration,
)
from exceptions import ValidationError


class TestValidateTicketCode:
    def test_valid_code(self):
        assert validate_ticket_code("26-083-026025") == "26-083-026025"

    def test_valid_hex_id(self):
        assert validate_ticket_code("00294000001e8cbd") == "00294000001e8cbd"

    def test_invalid_format(self):
        with pytest.raises(ValidationError):
            validate_ticket_code("invalid-code")

    def test_empty_string(self):
        with pytest.raises(ValidationError):
            validate_ticket_code("")

    def test_none(self):
        with pytest.raises(ValidationError):
            validate_ticket_code(None)


class TestValidateEmail:
    def test_valid_email(self):
        assert validate_email("test@example.com") == "test@example.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            validate_email("not-an-email")

    def test_empty(self):
        with pytest.raises(ValidationError):
            validate_email("")


class TestValidateUrl:
    def test_valid_https(self):
        assert validate_url("https://example.com") == "https://example.com"

    def test_valid_http(self):
        assert validate_url("http://example.com") == "http://example.com"

    def test_invalid_url(self):
        with pytest.raises(ValidationError):
            validate_url("ftp://example.com")

    def test_empty(self):
        with pytest.raises(ValidationError):
            validate_url("")



class TestTruncateString:
    def test_short_string(self):
        assert truncate_string("hello", 10) == "hello"

    def test_exact_length(self):
        assert truncate_string("hello", 5) == "hello"

    def test_long_string(self):
        result = truncate_string("hello world", 8)
        assert len(result) <= 8
        assert result.endswith("...")

    def test_custom_suffix(self):
        result = truncate_string("hello world", 8, suffix="…")
        assert result.endswith("…")

    def test_non_string(self):
        assert truncate_string(123, 5) == 123


class TestSafeGetDict:
    def test_single_key(self):
        assert safe_get_dict({"a": 1}, "a") == 1

    def test_nested_keys(self):
        assert safe_get_dict({"a": {"b": {"c": 3}}}, "a", "b", "c") == 3

    def test_missing_key(self):
        assert safe_get_dict({"a": 1}, "b") is None

    def test_missing_key_with_default(self):
        assert safe_get_dict({"a": 1}, "b", default="N/A") == "N/A"

    def test_non_dict_input(self):
        assert safe_get_dict("not a dict", "key") is None

    def test_none_in_path(self):
        assert safe_get_dict({"a": None}, "a", "b") is None


class TestFormatDuration:
    def test_sub_second(self):
        assert "s" in format_duration(0.5)

    def test_seconds(self):
        assert format_duration(45) == "45s"

    def test_minutes(self):
        assert format_duration(90) == "1m 30s"

    def test_hours(self):
        assert format_duration(3660) == "1h 1m"
