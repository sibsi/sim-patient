"""Validate and render a minimal Big Five induction in a fixed trait order."""
TRAITS = ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism")


def render_profile(profile):
    if not isinstance(profile, dict) or set(profile) != {"name", "traits"}:
        raise ValueError("A persona profile requires exactly name and traits")
    if not isinstance(profile["name"], str) or not profile["name"].strip():
        raise ValueError("Persona profile name must be nonempty")
    traits = profile["traits"]
    if not isinstance(traits, dict) or set(traits) != set(TRAITS):
        raise ValueError("Persona profile must contain all five Big Five traits")
    if any(value not in ("low", "moderate", "high") for value in traits.values()):
        raise ValueError("Trait levels must be low, moderate, or high")
    return "Your Big Five personality:\n" + "\n".join(
        f"{trait.capitalize()}: {traits[trait]}" for trait in TRAITS
    )
