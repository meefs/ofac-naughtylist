"""Parse the SDN Advanced XML and extract all digital currency addresses."""

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SanctionedAddress:
    address: str
    ofac_ticker: str
    entity_id: int
    entity_name: str
    programs: list[str]
    date_listed: str
    feature_id: int


def get_namespace(root: ET.Element) -> dict[str, str]:
    """Extract namespace from root element tag."""
    match = re.match(r'\{(.+?)\}', root.tag)
    return {'ns': match.group(1)} if match else {}


def _extract_entity_name(identity_elem: ET.Element, ns: dict[str, str]) -> str:
    """Extract the primary entity name from an Identity element."""
    prefix = f"{{{ns['ns']}}}" if ns else ""

    for alias in identity_elem.findall(f"{prefix}Alias"):
        if alias.get("Primary", "").lower() != "true":
            continue
        for doc_name in alias.findall(f"{prefix}DocumentedName"):
            parts = []
            for doc_name_part in doc_name.findall(f"{prefix}DocumentedNamePart"):
                for name_part_val in doc_name_part.findall(f"{prefix}NamePartValue"):
                    if name_part_val.text:
                        parts.append(name_part_val.text.strip())
            if parts:
                return " ".join(parts)
    return "UNKNOWN"


def parse_sdn_xml(xml_path: str) -> list[SanctionedAddress]:
    """
    Parse the SDN Advanced XML file and extract all digital currency addresses.

    Uses iterparse for memory efficiency on large (~80MB) files.

    Args:
        xml_path: Path to the downloaded sdn_advanced.xml file.

    Returns:
        List of SanctionedAddress objects.
    """
    results: list[SanctionedAddress] = []
    known_tickers = set()

    # First pass: detect namespace from root element
    ns = {}
    for event, elem in ET.iterparse(xml_path, events=("start",)):
        ns = get_namespace(elem)
        break

    prefix = f"{{{ns['ns']}}}" if ns else ""

    # Full parse using iterparse, processing DistinctParty elements
    tree = ET.iterparse(xml_path, events=("end",))

    for event, elem in tree:
        if elem.tag != f"{prefix}DistinctParty":
            continue

        entity_id = int(elem.get("FixedRef", "0"))

        # Extract entity name from Profile > Identity
        entity_name = "UNKNOWN"
        profile = elem.find(f"{prefix}Profile")
        if profile is not None:
            identity = profile.find(f"{prefix}Identity")
            if identity is not None:
                entity_name = _extract_entity_name(identity, ns)

        # Extract programs
        programs = []
        for sp in elem.findall(f"{prefix}SanctionsProgram"):
            spv = sp.find(f"{prefix}SanctionsProgramValue")
            if spv is not None and spv.text:
                programs.append(spv.text.strip())

        # Extract date listed from DateOfRecord
        date_listed = ""
        date_elem = elem.find(f"{prefix}DateOfRecord")
        if date_elem is not None:
            day = date_elem.get("Day", "01")
            month = date_elem.get("Month", "01")
            year = date_elem.get("Year", "1970")
            date_listed = f"{year}-{int(month):02d}-{int(day):02d}"

        # Extract digital currency address features
        if profile is not None:
            for feature in profile.findall(f"{prefix}Feature"):
                feature_id = int(feature.get("ID", "0"))

                for fv in feature.findall(f"{prefix}FeatureVersion"):
                    # Get the comment which contains the ticker info
                    comment_elem = fv.find(f"{prefix}Comment")
                    if comment_elem is None or not comment_elem.text:
                        continue

                    comment = comment_elem.text.strip()
                    if not comment.startswith("Digital Currency Address - "):
                        continue

                    ticker = comment.split(" - ", 1)[1].strip()

                    # Log warning for unknown tickers
                    if ticker not in known_tickers:
                        known_tickers.add(ticker)
                        logger.info("Discovered ticker: %s", ticker)

                    # Extract address from VersionDetail > DetailReferenceValue
                    address = ""
                    for vd in fv.findall(f"{prefix}VersionDetail"):
                        drv = vd.find(f"{prefix}DetailReferenceValue")
                        if drv is not None and drv.text:
                            address = drv.text.strip()
                            break

                    if not address:
                        logger.warning(
                            "Empty address for feature %d on entity %d (%s)",
                            feature_id, entity_id, entity_name
                        )
                        continue

                    results.append(SanctionedAddress(
                        address=address,
                        ofac_ticker=ticker,
                        entity_id=entity_id,
                        entity_name=entity_name,
                        programs=programs,
                        date_listed=date_listed,
                        feature_id=feature_id,
                    ))

        # Free memory
        elem.clear()

    return results
