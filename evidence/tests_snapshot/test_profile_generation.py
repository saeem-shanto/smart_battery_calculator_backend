"""Django TestCase tests; run: python manage.py test apps.calculations.tests_generated"""
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from django.test import SimpleTestCase
from apps.calculations.services.generated_profiles import build_generated_csv, ProfileGenerationError, LEGACY_PV_MULTIPLIER
import base64
import csv
import io

class AnnualGenerationTests(SimpleTestCase):
    @patch('apps.calculations.services.generated_profiles._annual_pv')
    @patch('apps.calculations.services.generated_profiles.postcode_coordinates')
    def test_8760_rows_load_repeat_and_inverse_pv_scaling(self, lookup, pv):
        lookup.return_value = {'latitude':-34.9,'longitude':138.6,'place':'Adelaide','approximate':False}
        pv.return_value = [2.0] * 8760
        generated = build_generated_csv(postcode='5000',state='SA',load=[float(i) for i in range(24)],year=2023,tilt=25,azimuth=0,loss=0.1)
        rows = list(csv.reader(io.StringIO(base64.b64decode(generated['csv_base64']).decode())))
        self.assertEqual(len(rows),8761)
        self.assertEqual(rows[0],['PV Generation','Load Data'])
        self.assertAlmostEqual(float(rows[1][0])*LEGACY_PV_MULTIPLIER,2.0,places=7)
        self.assertEqual(float(rows[1][1]),0.0)
        self.assertEqual(float(rows[25][1]),0.0)
        self.assertEqual(float(rows[8760][1]),23.0)
        self.assertEqual(generated['annual_load_kwh'],sum(range(24))*365)

    def test_rejects_incorrect_load_length(self):
        with self.assertRaises(ProfileGenerationError):
            build_generated_csv(postcode='5000',state='SA',load=[1]*23,year=2023,tilt=25,azimuth=0,loss=0.1)

    @patch('apps.calculations.services.generated_profiles._annual_pv')
    @patch('apps.calculations.services.generated_profiles.postcode_coordinates')
    def test_leap_year_supported_as_8760_rows(self, lookup, pv):
        lookup.return_value = {'latitude':-34.9,'longitude':138.6,'place':'Adelaide','approximate':False}
        pv.return_value = [2.0] * 8760
        generated = build_generated_csv(postcode='5000',state='SA',load=[1]*24,year=2024,tilt=25,azimuth=0,loss=0.1)
        self.assertEqual(generated['row_count'], 8760)
