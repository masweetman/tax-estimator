"""Service layer for per-year tax rate settings.

Loads TaxYearSettings from the DB and returns a dict of override keys that
the calculator's inputs dict understands.  Any null field means "use
constants.py default" — the calculator already handles that via ``or`` fallback.
"""
import json
from app.models import TaxYearSettings


def _parse_brackets(json_str):
    """Parse a JSON bracket string into a list of (rate, upper) tuples."""
    if not json_str:
        return None
    try:
        rows = json.loads(json_str)
        return [(float(r["rate"]), float(r["upper"]) if r.get("upper") is not None else None)
                for r in rows]
    except (ValueError, KeyError, TypeError):
        return None


def get_settings_inputs(ty) -> dict:
    """Return a dict of calculator input overrides for the given TaxYear.

    Returns an empty dict if no settings row exists or all values are null.
    The returned keys match what federal.py / california.py check via
    ``inputs.get(key)``.
    """
    s = ty.settings
    if s is None:
        return {}

    overrides = {}

    def _add(key, val):
        if val is not None:
            overrides[key] = float(val)

    # Federal scalars
    _add("federal_standard_deduction", s.federal_standard_deduction)
    _add("ss_wage_base", s.ss_wage_base)
    _add("salt_cap", s.salt_cap)
    _add("child_tax_credit", s.child_tax_credit)
    _add("ctc_phase_out_start", s.ctc_phase_out_start)
    _add("niit_rate", s.niit_rate)
    _add("niit_threshold", s.niit_threshold)
    _add("additional_medicare_rate", s.additional_medicare_rate)
    _add("additional_medicare_threshold", s.additional_medicare_threshold)
    _add("irs_mileage_rate", s.irs_mileage_rate)

    # CA scalars
    _add("ca_standard_deduction", s.ca_standard_deduction)
    _add("ca_sdi_rate", s.ca_sdi_rate)
    _add("ca_mental_health_surtax_rate", s.ca_mental_health_surtax_rate)
    _add("ca_mental_health_surtax_threshold", s.ca_mental_health_surtax_threshold)
    _add("ca_personal_exemption", s.ca_personal_exemption)
    _add("ca_dependent_credit", s.ca_dependent_credit)
    _add("ca_young_child_credit", s.ca_young_child_credit)
    if s.qualifying_children_under_6 is not None:
        overrides["qualifying_children_under_6"] = int(s.qualifying_children_under_6)

    # Bracket arrays
    fed_brackets = _parse_brackets(s.federal_brackets_json)
    if fed_brackets:
        overrides["federal_brackets"] = fed_brackets

    ltcg_brackets = _parse_brackets(s.ltcg_brackets_json)
    if ltcg_brackets:
        overrides["ltcg_brackets"] = ltcg_brackets

    ca_brackets = _parse_brackets(s.ca_brackets_json)
    if ca_brackets:
        overrides["ca_brackets"] = ca_brackets

    return overrides
