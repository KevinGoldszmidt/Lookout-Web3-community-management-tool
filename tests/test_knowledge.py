from lookout.knowledge import chunk_text

def test_chunk_text_splits():
    text = "alpha beta gamma " * 500
    chunks = chunk_text(text, target=500, overlap=50)
    assert len(chunks) > 2
    assert all(chunks)
