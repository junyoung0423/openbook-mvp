from openbook.safety import BANNED_TERMS, find_banned, is_clean


def test_each_banned_term_is_caught():
    for t in BANNED_TERMS:
        assert not is_clean(f"이 조항은 {t}합니다.")


def test_neutral_sentence_passes():
    assert is_clean("계약기간이 표준은 3년, 계약서는 7년입니다.")


def test_find_banned_lists_all_hits():
    assert find_banned("부당하고 불리한 조항") == ["부당", "불리"]
