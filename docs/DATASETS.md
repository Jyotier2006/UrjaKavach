# Dataset acquisition

**CARE To Compare v6 has been downloaded**, MD5-verified against the provider checksum and extracted to `data/raw/CARE_To_Compare/` (5,503,439,673 bytes archived, ~19 GB expanded, 110 archive members, integrity record in `data/raw/CARE_To_Compare.zip.integrity.json`). The solar and infrared datasets are still absent.

## CARE to Compare v6

- Provider: https://zenodo.org/records/15846963
- Direct archive: https://zenodo.org/api/records/15846963/files/CARE_To_Compare.zip/content
- Provider-reported size: 5,503,439,673 bytes.
- Provider-reported MD5: `2547b58c21ac8c242d13232860cf500c`.
- License verified in record metadata: CC BY-SA 4.0.
- Intended extraction: `data/raw/CARE_To_Compare/`.
- Treat each event file as independent. Never stitch anonymized timestamps. Inspect archive member sizes before extraction; the uncompressed collection is much larger than the ZIP.

## Solar Power Generation Data

- Author: anikannal / Ani Kannal.
- Provider: https://www.kaggle.com/datasets/anikannal/solar-power-generation-data
- Public download endpoint: https://www.kaggle.com/api/v1/datasets/download/anikannal/solar-power-generation-data
- Account requirements may depend on Kaggle access rules. If the request is denied, use the provider's authenticated download; do not substitute an unknown mirror.
- Verify the dataset license, CSV units, date ranges and DC/AC consistency before modeling. No unit correction has been established in this handoff.

## Infrared Solar Modules

- Provider: https://github.com/RaptorMaps/InfraredSolarModules
- Direct archive: https://raw.githubusercontent.com/RaptorMaps/InfraredSolarModules/master/2020-02-14_InfraredSolarModules.zip
- Provider-reported archive size: 15,495,990 bytes.
- License file: https://raw.githubusercontent.com/RaptorMaps/InfraredSolarModules/master/LICENSE
- Repository reports MIT. Download and preserve LICENSE with the images.
- Read class names/counts from `module_metadata.json` after extraction. These are single-module crops, not drone maps.

## Download commands

Python standard library only; run from the repository root:

```bash
python3 scripts/download_datasets.py ir
python3 scripts/download_datasets.py solar
python3 scripts/download_datasets.py care
```

The script avoids overwriting completed archives, supports resumable partial downloads where the server honors byte ranges, verifies the CARE checksum, and saves local integrity records. It does not automatically extract or train models. No multi-gigabyte dataset is committed or included in the source ZIP.
