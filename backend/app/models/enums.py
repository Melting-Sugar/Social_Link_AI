from enum import StrEnum


class Scene(StrEnum):
    """§11.1 A-② — the 5 fixed scene presets."""

    SCHOOL_UNIVERSITY = "school_university"
    WORKPLACE = "workplace"
    FIRST_MEETING = "first_meeting"
    FRIEND = "friend"
    ROMANTIC = "romantic"


class RelationshipDistance(StrEnum):
    """§11.9 — 5-stage relationship-distance indicator (draft wording,
    §10 残る未決事項 #4 — final copy/icons still open)."""

    DISTANT = "distant"
    NO_CHANGE = "no_change"
    WARMING_UP = "warming_up"
    GETTING_CLOSER = "getting_closer"
    OPENING_UP = "opening_up"


class SuggestionCategory(StrEnum):
    """§11.9 — "次に話すと良いこと" categories (draft, §10 残る未決事項 #4)."""

    ASK_QUESTION = "ask_question"
    SHOW_EMPATHY = "show_empathy"
    TALK_ABOUT_SELF = "talk_about_self"
    CHANGE_TOPIC = "change_topic"
    JUST_LISTEN = "just_listen"


class Condition(StrEnum):
    """§11.1 A-⑥ — 4-stage condition indicator. Exact wording/icons were
    never pinned down in the requirements doc (only relationship-distance
    and suggestion-category were flagged as open in §10); these are a
    reasonable placeholder pending the same kind of confirmation."""

    VERY_GOOD = "very_good"
    GOOD = "good"
    TIRED = "tired"
    UNWELL = "unwell"
