init python:
    # -- Trait fixtures -------------------------------------------------------
    def setup_default_traits():
        Alpha.give_trait("shy")
        Alpha.give_trait("romantic")
        Beta.check_trait("brave")
        Alpha.remove_trait("cowardly")

    # # Commented-out trait — should be ignored.
    # Alpha.give_trait("commented_out_trait")

    """
    Alpha.give_trait("inside_docstring_trait")
    """

    # -- Personality fixtures -------------------------------------------------
    def check_moods():
        if Alpha.check_personality("bold"):
            pass
        if Beta.check_personality("sarcastic", 3):
            pass

    # # Alpha.check_personality("commented_personality")

    """
    Alpha.check_personality("docstring_personality")
    """

    # -- History event fixtures -----------------------------------------------
    def track_events():
        Alpha.History.check("kissed_player")
        Alpha.History.add("fought_villain")
        Beta.History.record("visited_library")

    # # Alpha.History.check("commented_event")

    """
    Alpha.History.check("docstring_event")
    """
