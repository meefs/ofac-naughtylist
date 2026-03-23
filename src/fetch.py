"""Download the SDN Advanced XML file from OFAC."""

import logging
import time

import requests

logger = logging.getLogger(__name__)

URLS = {
    "SDN": "https://www.treasury.gov/ofac/downloads/sanctions/1.0/sdn_advanced.xml",
    "CONSOLIDATED": "https://www.treasury.gov/ofac/downloads/sanctions/1.0/cons_advanced.xml",
}

USER_AGENT = "ofac-naughtylist/1.0 (https://github.com/cylon56/ofac-naughtylist)"


def download_sdn_xml(
    output_path: str = "./sdn_advanced.xml",
    source: str = "SDN",
) -> str:
    """
    Download the SDN (or Consolidated) Advanced XML file from OFAC.

    Args:
        output_path: Local path to save the downloaded XML.
        source: "SDN" or "CONSOLIDATED".

    Returns:
        Path to the downloaded file.

    Raises:
        requests.HTTPError: If the download fails after retries.
        ValueError: If source is not recognized.
    """
    if source not in URLS:
        raise ValueError(f"Unknown source: {source}. Must be one of: {list(URLS.keys())}")

    url = URLS[source]
    headers = {"User-Agent": USER_AGENT}

    max_retries = 3
    backoff_seconds = 2

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Downloading %s XML (attempt %d/%d)...", source, attempt, max_retries)
            response = requests.get(url, headers=headers, stream=True, timeout=120)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info("Downloaded %s to %s", source, output_path)
            return output_path

        except (requests.RequestException, TimeoutError) as e:
            if attempt == max_retries:
                logger.error("Failed to download after %d attempts: %s", max_retries, e)
                raise
            wait = backoff_seconds * (2 ** (attempt - 1))
            logger.warning("Download attempt %d failed: %s. Retrying in %ds...", attempt, e, wait)
            time.sleep(wait)

    # Should not reach here, but satisfy type checker
    raise RuntimeError("Download failed")
