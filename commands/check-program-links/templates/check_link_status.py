#!/usr/bin/env python3
"""
Check HTTP status of all learn_more_link URLs in the CSV
"""

import csv
import requests
from urllib.parse import urlparse

def check_url_status(url):
    """Check the HTTP status of a URL"""
    if not url or url.strip() == '' or url == '[PLACEHOLDER]':
        return 'EMPTY'

    try:
        # Parse URL to make sure it's valid
        parsed = urlparse(url)
        if not parsed.scheme:
            return 'INVALID_URL'

        # Try HEAD request first (faster)
        response = requests.head(
            url,
            timeout=10,
            allow_redirects=True,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; LinkChecker/1.0)'}
        )

        # Some servers don't support HEAD, try GET if HEAD fails
        if response.status_code == 405 or response.status_code == 501:
            response = requests.get(
                url,
                timeout=10,
                allow_redirects=True,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; LinkChecker/1.0)'}
            )

        return f"{response.status_code}"

    except requests.exceptions.Timeout:
        return 'TIMEOUT'
    except requests.exceptions.ConnectionError:
        return 'CONNECTION_ERROR'
    except requests.exceptions.TooManyRedirects:
        return 'TOO_MANY_REDIRECTS'
    except requests.exceptions.RequestException as e:
        return f'ERROR: {str(e)[:50]}'
    except Exception as e:
        return f'EXCEPTION: {str(e)[:50]}'

def main():
    input_file = '/Users/jm/code/mfb/programs_export.csv'
    output_file = '/Users/jm/code/mfb/programs_export_with_status.csv'

    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='') as outfile:

        reader = csv.DictReader(infile)
        # Maintain column order: original columns + link_status
        fieldnames = list(reader.fieldnames) + ['link_status']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)

        writer.writeheader()

        total = 0
        checked = 0

        for row in reader:
            total += 1
            url = row['learn_more_link']

            print(f"Checking {total}: {row['name_abbreviated']} - {url[:80]}...")

            status = check_url_status(url)
            row['link_status'] = status

            print(f"  Status: {status}")

            writer.writerow(row)
            checked += 1

        print(f"\n✓ Checked {checked} programs")
        print(f"✓ Results saved to: {output_file}")

if __name__ == '__main__':
    main()
