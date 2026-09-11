"""Shared journal metadata for the source-composition figures."""
from __future__ import annotations


# 2024 Journal Impact Factor values retained from the verified metadata used by
# the earlier journal-source artwork. Nature Sensors launched in January 2026
# and therefore has not yet been assigned a Journal Impact Factor.
JIF_2024: dict[str, float | None] = {
    "ACS Applied Materials & Interfaces": 8.2,
    "ACS Energy Letters": 19.5,
    "ACS Nano": 16.0,
    "ACS Sensors": 8.3,
    "Advanced Energy Materials": 26.0,
    "Advanced Functional Materials": 19.0,
    "Advanced Materials": 26.8,
    "Advanced Materials Technologies": 6.0,
    "Advanced Science": 14.1,
    "Biosensors and Bioelectronics": 10.5,
    "Chemical Reviews": 51.4,
    "EcoMat": 11.3,
    "Energy Storage Materials": 20.2,
    "eScience": 36.6,
    "iScience": 4.6,
    "InfoMat": 22.7,
    "Interdisciplinary Materials": 15.0,
    "Journal of the American Chemical Society": 14.4,
    "Joule": 35.4,
    "Materials Today": 24.2,
    "MRS Bulletin": 5.0,
    "Nano Energy": 17.1,
    "Nano Letters": 9.6,
    "Nano Research": 9.0,
    "Nano Today": 13.9,
    "Nature": 48.5,
    "Nature Communications": 15.7,
    "Nature Sensors": None,
    "npj Flexible Electronics": 15.5,
    "Science Advances": 12.5,
    "Science Bulletin": 18.9,
    "Small": 12.1,
    "Small Methods": 10.7,
}


# Corporate/platform publisher is used as the single flow level. This avoids
# splitting Cell Press and KeAi imprints away from Elsevier, while journals
# co-published on the Nature platform remain under Springer Nature.
PUBLISHER_BY_JOURNAL: dict[str, str] = {
    "ACS Applied Materials & Interfaces": "ACS",
    "ACS Energy Letters": "ACS",
    "ACS Nano": "ACS",
    "ACS Sensors": "ACS",
    "Chemical Reviews": "ACS",
    "Journal of the American Chemical Society": "ACS",
    "Nano Letters": "ACS",
    "Advanced Energy Materials": "Wiley",
    "Advanced Functional Materials": "Wiley",
    "Advanced Materials": "Wiley",
    "Advanced Materials Technologies": "Wiley",
    "Advanced Science": "Wiley",
    "EcoMat": "Wiley",
    "InfoMat": "Wiley",
    "Interdisciplinary Materials": "Wiley",
    "Small": "Wiley",
    "Small Methods": "Wiley",
    "Biosensors and Bioelectronics": "Elsevier",
    "Energy Storage Materials": "Elsevier",
    "eScience": "Elsevier",
    "iScience": "Elsevier",
    "Joule": "Elsevier",
    "Materials Today": "Elsevier",
    "Nano Energy": "Elsevier",
    "Nano Today": "Elsevier",
    "Science Bulletin": "Elsevier",
    "Nature": "Springer Nature",
    "Nature Communications": "Springer Nature",
    "Nature Sensors": "Springer Nature",
    "npj Flexible Electronics": "Springer Nature",
    "Nano Research": "Tsinghua UP",
    "MRS Bulletin": "Springer Nature",
    "Science Advances": "AAAS",
}


JOURNAL_ABBREVIATIONS: dict[str, str] = {
    "ACS Applied Materials & Interfaces": "ACS AMI",
    "ACS Energy Letters": "ACS Energy Lett.",
    "Advanced Energy Materials": "Adv. Energy Mater.",
    "Advanced Functional Materials": "Adv. Funct. Mater.",
    "Advanced Materials": "Adv. Mater.",
    "Advanced Materials Technologies": "Adv. Mater. Technol.",
    "Advanced Science": "Adv. Sci.",
    "Biosensors and Bioelectronics": "Biosens.",
    "Chemical Reviews": "Chem. Rev.",
    "Energy Storage Materials": "Energy Storage",
    "Interdisciplinary Materials": "Interdiscip. Mater.",
    "Journal of the American Chemical Society": "JACS",
    "Materials Today": "Mater. Today",
    "MRS Bulletin": "MRS Bull.",
    "Nano Letters": "Nano Lett.",
    "Nano Research": "Nano Res.",
    "Nature Communications": "Nat. Commun.",
    "Nature Sensors": "Nat. Sens.",
    "npj Flexible Electronics": "npj Flex. Electron.",
    "Science Advances": "Sci. Adv.",
    "Science Bulletin": "Sci. Bull.",
}


def display_journal(name: str) -> str:
    """Return the manuscript-safe abbreviated journal name."""
    return JOURNAL_ABBREVIATIONS.get(name, name)
