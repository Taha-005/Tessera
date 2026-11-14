# data/

Only synthetic data is committed here, under `data/synthetic/`. Each generated instance records its seed and
parameters and is labeled synthetic (project document, Section 8.3).

Raw department files are stored in the team-only shared drive and are never committed (Decision D-13).
The code reads the data location from configuration, so nothing in this repository points at real files.
