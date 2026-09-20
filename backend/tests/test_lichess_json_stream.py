# tests/test_lichess_json_stream.py

from app.lichess.pgn_parser import ChessStateTracker, GameMetadata, ParsedMoveEvent

SAMPLE_STREAM = [
    '{"id":"kSc2w4MX","variant":{"key":"standard","name":"Standard","short":"Std"},"speed":"rapid","perf":"rapid","rated":true,"source":"pool","createdAt":1789536484065,"players":{"white":{"user":{"name":"pagnola","id":"pagnola"},"rating":2168},"black":{"user":{"name":"Amrullahm","id":"amrullahm"},"rating":2130}}}',
    '{"fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1","wc":600,"bc":600}',
    '{"fen":"rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1","lm":"e2e4","wc":600,"bc":600}',
    '{"fen":"rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2","lm":"e7e5","wc":600,"bc":600}',
    '{"fen":"rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2","lm":"g1f3","wc":598,"bc":600}',
    '{"fen":"r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3","lm":"b8c6","wc":598,"bc":598}',
    '{"fen":"r1bqkbnr/pppp1ppp/2n5/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R b KQkq - 3 3","lm":"b1c3","wc":595,"bc":598}',
    '{"fen":"r1bqkbnr/1ppp1ppp/p1n5/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 0 4","lm":"a7a6","wc":595,"bc":595}',
]


def test_live_stream_ingestion():
    tracker = ChessStateTracker(time_trouble_threshold_seconds=30.0)

    # Line 1: Metadata
    meta = tracker.parse_lichess_line(SAMPLE_STREAM[0])
    assert isinstance(meta, GameMetadata)
    assert meta.white_player.username == "pagnola"
    assert meta.black_player.rating == 2130

    # Line 2: Initial Setup
    baseline = tracker.parse_lichess_line(SAMPLE_STREAM[1])
    assert baseline is None
    assert tracker.last_white_clock == 600.0
    assert tracker.last_black_clock == 600.0

    # Line 3: 1. e4
    e4_event = tracker.parse_lichess_line(SAMPLE_STREAM[2])
    assert isinstance(e4_event, ParsedMoveEvent)
    assert e4_event.san == "e4"
    assert e4_event.ply == 1
    assert e4_event.move_time_spent_seconds == 0.0

    # Line 5: 2. Nf3 (White spent 2s: 600 -> 598)
    tracker.parse_lichess_line(SAMPLE_STREAM[3])  # 1... e5
    nf3_event = tracker.parse_lichess_line(SAMPLE_STREAM[4])
    assert nf3_event.san == "Nf3"
    assert nf3_event.move_time_spent_seconds == 2.0
    assert not nf3_event.is_time_trouble

    # Line 7: 3. Nc3 (White spent 3s: 598 -> 595)
    tracker.parse_lichess_line(SAMPLE_STREAM[5])  # 2... Nc6
    nc3_event = tracker.parse_lichess_line(SAMPLE_STREAM[6])
    assert nc3_event.san == "Nc3"
    assert nc3_event.move_time_spent_seconds == 3.0