# utils.py — intentionally-flawed for debt detection
# Debt seeded: two unused imports, one unused variable

# DEBT: unused imports — neither 'os' nor 'json' is referenced below
import os
import json

import re


def format_name(first, last):
    # DEBT: unused variable — 'separator' is assigned but never read
    separator = "---"
    full = first.strip() + " " + last.strip()
    return re.sub(r"\s+", " ", full)


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
