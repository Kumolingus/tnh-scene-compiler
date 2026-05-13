init python:

    def Alpha_default_Outfits() -> list:
        Outfits = []

        Outfits.append(
            OutfitClass(
                Alpha,
                "Casual 1",
                flags = {"public", "fall"},
            ),
        )

        Outfits.append(
            OutfitClass(
                Alpha,
                "Hero",
                flags = {"public", "combat"},
            ),
        )

        # Duplicate name — should be deduplicated.
        Outfits.append(OutfitClass(Alpha, "Casual 1"))

        return Outfits
