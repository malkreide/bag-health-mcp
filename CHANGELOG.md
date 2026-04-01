# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
