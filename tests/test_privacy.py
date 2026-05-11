from pathlib import Path

from src.privacy import load_privacy_config, mask_pii


CONFIG_PATH = Path("config/privacy_rules.yml")


def test_load_privacy_config_reads_rules_and_policy() -> None:
    config = load_privacy_config(CONFIG_PATH)

    assert config.version == "privacy_rules.2026-05-11"
    assert [rule.pii_type for rule in config.masking_rules] == [
        "email",
        "phone",
        "rrn_like",
        "order_id",
        "person",
    ]
    assert config.policy["person_masking"] == "enabled"


def test_disabled_privacy_rules_are_skipped(tmp_path: Path) -> None:
    config_path = tmp_path / "privacy.yml"
    config_path.write_text(
        """
version: "privacy_rules.test"
masking:
  person:
    enabled: false
    pattern: "김대리"
    replacement: "[PERSON]"
policy: {}
""".strip(),
        encoding="utf-8",
    )

    config = load_privacy_config(config_path)
    result = mask_pii("김대리님 확인 부탁드립니다.", config)

    assert config.masking_rules == ()
    assert result.pii_detected is False
    assert result.masked_text == "김대리님 확인 부탁드립니다."


def test_mask_pii_returns_detected_types_and_masked_text() -> None:
    config = load_privacy_config(CONFIG_PATH)

    result = mask_pii(
        (
            "김대리님 test@example.com 으로 연락했고 "
            "010-1234-5678, 주문번호 ORD-12345, 식별값 900101-1234567 입니다."
        ),
        config,
    )

    assert result.pii_detected is True
    assert result.pii_types == ["email", "phone", "rrn_like", "order_id", "person"]
    assert result.masked_text == (
        "[PERSON] [EMAIL] 으로 연락했고 "
        "[PHONE], 주문번호 [ORDER_ID], 식별값 [ID_NUMBER] 입니다."
    )


def test_person_masking_does_not_mask_generic_customer_phrase() -> None:
    config = load_privacy_config(CONFIG_PATH)

    result = mask_pii("고객님 문의는 CS에서 확인합니다. 김대리님 확인 부탁드립니다.", config)

    assert result.pii_detected is True
    assert result.pii_types == ["person"]
    assert result.masked_text == "고객님 문의는 CS에서 확인합니다. [PERSON] 확인 부탁드립니다."


def test_mask_pii_leaves_text_unchanged_when_no_pattern_matches() -> None:
    config = load_privacy_config(CONFIG_PATH)

    result = mask_pii("A 고객사 결제 오류가 발생했습니다.", config)

    assert result.pii_detected is False
    assert result.pii_types == []
    assert result.masked_text == "A 고객사 결제 오류가 발생했습니다."
