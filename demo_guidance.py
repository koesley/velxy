"""Shared deterministic demo guidance; no external services."""

def recommend(accepted, rejected, *, channel='web'):
    """Choose the next action from report counts, retaining channel copy."""
    if rejected:
        return ('Review flagged records before relying on sales totals. Correct the source records and rerun the report.'
                if channel == 'email' else
                'Review flagged rows before relying on the sales totals. Correct the source records and rerun the report.')
    if accepted:
        return ('Compare monthly and product summaries for changes worth investigating. Validation does not verify every sale.'
                if channel == 'email' else
                'Compare monthly and product summaries to identify changes worth investigating. Accepted rows passed validation; this does not verify every sale.')
    return ('Upload sales records before drawing business conclusions.'
            if channel == 'email' else
            'Upload a CSV containing sales records before drawing business conclusions.')
