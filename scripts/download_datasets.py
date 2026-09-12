"""Explicit, resumable public dataset downloads. No automatic extraction or training."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

SOURCES = {
    'care': ('https://zenodo.org/api/records/15846963/files/CARE_To_Compare.zip/content', 'CARE_To_Compare.zip', '2547b58c21ac8c242d13232860cf500c'),
    'ir': ('https://raw.githubusercontent.com/RaptorMaps/InfraredSolarModules/master/2020-02-14_InfraredSolarModules.zip', 'InfraredSolarModules.zip', None),
    'solar': ('https://www.kaggle.com/api/v1/datasets/download/anikannal/solar-power-generation-data', 'solar-power-generation-data.zip', None),
}


def digest(path, kind):
    result = hashlib.new(kind)
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''): result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', choices=SOURCES)
    args = parser.parse_args()
    url, name, expected = SOURCES[args.dataset]
    raw = Path(__file__).resolve().parents[1] / 'data/raw'
    raw.mkdir(parents=True, exist_ok=True)
    destination, partial = raw / name, raw / (name + '.part')
    if not destination.exists():
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {'User-Agent': 'UrjaKavach-dataset-download/1.0'}
        if offset: headers['Range'] = f'bytes={offset}-'
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=60) as response:
            if offset and response.status != 206:
                raise SystemExit('The server did not honor resume. Partial data retained; explicitly remove the .part file to restart.')
            if offset and not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
                raise SystemExit('Unexpected resume range. Partial data retained.')
            if 'text/html' in response.headers.get('Content-Type', ''):
                raise SystemExit('Provider returned a web page, not an archive. Check account/download requirements.')
            total = offset
            announced = total // (128 * 1024 * 1024)
            with partial.open('ab' if offset else 'wb') as output:
                while True:
                    block = response.read(1024 * 1024)
                    if not block: break
                    output.write(block); total += len(block)
                    if total // (128 * 1024 * 1024) > announced:
                        announced = total // (128 * 1024 * 1024)
                        print(f'{args.dataset}: {total:,} bytes downloaded', flush=True)
        if not zipfile.is_zipfile(partial): raise SystemExit('Not a valid ZIP. Partial file retained for inspection.')
        actual = digest(partial, 'md5')
        if expected and actual != expected: raise SystemExit(f'MD5 mismatch: {actual}. Do not use this archive.')
        partial.rename(destination)
    else:
        print('Existing archive found; verifying instead of downloading again.')
        if not zipfile.is_zipfile(destination): raise SystemExit('Existing file is not a ZIP archive.')
        actual = digest(destination, 'md5')
        if expected and actual != expected: raise SystemExit('Existing archive does not match the expected MD5.')
    with zipfile.ZipFile(destination) as archive:
        members = archive.infolist()
        expanded = sum(f.file_size for f in members)
    report = {'dataset': args.dataset, 'source': url, 'file': name, 'bytes': destination.stat().st_size, 'md5': actual, 'expected_md5': expected, 'sha256': digest(destination, 'sha256'), 'archive_members': len(members), 'uncompressed_bytes': expanded, 'extracted': False, 'trained': False}
    (raw / (name + '.integrity.json')).write_text(json.dumps(report, indent=2))
    if args.dataset == 'ir':
        urllib.request.urlretrieve('https://raw.githubusercontent.com/RaptorMaps/InfraredSolarModules/master/LICENSE', raw / 'InfraredSolarModules-LICENSE.txt')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
