"""Best-effort PDF paystub parser.

Extracts common paystub fields from a PDF file object using pdfplumber.
Designed around one specific SAP paystub format but tolerates other layouts.

Returns a dict with field names matching Paystub model columns plus:
  _warnings: list of unrecognized lines that contained dollar amounts
On any failure, returns an empty dict with a _warnings entry.
"""
import re

try:
    import pdfplumber
    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    _PDFPLUMBER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

# Matches a positive dollar amount like "7,091.15" or "448.57-" (negative = withholding)
_AMOUNT_RE = re.compile(r"[\d,]+\.\d{2}-?")


def _clean_amount(s: str) -> float:
    """Parse a paystub amount string to a positive float (negatives are withholdings)."""
    s = s.strip().replace(",", "").rstrip("-")
    try:
        return abs(float(s))
    except ValueError:
        return 0.0


def _first_amount(text: str) -> float | None:
    """Return the first dollar amount found in text, or None."""
    m = _AMOUNT_RE.search(text)
    return _clean_amount(m.group()) if m else None


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"(\d{2}/\d{2}/\d{4})")


def _parse_date(text: str) -> str | None:
    """Extract a date in MM/DD/YYYY format and return as ISO YYYY-MM-DD."""
    m = _DATE_RE.search(text)
    if not m:
        return None
    mo, d, y = m.group().split("/")
    return f"{y}-{mo}-{d}"


# ---------------------------------------------------------------------------
# Line-label matchers
# (each yields (field_name, value) or None)
# ---------------------------------------------------------------------------

def _match_line(line: str) -> tuple[str, float] | None:
    """Try to match a paystub line to a known field.  Returns (field, value) or None."""
    l = line.strip()
    upper = l.upper()

    # Amount extraction: look for the first standalone amount in the current-period column.
    # On SAP paystubs the current-period amount comes before YTD, so we take the first.
    amt = _first_amount(l)
    if amt is None:
        return None

    # ----- Earnings -----
    if re.search(r"\bGROSS\s+PAY\b", upper):
        return ("gross_pay", amt)

    # ----- Federal withholdings -----
    # "Withholding Tax" appears twice: first = federal, second = CA.
    # Caller handles ordering via state machine.
    if re.search(r"\bWITHHOLDING\s+TAX\b", upper):
        return ("_withholding_tax", amt)  # caller resolves fed vs CA

    if re.search(r"\bSOCIAL\s+SECURITY\b", upper) or re.search(r"EE\s+SOCIAL\s+SECURITY", upper):
        return ("ss_withholding", amt)

    if re.search(r"\bMEDICARE\b", upper) and "ADDITIONAL" not in upper:
        return ("medicare_withholding", amt)

    # ----- CA withholdings -----
    if re.search(r"\bDISABILITY\s+TAX\b", upper) or re.search(r"EE\s+DISABILITY", upper):
        return ("state_disability_withholding", amt)

    # ----- Pre-tax benefits -----
    if re.search(r"\bMEDICAL\s+(?:PLAN|INS)", upper):
        return ("medical_insurance", amt)

    if re.search(r"\bDENTAL\s+(?:PLAN|INS)", upper):
        return ("dental_insurance", amt)

    if re.search(r"\bVISION\s+(?:PLAN|INS)", upper):
        return ("vision_insurance", amt)

    # 401(k) pre-tax: SRP Before-Tax, 401(k) Pre-Tax, Before-Tax 401k, etc.
    if re.search(r"BEFORE[\s-]TAX", upper) or re.search(r"PRE[\s-]TAX\s+401", upper):
        return ("pretax_401k", amt)

    # Roth 401(k)
    if re.search(r"ROTH", upper) and re.search(r"401", upper):
        return ("roth_401k", amt)

    if re.search(r"\bDEP(?:ENDENT)?\s+CARE\s+FSA\b", upper) or re.search(r"DEP\s+CARE\s+FSA", upper):
        return ("dependent_care_fsa", amt)

    if re.search(r"\bHEALTH(?:CARE)?\s+FSA\b", upper):
        return ("healthcare_fsa", amt)

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_paystub_pdf(file_obj) -> dict:
    """Parse a paystub PDF and return a dict of field values.

    Always returns a dict; on failure returns {"_warnings": [error_str]}.
    Unknown lines with amounts are collected in "_warnings".
    """
    if not _PDFPLUMBER_AVAILABLE:
        return {"_warnings": ["pdfplumber is not installed — PDF import unavailable."]}

    result: dict = {"_warnings": []}

    try:
        with pdfplumber.open(file_obj) as pdf:
            text_lines = []
            for page in pdf.pages:
                raw = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                text_lines.extend(raw.splitlines())
    except Exception as exc:
        return {"_warnings": [f"Could not read PDF: {exc}"]}

    # ---- Date extraction ----
    for line in text_lines:
        l = line.strip()
        if re.search(r"PERIOD\s+BEGINNING", l, re.I):
            d = _parse_date(l)
            if d:
                result["pay_period_start"] = d
        elif re.search(r"PERIOD\s+ENDING", l, re.I):
            d = _parse_date(l)
            if d:
                result["pay_period_end"] = d
        elif re.search(r"CHECK\s+DATE", l, re.I):
            d = _parse_date(l)
            if d:
                result["pay_date"] = d

    # ---- Field extraction ----
    # "Withholding Tax" appears for federal first, then CA. Track which we've seen.
    withholding_count = 0

    for line in text_lines:
        l = line.strip()
        upper = l.upper()

        # Skip header / footer noise
        if not l or re.match(r"^[-=\s*]+$", l):
            continue

        # Handle "Withholding Tax" state machine
        if re.search(r"\bWITHHOLDING\s+TAX\b", upper):
            amt = _first_amount(l)
            if amt is not None:
                if withholding_count == 0:
                    result["federal_income_withholding"] = amt
                elif withholding_count == 1:
                    result["state_income_withholding"] = amt
                withholding_count += 1
            continue

        match = _match_line(l)
        if match:
            field, val = match
            if field != "_withholding_tax":
                result[field] = val
        else:
            # If the line has a dollar amount but we didn't recognise it, warn
            if _AMOUNT_RE.search(l):
                # Skip noisy lines (YTD totals, totals, net pay, etc.)
                skip_patterns = [
                    r"TOTAL", r"NET PAY", r"GROSS", r"DIRECT DEPOSIT", r"DEPOSITED",
                    r"CHECK DATE", r"PERIOD", r"PERS\.", r"COST CENTER", r"BANK",
                    r"PAYMENT METHOD", r"QUOTA", r"EARNED", r"USED", r"BALANCE",
                    r"STI GLOBAL", r"REGULAR PAY", r"MATCHING", r"RETIREMENT",
                    r"IMPUTED", r"HOURS", r"TAXABLE WAGES",
                ]
                if not any(re.search(p, upper) for p in skip_patterns):
                    result["_warnings"].append(l)
                    label = _AMOUNT_RE.split(l)[0].strip()
                    if label:
                        result.setdefault("_extras", []).append(
                            {"label": label, "amount": _first_amount(l)}
                        )

    result["_from_pdf"] = True
    return result
