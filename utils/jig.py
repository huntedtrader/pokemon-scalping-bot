"""Address and profile jigging for multi-checkout bypass.

Generates slight variations of shipping/billing info so each order
looks unique to the retailer's fraud detection systems.
"""

import random
import string


# Common address line 2 prefixes
APT_PREFIXES = [
    "Apt", "APT", "Apt.", "apt", "Unit", "UNIT", "Suite", "STE",
    "Ste", "Ste.", "#", "No.", "Room", "Rm", "Floor", "Fl",
]

# Directional suffixes
DIRECTIONS = ["N", "S", "E", "W", "NE", "NW", "SE", "SW"]

# Street type variations
STREET_TYPES = {
    "Street": ["St", "St.", "STR", "Str"],
    "Avenue": ["Ave", "Ave.", "AVE", "Av"],
    "Boulevard": ["Blvd", "Blvd.", "BLVD"],
    "Drive": ["Dr", "Dr.", "DR"],
    "Lane": ["Ln", "Ln.", "LN"],
    "Road": ["Rd", "Rd.", "RD"],
    "Place": ["Pl", "Pl.", "PL"],
    "Court": ["Ct", "Ct.", "CT"],
    "Circle": ["Cir", "Cir.", "CIR"],
    "Way": ["Wy", "Wy.", "WY"],
}


def jig_address(address: dict, variation_index: int = 0) -> dict:
    """Generate a jigged variation of a shipping/billing address.

    Args:
        address: Dict with address1, address2, city, state, zip, country
        variation_index: Which variation to generate (0 = original)

    Returns:
        Modified address dict that looks different but delivers the same
    """
    if variation_index == 0:
        return address.copy()

    jigged = address.copy()

    # Jig address line 1 - swap street type abbreviation
    addr1 = jigged.get("address1", "")
    for full, abbrevs in STREET_TYPES.items():
        if full in addr1:
            jigged["address1"] = addr1.replace(full, random.choice(abbrevs))
            break
        for abbr in abbrevs:
            if abbr in addr1:
                replacements = [full] + [a for a in abbrevs if a != abbr]
                jigged["address1"] = addr1.replace(abbr, random.choice(replacements))
                break

    # Jig address line 2 - add/modify apartment number
    existing_line2 = jigged.get("address2", "").strip()
    if not existing_line2:
        prefix = random.choice(APT_PREFIXES)
        num = random.randint(1, 9999)
        jigged["address2"] = f"{prefix} {num}"
    else:
        # Swap the prefix style
        prefix = random.choice(APT_PREFIXES)
        # Extract the number part
        parts = existing_line2.split()
        if len(parts) >= 2:
            jigged["address2"] = f"{prefix} {parts[-1]}"
        else:
            jigged["address2"] = f"{prefix} {random.randint(1, 9999)}"

    return jigged


def jig_name(first_name: str, last_name: str, variation_index: int = 0) -> tuple:
    """Generate name variations that still match payment card.

    Keeps the name recognizable while adding minor differences.
    """
    if variation_index == 0:
        return first_name, last_name

    variations = [
        # Add middle initial
        lambda f, l: (f"{f} {random.choice(string.ascii_uppercase)}.", l),
        # Capitalize differently
        lambda f, l: (f.upper(), l),
        lambda f, l: (f, l.upper()),
        # Add suffix
        lambda f, l: (f, f"{l} {random.choice(['Jr', 'Jr.', 'II', 'III'])}"),
        # First initial + full last
        lambda f, l: (f"{f[0]}.", l),
    ]

    idx = (variation_index - 1) % len(variations)
    return variations[idx](first_name, last_name)


def jig_phone(phone: str, variation_index: int = 0) -> str:
    """Generate phone formatting variations.

    Same number, different formatting.
    """
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 10:
        return phone

    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]

    formats = [
        lambda d: d,                                          # 5551234567
        lambda d: f"({d[:3]}) {d[3:6]}-{d[6:]}",            # (555) 123-4567
        lambda d: f"{d[:3]}-{d[3:6]}-{d[6:]}",              # 555-123-4567
        lambda d: f"{d[:3]}.{d[3:6]}.{d[6:]}",              # 555.123.4567
        lambda d: f"1{d}",                                    # 15551234567
        lambda d: f"+1{d}",                                   # +15551234567
        lambda d: f"+1 ({d[:3]}) {d[3:6]}-{d[6:]}",         # +1 (555) 123-4567
        lambda d: f"1-{d[:3]}-{d[3:6]}-{d[6:]}",            # 1-555-123-4567
    ]

    idx = variation_index % len(formats)
    return formats[idx](digits)


def jig_email(email: str, variation_index: int = 0) -> str:
    """Generate email variations using Gmail dot trick or plus addressing.

    Gmail ignores dots in the local part and supports + aliases.
    """
    if variation_index == 0:
        return email

    local, domain = email.split("@")

    if "gmail" in domain.lower():
        # Gmail dot trick - insert dots at random positions
        if variation_index <= 5:
            chars = list(local.replace(".", ""))
            positions = random.sample(
                range(1, len(chars)), min(variation_index, len(chars) - 1)
            )
            for pos in sorted(positions, reverse=True):
                chars.insert(pos, ".")
            return f"{''.join(chars)}@{domain}"

    # Plus addressing (works with most providers)
    tag = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{local}+{tag}@{domain}"


def generate_jigged_profile(profile: dict, variation_index: int = 0) -> dict:
    """Generate a complete jigged profile for checkout.

    Args:
        profile: Full profile dict from config
        variation_index: 0 = original, 1+ = jigged variants

    Returns:
        Complete profile with jigged address, name, phone, email
    """
    jigged = profile.copy()

    first, last = jig_name(
        profile["first_name"], profile["last_name"], variation_index
    )
    jigged["first_name"] = first
    jigged["last_name"] = last

    jigged["shipping"] = jig_address(profile["shipping"], variation_index)

    if profile.get("billing", {}).get("same_as_shipping"):
        jigged["billing"] = jigged["shipping"].copy()
    else:
        jigged["billing"] = jig_address(
            profile.get("billing", profile["shipping"]), variation_index
        )

    jigged["phone"] = jig_phone(profile["phone"], variation_index)
    jigged["email"] = jig_email(profile["email"], variation_index)

    return jigged
