"""Excel export helpers: build export data from STRUCTURED rows and neutralize
spreadsheet formula injection in user-controlled text.

``neutralize_formula`` is stdlib-only and always usable. ``children_to_dataframe``
imports pandas lazily, so importing this module costs no third-party
dependency. The DataFrame is always built from the structured database rows
held by the application, never from the GUI Treeview's stringified value cache
(which turned every column, including the numeric id, into text).
"""

EXPORT_COLUMNS = ["ID", "ФИО", "Группа"]

# A leading one of these characters makes Excel/LibreOffice parse the cell as
# a formula rather than text (CSV/Excel formula injection).
FORMULA_PREFIXES = ("=", "+", "-", "@")


def neutralize_formula(value):
    """Return ``value`` so spreadsheet applications treat it as text.

    Strings starting with a formula trigger character get a leading apostrophe,
    which Excel and openpyxl interpret as an explicit "this is text" marker, so
    the cell is stored and displayed as text instead of being evaluated.
    Non-strings and ordinary strings are returned unchanged.
    """
    if isinstance(value, str) and value[:1] in FORMULA_PREFIXES:
        return "'" + value
    return value


def children_to_dataframe(rows):
    """Build the children export DataFrame from structured summary rows.

    The ID column stays NUMERIC (int) and the child/group text columns stay
    text and can never be parsed as spreadsheet formulas. Missing group
    memberships export as an empty string rather than a stringified None.
    """
    import pandas as pd

    records = [
        {
            "ID": int(r["id"]),
            "ФИО": neutralize_formula(r["full_name"] or ""),
            "Группа": neutralize_formula(r["group_name"] or ""),
        }
        for r in rows
    ]
    return pd.DataFrame(records, columns=EXPORT_COLUMNS)
