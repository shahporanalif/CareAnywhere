"""Small local fixture test for the PyOsmium facility importer."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

from app.healthcare_store import search_local_facilities
from scripts.import_healthcare_osm import import_pbf


@unittest.skipUnless(importlib.util.find_spec("osmium"), "optional PyOsmium package is not installed")
class HealthcareImporterTests(unittest.TestCase):
    def test_imports_nodes_ways_and_area_relations(self):
        osm_xml = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="CareAnywhere test">
  <node id="1" version="1" lat="23.7800" lon="90.4100"><tag k="amenity" v="pharmacy"/><tag k="name" v="Fixture Pharmacy"/></node>
  <node id="2" version="1" lat="23.7800" lon="90.4110"/>
  <node id="3" version="1" lat="23.7810" lon="90.4110"/>
  <node id="4" version="1" lat="23.7810" lon="90.4120"/>
  <node id="5" version="1" lat="23.7800" lon="90.4120"/>
  <node id="6" version="1" lat="23.7820" lon="90.4110"/>
  <node id="7" version="1" lat="23.7830" lon="90.4110"/>
  <node id="8" version="1" lat="23.7830" lon="90.4120"/>
  <node id="9" version="1" lat="23.7820" lon="90.4120"/>
  <way id="20" version="1"><nd ref="6"/><nd ref="7"/><nd ref="8"/><nd ref="9"/><nd ref="6"/><tag k="amenity" v="clinic"/><tag k="name" v="Fixture Clinic"/></way>
  <way id="30" version="1"><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="5"/><nd ref="2"/></way>
  <relation id="40" version="1"><member type="way" ref="30" role="outer"/><tag k="type" v="multipolygon"/><tag k="amenity" v="hospital"/><tag k="name" v="Fixture Hospital"/></relation>
</osm>"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "fixture.osm"
            database = root / "healthcare.sqlite3"
            source.write_text(osm_xml, encoding="utf-8")
            count = import_pbf(source, database)
            facilities, _ = search_local_facilities(23.781, 90.411, 1000, "all", db_path=database)
        self.assertEqual(count, 3)
        self.assertEqual({facility["name"] for facility in facilities}, {
            "Fixture Pharmacy", "Fixture Clinic", "Fixture Hospital"
        })


if __name__ == "__main__":
    unittest.main()
