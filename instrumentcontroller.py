import random
import time

import numpy as np

from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal
from forgot_again.file import load_ast_if_exists, pprint_to_file

from instr.instrumentfactory import mock_enabled, SourceFactory, AnalyzerFactory, GeneratorFactory
from measureresult import MeasureResult
from secondaryparams import SecondaryParams

GIGA = 1_000_000_000
MEGA = 1_000_000
KILO = 1_000
MILLI = 1 / 1_000
MICRO = 1 / 1_000_000
NANO = 1 / 1_000_000_000


class InstrumentController(QObject):
    pointReady = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        addrs = load_ast_if_exists('instr.ini', default={
            'Генератор': 'GPIB1::19::INSTR',
            'Источник': 'GPIB1::3::INSTR',
            'Анализатор': 'GPIB1::18::INSTR',
        })

        self.requiredInstruments = {
            'Генератор': GeneratorFactory(addrs['Генератор']),
            'Источник': SourceFactory(addrs['Источник']),
            'Анализатор': AnalyzerFactory(addrs['Анализатор']),
        }

        self.deviceParams = {
            'Приёмник': {
                'F': 1,
            },
        }

        self.secondaryParams = SecondaryParams(required={
            'rf_f_min': [
                'Fмин=',
                {'start': 1.0, 'end': 6.0, 'step': 0.1, 'value': 1.15, 'decimals': 3, 'suffix': ' GHz'}
            ],
            'rf_f_max': [
                'Fмакс=',
                {'start': 1.0, 'end': 6.0, 'step': 0.1, 'value': 1.65, 'decimals': 3, 'suffix': ' GHz'}
            ],
            'rf_f_step': [
                'Fшаг=',
                {'start': 0.001, 'end': 6.0, 'step': 0.1, 'value': 0.1, 'decimals': 3, 'suffix': ' GHz'}
            ],
            'rf_p_min': [
                'Pвх.мин=',
                {'start': -60.0, 'end': 20.0, 'step': 1.0, 'value': -30.0, 'suffix': ' дБм'}
            ],
            'rf_p_max': [
                'Pвх.макс=',
                {'start': -60.0, 'end': 20.0, 'step': 1.0, 'value': 0.0, 'suffix': ' дБм'}
            ],
            'rf_p_step': [
                'Pвх.шаг=',
                {'start': -60.0, 'end': 20.0, 'step': 1.0, 'value': 10.0, 'suffix': ' дБм'}
            ],
            'src_u': [
                'Uпит=',
                {'start': 3.0, 'end': 3.5, 'step': 0.1, 'value': 3.3, 'suffix': ' В'}
            ],
            'src_i_max': [
                'Iпот.макс=',
                {'start': 10.0, 'end': 80.0, 'step': 1.0, 'value': 60.0, 'suffix': ' мА'}
            ],
            'sa_span': [
                'SA span',
                {'start': 5.0, 'end': 500.0, 'step': 1.0, 'value': 100.0, 'suffix': ' МГц'}
            ],
            'sa_rlev': [
                'SA rlev',
                {'start': 0.0, 'end': 50.0, 'step': 1.0, 'value': 10.0, 'suffix': ' дБ'}
            ],
        })
        self.secondaryParams.load_from_config('params.ini')

        self._instruments = dict()
        self.found = False
        self.present = False
        self.hasResult = False

        self.result = MeasureResult()

    def __str__(self):
        return f'{self._instruments}'

    # region connections
    def connect(self, addrs):
        print(f'searching for {addrs}')
        for k, v in addrs.items():
            self.requiredInstruments[k].addr = v
        self.found = self._find()

    def _find(self):
        self._instruments = {
            k: v.find() for k, v in self.requiredInstruments.items()
        }
        return all(self._instruments.values())

    def check(self, token, params):
        print(f'call check with {token} {params}')
        device, secondary = params
        self.present = self._check(token, device, secondary)

    def _check(self, token, device, secondary):
        print(f'launch check with {self.deviceParams[device]} {self.secondaryParams}')
        self._init()
        res = random.choice([1, 2])
        if res == 2:
            return False
        return True
    # endregion

    # region calibrations
    def calibrate(self, token, params):
        print(f'call calibrate with {token} {params}')
        return self._calibrate(token, self.secondaryParams)

    def _calibrateLO(self, token, secondary):
        print('run calibrate LO with', secondary)
        result = {}
        self._calibrated_pows_lo = result
        return True

    def _calibrateRF(self, token, secondary):
        print('run calibrate RF')
        result = {}
        self._calibrated_pows_rf = result
        return True

    def _calibrateMod(self, token, secondary):
        print('calibrate mod gen')
        result = {}
        self._calibrated_pows_mod = result
        return True
    # endregion

    # region initialization
    def _clear(self):
        self.result.clear()

    def _init(self):
        self._instruments['Анализатор'].send('*RST')
        self._instruments['Генератор'].send('*RST')
        self._instruments['Источник'].send('*RST')
    # endregion

    def measure(self, token, params):
        print(f'call measure with {token} {params}')
        device, _ = params
        try:
            self.result.set_secondary_params(self.secondaryParams)
            self.result.set_primary_params(self.deviceParams[device])
            self._measure(token, device)
            # self.hasResult = bool(self.result)
            self.hasResult = True  # TODO HACK
        except RuntimeError as ex:
            print('runtime error:', ex)

    def _measure(self, token, device):
        param = self.deviceParams[device]
        secondary = self.secondaryParams.params
        print(f'launch measure with {token} {param} {secondary}')

        self._clear()
        _ = self._measure_tune(token, param, secondary)
        self.result.set_secondary_params(self.secondaryParams)
        return True

    def _measure_tune(self, token, param, secondary):
        sa = self._instruments['Анализатор']
        gen_rf = self._instruments['Генератор']
        src = self._instruments['Источник']

        rf_f_min = secondary['rf_f_min'] * GIGA
        rf_f_max = secondary['rf_f_max'] * GIGA
        rf_f_step = secondary['rf_f_step'] * GIGA
        rf_p_min = secondary['rf_p_min']
        rf_p_max = secondary['rf_p_max']
        rf_p_step = secondary['rf_p_step']

        src_v = secondary['src_u']
        src_i_max = secondary['src_i_max'] * MILLI

        sa_span = secondary['sa_span'] * MEGA
        sa_rlev = secondary['sa_rlev']

        gen_rf.send('*RST')
        sa.send('*RST')
        src.send('*RST')

        # setup
        gen_rf.send(f':OUTP:MOD:STAT OFF')

        sa.send(':CAL:AUTO OFF')
        sa.send(':CALC:MARK1:MODE POS')
        sa.send(f':SENS:FREQ:SPAN {sa_span}Hz')
        sa.send(f'DISP:WIND:TRAC:Y:RLEV {sa_rlev}')
        # sa.send(f'DISP:WIND:TRAC:Y:PDIV {sa_scale_y}')

        src.send(f'APPLY p6v,{src_v}V,{src_i_max}mA')
        src.send('OUTP ON')

        freq_rf_values = [round(x, 3) for x in np.arange(start=rf_f_min, stop=rf_f_max + 0.0001, step=rf_f_step)] \
            if rf_f_min != rf_f_max else [rf_f_min]
        pow_rf_values = [round(x, 3) for x in np.arange(start=rf_p_min, stop=rf_p_max + 0.0001, step=rf_p_step)] \
            if rf_p_min != rf_p_max else [rf_p_min]

        # measurement
        res = []
        for _ in range(3):
            for rf_freq in freq_rf_values:
                gen_rf.send(f'SOUR:FREQ {rf_freq}Hz')
                for rf_pow in pow_rf_values:

                    if token.cancelled:
                        src.send('OUTP OFF')
                        gen_rf.send(f'OUTP:STAT OFF')
                        time.sleep(0.2)

                        gen_rf.send(f'SOUR:POW {pow_rf_values[0]}dbm')
                        gen_rf.send(f'SOUR:FREQ {freq_rf_values[0]}Hz')

                        sa.send(':CAL:AUTO ON')
                        raise RuntimeError('calibration cancelled')

                    gen_rf.send(f'SOUR:POW {rf_pow}dbm')
                    gen_rf.send(f'OUTP:STAT ON')

                    if not mock_enabled:
                        time.sleep(0.5)

                    center_freq = rf_freq
                    sa.send(':CALC:MARK1:MODE POS')
                    sa.send(f':SENSe:FREQuency:CENTer {center_freq}Hz')
                    p = sa.send(f':CALCulate:MARKer1:X:CENTer {center_freq}Hz')
                    res.append(p)

        src.send('OUTP OFF')
        gen_rf.send(f'OUTP:STAT OFF')
        time.sleep(0.2)

        gen_rf.send(f'SOUR:POW {pow_rf_values[0]}dbm')
        gen_rf.send(f'SOUR:FREQ {freq_rf_values[0]}Hz')

        sa.send(':CAL:AUTO ON')
        return res

    def _add_measure_point(self, data):
        print('measured point:', data)
        self.result.add_point(data)
        self.pointReady.emit()

    def saveConfigs(self):
        pprint_to_file('params.ini', self.secondaryParams.params)

    @pyqtSlot(dict)
    def on_secondary_changed(self, params):
        self.secondaryParams.params = params

    @property
    def status(self):
        return [i.status for i in self._instruments.values()]
