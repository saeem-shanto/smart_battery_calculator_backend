"""Standalone v1 adapter tests, runnable without Django or Octave installed."""
import importlib.util
import math
import pathlib
import sys
import tempfile
import os
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = ROOT / 'apps/calculations/services/updated_battery_engine.py'

def load_engine():
    django = types.ModuleType('django')
    conf = types.ModuleType('django.conf')
    conf.settings = types.SimpleNamespace(BASE_DIR=ROOT, OCTAVE_EXECUTABLE='octave', OCTAVE_TIMEOUT_SECONDS=120)
    django.conf=conf
    sys.modules['django']=django
    sys.modules['django.conf']=conf
    for name in ['apps', 'apps.calculations', 'apps.calculations.services']:
        mod=types.ModuleType(name)
        mod.__path__=[]
        sys.modules[name]=mod
    errors=types.ModuleType('apps.calculations.services.errors')
    errors.CalculationEngineExecutionError=type('CalculationEngineExecutionError',(Exception,),{})
    errors.CalculationEngineUnavailable=type('CalculationEngineUnavailable',(Exception,),{})
    sys.modules[errors.__name__]=errors
    spec=importlib.util.spec_from_file_location('apps.calculations.services.updated_battery_engine',MODULE)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod

u=load_engine()
source=(ROOT/'matlab_source_v1/batt_cal_v1.m').read_text()
class UpdatedModelTests(unittest.TestCase):
    def test_uploaded_reference_source_is_identical(self):
        self.assertEqual(__import__('hashlib').sha256((ROOT/'matlab_source_v1/batt_cal_v1.m').read_bytes()).hexdigest(),
                         'd0cd927d2592b99edaf523b4516b588c77d882cd505bd393cbe23ed0f8c25df4')
    def test_transformation_all_fields(self):
        params=u.UpdatedModelSettings(battery_capacity_kwh=12, pv_capacity_kw=7.5,
             interest_rate_percent=3.5, installation_cost_aud=12000, loan_period_years=12,
             daily_supply_charge_aud=1.25,
             retail_tariff_24h=tuple([0.41]*24), feed_in_tariff_24h=tuple([0.07]*24))
        script=u.render_runtime_script(source,params,daily_average_kwh=22)
        for snippet in ('x=12;', 'cap_pv=7.5;', 'daily_avg=22;', 'i=0.035;', 'IC=12000;', 'lspan=12;', 'dc=1.25;',
                        'if i==0; crf=1/lspan;', 'rp_tou=['+';'.join(['0.41']*24)+']', 'fit_tou=['+';'.join(['0.07']*24)+']'):
            self.assertIn(snippet,script)
        self.assertNotIn('x=15;',script)
    def test_reject_missing_signature(self):
        with self.assertRaises(Exception): u.render_runtime_script(source.replace('x=15;', 'x=13;'),u.UpdatedModelSettings(), daily_average_kwh=12)
    def test_param_validation(self):
        for params in [u.UpdatedModelSettings(battery_capacity_kwh=51), u.UpdatedModelSettings(interest_rate_percent=-1),
                       u.UpdatedModelSettings(retail_tariff_24h=(0.4,)), u.UpdatedModelSettings(loan_period_years=2.5)]:
            with self.assertRaises(ValueError): u.validate_settings(params)
    def test_parse_new_model_seven_values(self):
        self.assertEqual(u.parse_runtime_output(b'15,921,400,200,0,900,6\n'),(15,921,400,200,0,900,6))
        with self.assertRaises(Exception):u.parse_runtime_output(b'1,2,3,4,5,6,7,8,9,10\n')
    def test_engine_result_mapping_with_stub_executable(self):
        # This is NOT an Octave execution; checks the execution interface and 7-value response mapping.
        with tempfile.TemporaryDirectory() as tmp:
            script=pathlib.Path(tmp)/'octave-fake'
            script.write_text('#!/bin/sh\nprintf "15,1000,200,400,0,900,6\\n" > Results_RPAtrail400.csv\n')
            os.chmod(script,0o755)
            engine=u.UpdatedBatteryEngine()
            engine.executable=str(script)
            result, raw, elapsed=engine.calculate([0.0]*8760,[0.6]*8760,u.UpdatedModelSettings())
            self.assertEqual(result['calculation_mode'],'selected_capacity')
            self.assertEqual(result['annual_installment_aud'],900)
            self.assertEqual(result['battery_capacity_kwh'],15)
            self.assertEqual(result['pv_size_kw'],6)
            self.assertEqual(result['annual_load_kwh'],round(0.6*8760,2))
            self.assertTrue(raw.startswith(b'15,'))
            self.assertGreaterEqual(elapsed,0)

    def test_pv_scaling(self):
        p5=10.0
        base=p5/(u.PV_CORRECTION*(5/3))
        self.assertAlmostEqual(base*u.PV_CORRECTION*(6/3),12.0,places=8)

if __name__=='__main__': unittest.main(verbosity=2)
