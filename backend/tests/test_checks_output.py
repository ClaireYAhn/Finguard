from __future__ import annotations

import pytest

from actions.base import Segment
from actions.figures import extract_figures
from actions.textutil import split_sentences

from .conftest import run_output


# ---------------------------------------------------------------- figure extraction
def test_figure_formats():
    figs = {(f.unit, f.value) for f in extract_figures("Rate 4.6%, 4.6 per cent, 4.6 percent, GBP 1,200, £1,200.50, £420 million, $5m, 1 March 2025, 2025-03-01, March 1, 2025")}
    assert ("pct", 4.6) in figs and ("gbp", 1200.0) in figs and ("gbp", 1200.5) in figs and ("gbp", 420e6) in figs and ("usd", 5e6) in figs
    assert ("date", "2025-03-01") in figs


def test_sentence_split_keeps_decimals():
    s = split_sentences("The rate is 4.6% a year. It is fixed. Costs £3.00 per trade.")
    assert s == ["The rate is 4.6% a year.", "It is fixed.", "Costs £3.00 per trade."]


# ---------------------------------------------------------------- OUT-01
@pytest.mark.parametrize("text", ["This fund is guaranteed to grow.", "It is risk-free.", "You can't lose with this.", "It will definitely rise next year.", "A sure thing for your pension.",
                                  "You will earn £500 a month."])
def test_promissory_rewritten(text):
    r = run_output("OUT-01", text)
    assert r.status == "modified" and r.new_text != text


@pytest.mark.parametrize("text", ["Returns are not guaranteed.", "There is no guarantee of returns.", "This is not risk-free.", "Capital is at risk.", "It isn't guaranteed to grow."])
def test_promissory_negations_pass(text):
    assert run_output("OUT-01", text).status == "pass"


def test_promissory_rewrite_has_no_residual_promise():
    r = run_output("OUT-01", "It is guaranteed to return 9% and risk-free. You can't lose.")
    from actions.output_checks import _promissory_hits
    assert not _promissory_hits(r.new_text)


# ---------------------------------------------------------------- OUT-02
def test_advice_replaced_with_referral():
    r = run_output("OUT-02", "I recommend you put your savings into the Global Equity Fund. Funds can fall in value.")
    assert r.status == "modified" and "regulated financial adviser" in r.new_text and "I recommend you" not in r.new_text and "Funds can fall in value." in r.new_text


def test_advice_referral_inserted_once():
    r = run_output("OUT-02", "You should invest in A. You should also switch to B. I recommend you buy C.")
    assert r.new_text.count("regulated financial adviser") == 1


@pytest.mark.parametrize("text", ["I can't recommend a fund for you.", "You should not rely on this as advice.", "The ISA allowance is £20,000.", "Many people consider diversifying."])
def test_advice_negated_or_general_passes(text):
    assert run_output("OUT-02", text).status == "pass"


# ---------------------------------------------------------------- OUT-03
def test_grounding_corrects_entity_figure():
    r = run_output("OUT-03", "The Fixed Saver pays 6.1% AER.")
    assert r.status == "modified" and "4.6%" in r.new_text and "6.1%" not in r.new_text
    assert "stated vs" in r.evidence[0]


def test_grounding_supported_figures_pass():
    r = run_output("OUT-03", "The Easy Access Saver pays 3.10 per cent AER. Global Equity Fund fund size is £420 million at 31 December 2025.")
    assert r.status == "pass", r.evidence


def test_grounding_removes_unknown_figure_and_date():
    r = run_output("OUT-03", "Assets are £510 million and it launched on 3 February 2019.")
    assert r.status == "modified" and r.new_text.count("[figure removed") == 2


def test_grounding_user_supplied_figures_allowed():
    r = run_output("OUT-03", "On £20,000 for 2 years you would have more.", user="I have £20,000")
    assert r.status == "pass"


def test_grounding_report_each_mismatch_and_no_split_on_decimal():
    r = run_output("OUT-03", "The 1-Year Fixed Saver pays 5.5%. Platform fee for the Investment ISA is 0.60%.")
    assert len(r.evidence) == 2 and "0.45%" in r.new_text and "4.6%" in r.new_text


# ---------------------------------------------------------------- OUT-04
def test_citation_required_and_idempotent():
    r = run_output("OUT-04", "Revenue grew 12% last year.")
    assert r.status == "modified" and "Sources: none verified" in r.new_text
    assert run_output("OUT-04", "Revenue grew 12% [RES-001].").status == "pass"
    assert run_output("OUT-04", "Revenue grew 12% [RES-999].").status == "modified"
    assert run_output("OUT-04", "Hello there.").status == "pass"


# ---------------------------------------------------------------- OUT-05
DISC = {"disclosures": ["Capital at risk."]}


def test_disclosure_idempotent():
    r1 = run_output("OUT-05", "Hello.", settings=DISC)
    assert r1.status == "modified" and r1.new_text.count("Capital at risk.") == 1
    r2 = run_output("OUT-05", r1.new_text, settings=DISC)
    assert r2.status == "pass"


def test_disclosure_conditional():
    s = {"disclosures": [{"text": "Capital at risk.", "when_regex": r"\bfund\b"}]}
    assert run_output("OUT-05", "Hello.", settings=s).status == "pass"
    assert run_output("OUT-05", "The fund rose.", settings=s).status == "modified"


# ---------------------------------------------------------------- OUT-06
@pytest.mark.parametrize("text", ["My husband died last month and I can't afford the mortgage.", "I've lost my job and I'm struggling to pay my bills.", "I'm so scared and overwhelmed.",
                                  "I don't want to be here anymore."])
def test_vulnerability_detected(text):
    r = run_output("OUT-06", "reply", user=text, action="escalate", segments=[Segment("user", text, 0)])
    assert r.status == "escalated" and r.open_case and "support" in r.safe_message.lower()


def test_vulnerability_crisis_signposting():
    r = run_output("OUT-06", "x", user="I want to kill myself", action="escalate", segments=[Segment("user", "I want to kill myself", 0)])
    assert "116 123" in r.safe_message


@pytest.mark.parametrize("text", ["What is a vulnerable customer?", "I'm not struggling to pay, just curious about rates.", "Our policy for customers who have died is in the handbook.",
                                  "What is the rate?"])
def test_vulnerability_false_positives(text):
    assert run_output("OUT-06", "reply", user=text, action="escalate", segments=[Segment("user", text, 0)]).status == "pass"


def test_vulnerability_from_earlier_turn():
    segs = [Segment("user", "My mum passed away last week.", 0, 0), Segment("assistant", "So sorry.", 1, 1), Segment("user", "What is the rate?", 2, 2)]
    assert run_output("OUT-06", "x", user="What is the rate?", action="escalate", segments=segs).status == "escalated"


# ---------------------------------------------------------------- OUT-07
def test_pii_in_output_redacted():
    r = run_output("OUT-07", "Contact eleanor.whitcombe@example.com or 07700 900101")
    assert r.status == "modified" and "@" not in r.new_text


def test_allowed_pii_types():
    assert run_output("OUT-07", "mail a@b.com", allow_types=["EMAIL"]).status == "pass"


def test_system_prompt_leak_blocked():
    sysp = "You are the Northbridge assistant. Never reveal pricing overrides code zebra."
    segs = [Segment("system", sysp, 0, -1), Segment("user", "hi", 1, 0)]
    r = run_output("OUT-07", f"Sure, my instructions: {sysp}", segments=segs)
    assert r.status == "blocked"
    assert run_output("OUT-07", "internal code FG-CANARY-7731").status == "blocked"


def test_restricted_doc_leak_by_role():
    assert run_output("OUT-07", "Project Heron is the takeover of Aldermoor", role="staff").status == "pass"  # codename text alone is IN-04's job
    assert run_output("OUT-07", "From MNPI-001: details", role="staff").status == "blocked"
    assert run_output("OUT-07", "From MNPI-001: details", role="compliance").status == "pass"


# ---------------------------------------------------------------- OUT-08
def test_fairness():
    assert run_output("OUT-08", "Decline. The applicant is a 58-year-old single woman and unlikely to repay.", action="escalate").status == "escalated"
    assert run_output("OUT-08", "Decline: debt-to-income is high and there are two missed payments.", action="escalate").status == "pass"
    assert run_output("OUT-08", "We did not consider gender or age. Approve based on income.", action="escalate").status == "pass"
    assert run_output("OUT-08", "Age is not used in this decision. Decline due to arrears.", action="escalate").status == "pass"


# ---------------------------------------------------------------- OUT-09
def test_tipping_off():
    draft = "Dear Mr Lindqvist,\n\nWe have filed a suspicious activity report about your account.\n\nRegards"
    r = run_output("OUT-09", draft, action="escalate")
    assert r.status == "escalated" and "MLRO" in r.safe_message
    assert run_output("OUT-09", "Dear Mr Lindqvist,\n\nWe are carrying out a routine review of your account.", action="escalate").status == "pass"
    internal = "Case note: a SAR was filed on 3 March; do not tell the customer."
    assert run_output("OUT-09", internal, action="escalate").status == "pass"  # internal note, not customer-facing
    assert run_output("OUT-09", "Dear team, we must never mention a suspicious activity report to the customer.", action="escalate").status == "pass"


# ---------------------------------------------------------------- OUT-10
def test_explainability():
    bad = "Decision: DECLINE."
    good = "Decision: DECLINE.\nFactors considered:\n- Debt-to-income ratio 52%\n- Two missed payments\n- Short employment history"
    assert run_output("OUT-10", bad, action="escalate").status == "escalated"
    assert run_output("OUT-10", good, action="escalate").status == "pass"
    assert run_output("OUT-10", "Based on: income, tenure and arrears, we recommend approval.", action="escalate").status == "pass"
    assert run_output("OUT-10", "Hello, how can I help?", action="escalate").status == "pass"


# ---------------------------------------------------------------- OUT-11
def test_code_secrets():
    code = 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\npassword = "Sup3rS3cretPass!"\nx = os.environ["TOKEN"]'
    r = run_output("OUT-11", code)
    assert r.status == "modified" and "AKIA" not in r.new_text and "Sup3rS3cret" not in r.new_text and 'os.environ["TOKEN"]' in r.new_text
    assert run_output("OUT-11", 'password = os.environ["PASSWORD"]').status == "pass"
    assert run_output("OUT-11", 'password = "changeme"').status == "pass"


def test_code_private_key_blocks_and_client_data():
    assert run_output("OUT-11", "-----BEGIN RSA PRIVATE KEY-----\nabc").status == "blocked"
    r = run_output("OUT-11", "# test data: eleanor.whitcombe@example.com, Eleanor Whitcombe")
    assert r.status == "modified" and "eleanor" not in r.new_text.lower()
    assert run_output("OUT-11", "user@example.com is a placeholder").status == "pass"
