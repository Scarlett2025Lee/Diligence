"""Cell agent: answers ONE question over ONE document, with citations.

This is the atomic unit of the Matrix. Contract:
    answer_cell(doc_id, question) -> CellResult(answer, citations[], cost, latency)
Citations must point to chunk ids + char offsets — defensibility is the product.
TODO(phase-1): retrieve -> prompt -> parse structured output (Pydantic).
"""
