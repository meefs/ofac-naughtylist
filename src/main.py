"""CLI entrypoint for ofac-naughtylist pipeline."""

import argparse
import logging
import sys

from src.categorize import categorize_addresses, load_chain_mapping
from src.fetch import download_sdn_xml
from src.output import generate_output
from src.parse import parse_sdn_xml

SOURCES = {
    "SDN": "https://www.treasury.gov/ofac/downloads/sanctions/1.0/sdn_advanced.xml",
    "CONSOLIDATED": "https://www.treasury.gov/ofac/downloads/sanctions/1.0/cons_advanced.xml",
}


def main() -> int:
    """CLI entrypoint. Orchestrates: fetch -> parse -> categorize -> output."""
    parser = argparse.ArgumentParser(
        description="Extract and categorize OFAC-sanctioned digital currency addresses."
    )
    parser.add_argument(
        "--xml",
        type=str,
        default=None,
        help="Path to local SDN Advanced XML file (skips download).",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="SDN",
        choices=list(SOURCES.keys()),
        help="OFAC list to use (default: SDN).",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/chain_mapping.yaml",
        help="Path to chain mapping config (default: config/chain_mapping.yaml).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data",
        help="Output directory (default: data).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    try:
        # Step 1: Fetch XML
        if args.xml:
            xml_path = args.xml
            logger.info("Using local XML: %s", xml_path)
        else:
            xml_path = download_sdn_xml(source=args.source)

        # Step 2: Parse XML
        logger.info("Parsing XML...")
        raw_addresses = parse_sdn_xml(xml_path)
        logger.info("Extracted %d raw address records.", len(raw_addresses))

        # Step 3: Categorize
        logger.info("Loading chain mapping from %s...", args.config)
        chain_mapping = load_chain_mapping(args.config)
        categorized = categorize_addresses(raw_addresses, chain_mapping)

        # Step 4: Generate output
        source_xml_url = SOURCES[args.source]
        logger.info("Generating output to %s...", args.output_dir)
        generate_output(
            categorized,
            output_dir=args.output_dir,
            source_list=args.source,
            source_xml_url=source_xml_url,
        )

        # Print summary
        total = sum(len(addrs) for addrs in categorized.values())
        print(f"\nSummary: {total} addresses across {len(categorized)} chains")
        for chain, addrs in sorted(categorized.items()):
            print(f"  {chain}: {len(addrs)}")

        return 0

    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
