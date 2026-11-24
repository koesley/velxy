"""Shared deterministic demo guidance; no external services."""

def recommend(accepted, rejected, *, channel='web'):
    """Choose the next action from report counts, retaining channel copy."""
    if any(type(count) is not int or count < 0 for count in (accepted, rejected)):
        return 'Report counts are invalid. Regenerate the report before drawing business conclusions.'
    if rejected:
        guidance = ('Review flagged records before relying on sales totals. Correct the source records and rerun the report.'
                if channel == 'email' else
                'Review flagged rows before relying on the sales totals. Correct the source records and rerun the report.')
        if not accepted:
            return guidance + ' No rows passed validation; resolve the flagged records before using the report.'
        if rejected >= accepted:
            return guidance + ' At least half of the rows were flagged; prioritize correcting the source data.'
        return guidance + ' Some rows passed validation, but flagged rows may make the totals incomplete.'
    if accepted:
        return ('Compare monthly and product summaries for changes worth investigating. Validation does not verify every sale.'
                if channel == 'email' else
                'Compare monthly and product summaries to identify changes worth investigating. Accepted rows passed validation; this does not verify every sale.')
    return ('Upload sales records before drawing business conclusions.'
            if channel == 'email' else
            'Upload a CSV containing sales records before drawing business conclusions.')
