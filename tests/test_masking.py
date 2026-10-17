"""
Masking must give the same person the same token in every document of a pack.

Needs Presidio and a spaCy English model; skipped when they are not installed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

pytest.importorskip("presidio_analyzer")
spacy_util = pytest.importorskip("spacy.util")
if not (spacy_util.is_package("en_core_web_sm") or spacy_util.is_package("en_core_web_lg")):
    pytest.skip("no spaCy English model installed", allow_module_level=True)

from privacy import PIIMasker  # noqa: E402


def test_same_person_same_token_across_documents():
    masker = PIIMasker()
    schedule, s_map = masker.mask(
        "Policyholder: Alex Morgan. Named drivers: Priya Shah and Jordan Reed."
    )
    certificate, c_map = masker.mask(
        "Persons entitled to drive: Jordan Reed, Alex  Morgan, Priya Shah."
    )
    s_tokens = {v: k for k, v in s_map.items()}
    c_tokens = {" ".join(v.split()): k for k, v in c_map.items()}
    for name in ("Alex Morgan", "Priya Shah", "Jordan Reed"):
        if name in s_tokens and name in c_tokens:
            assert s_tokens[name] == c_tokens[name], name
    assert "Alex Morgan" not in certificate


def test_reset_starts_numbering_again():
    masker = PIIMasker()
    first, _ = masker.mask("My name is Alex Morgan.")
    masker.reset()
    second, _ = masker.mask("My name is Priya Shah.")
    assert first.strip() == second.strip()
