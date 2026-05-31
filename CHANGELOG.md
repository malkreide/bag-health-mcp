# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Tool-definition hash pinning (SEC-022, rug-pull guard):** each tool's
  contract (name + description + input/output schema) is SHA-256-hashed and
  pinned in [`tool-hashes.json`](tool-hashes.json); CI fails on unacknowledged
  drift. Current truncated hashes (full values in the snapshot):
  - `bag_download_export`: `5faea66714a4f780…`
  - `bag_get_canton_situation`: `cc636a3b734a87bf…`
  - `bag_get_data_version`: `657be7231cf217c4…`
  - `bag_get_disease_data`: `21738ff8a24a2485…`
  - `bag_get_series_details`: `47b86d154028caa4…`
  - `bag_list_diseases`: `2d28813b0d3efe9a…`
  - `bag_list_export_files`: `372ec2d116b025aa…`
  - `bag_list_series`: `93aabc362e869fb0…`

  Regenerate after an intentional tool change with
  `python scripts/tool_hashes.py --write`.

## [0.1.0] - 2026-04-01

### Added
- Initial release with BAG Infectious Disease Dashboard (IDD) integration
- **8 Tools**: `bag_list_diseases`, `bag_list_series`, `bag_get_series_details`, `bag_get_disease_data`, `bag_get_canton_situation`, `bag_list_export_files`, `bag_download_export`, `bag_get_data_version`
- 51 pathogens across 6 categories (respiratory, enteric, STI/bloodborne, vaccine-preventable, vector-borne, wastewater)
- Canton-level situational overview for school authorities
- Dual transport: stdio (Claude Desktop) + Streamable HTTP (cloud)
- GitHub Actions CI (Python 3.11, 3.12, 3.13)
- Bilingual documentation (DE/EN)
- Unit and live integration tests (mocked HTTP via respx)
