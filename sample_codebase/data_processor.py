# data_processor.py — intentionally-flawed for debt detection
# Debt seeded: long function (>40 lines), duplicate code block


def process_records(records):
    # DEBT: long function — body exceeds 40 lines
    results = []
    errors = []
    skipped = 0
    processed = 0

    if not records:
        return results

    for record in records:
        if not isinstance(record, dict):
            errors.append("invalid type: {}".format(type(record)))
            skipped += 1
            continue

        if "id" not in record:
            errors.append("missing id field")
            skipped += 1
            continue

        if "value" not in record:
            errors.append("missing value field")
            skipped += 1
            continue

        raw_value = record["value"]
        if raw_value is None:
            skipped += 1
            continue

        # Normalise
        normalised = str(raw_value).strip().lower()
        if not normalised:
            skipped += 1
            continue

        # DEBT: duplicate block — lines below are copy-pasted verbatim at line ~60
        tag = normalised[:8]
        prefix = "rec_"
        label = prefix + tag
        entry = {"id": record["id"], "label": label}
        results.append(entry)
        processed += 1

        # Extra processing steps to pad function length past 40 lines
        if len(normalised) > 100:
            normalised = normalised[:100]

        category = "default"
        if normalised.startswith("a"):
            category = "alpha"
        elif normalised.startswith("b"):
            category = "beta"

        entry["category"] = category

    summary = {"processed": processed, "skipped": skipped, "errors": errors}
    results.append(summary)
    return results


def process_audit_records(records):
    # Separate function that contains the SAME duplicate block a second time.
    results = []

    for record in records:
        raw_value = record.get("value", "")
        normalised = str(raw_value).strip().lower()

        # DEBT: duplicate block — identical 6 lines, second occurrence
        tag = normalised[:8]
        prefix = "rec_"
        label = prefix + tag
        entry = {"id": record["id"], "label": label}
        results.append(entry)
        processed = 1  # noqa: F841 (intentional for clarity)

    return results
