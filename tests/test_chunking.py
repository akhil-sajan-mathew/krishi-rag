from app.ingest import chunk_pages, clean_pages


def test_repeated_header_and_footer_removed():
    crops = ["rice", "wheat", "cotton", "tomato", "banana", "maize"]
    pages = [f"KAU Package of Practices\nNotes on {c}.\nPage {i}" for i, c in enumerate(crops, 1)]
    cleaned = clean_pages(pages)
    assert cleaned == [f"Notes on {c}." for c in crops]


def test_hyphenated_line_break_rejoined():
    assert clean_pages(["Apply fertil-\nizer at sowing."]) == ["Apply fertilizer at sowing."]
    assert clean_pages(["Sow in September-\nDecember."]) == ["Sow in September-\nDecember."]


def test_non_english_chunks_skipped():
    chunks = chunk_pages(["किसान सम्मान निधि योजना के लिए पात्रता", "Seed rate: 3 kg/ha."], 128, 16)
    assert [c.page for c in chunks] == [2]


def test_chunks_keep_page_numbers_and_respect_size():
    long_page = " ".join(f"Sentence number {i} about seed rate." for i in range(300))
    chunks = chunk_pages(["", long_page, "Short page three."], size=128, overlap=16)
    assert {c.page for c in chunks} == {2, 3}  # empty page 1 yields nothing
    assert all(c.text and c.token_count <= 128 for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))
