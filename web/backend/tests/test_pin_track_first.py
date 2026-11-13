from web.backend.routers.player import pin_track_first


def test_clicked_track_missing_from_sample_is_inserted_first():
    assert pin_track_first([3, 1, 2], 9, window_size=3) == [9, 3, 1]


def test_clicked_track_mid_queue_moves_to_front():
    assert pin_track_first([3, 9, 1, 2], 9, window_size=10) == [9, 3, 1, 2]


def test_already_first_is_unchanged():
    assert pin_track_first([9, 3, 1], 9, window_size=10) == [9, 3, 1]
