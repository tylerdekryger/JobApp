from app.discovery.source_detection import detect_source


def test_detects_greenhouse_board_url():
    detected = detect_source("https://boards.greenhouse.io/acme")
    assert detected is not None
    assert detected.provider == "greenhouse"
    assert detected.source_identifier == "acme"


def test_detects_job_boards_greenhouse_host():
    detected = detect_source("https://job-boards.greenhouse.io/acme")
    assert detected is not None
    assert detected.source_identifier == "acme"


def test_ignores_path_after_board_token():
    detected = detect_source("https://boards.greenhouse.io/acme/jobs/12345")
    assert detected is not None
    assert detected.source_identifier == "acme"


def test_detects_ashby_board_url():
    detected = detect_source("https://jobs.ashbyhq.com/linear")
    assert detected is not None
    assert detected.provider == "ashby"
    assert detected.source_identifier == "linear"


def test_detects_lever_board_url():
    detected = detect_source("https://jobs.lever.co/palantir")
    assert detected is not None
    assert detected.provider == "lever"
    assert detected.source_identifier == "palantir"


def test_returns_none_for_non_ats_url():
    assert detect_source("https://acme.com/careers") is None
    assert detect_source("https://jobs.workday.com/acme") is None
