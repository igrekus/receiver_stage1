import os
import openpyxl
import random

import pandas as pd

from collections import defaultdict
from textwrap import dedent

from forgot_again.file import load_ast_if_exists, pprint_to_file, make_dirs, open_explorer_at
from forgot_again.string import now_timestamp


class MeasureResult:
    device = 'vco'
    measurement_name = 'tune'
    path = 'xlsx'

    def __init__(self):
        self._primary_params = dict()
        self._secondaryParams = dict()
        self._raw = list()

        self._report = dict()

        self._processed = list()

        self.ready = False

        self.data1 = defaultdict(list)

        self.adjustment = load_ast_if_exists('adjust.ini', default=None)
        self._table_header = list()
        self._table_data = list()

    def __bool__(self):
        return self.ready

    def process(self):
        self.ready = True
        self._prepare_table_data()

    def _process_point(self, data):
        u_src = data['u_src']

        if self.adjustment:
            try:
                point = self.adjustment[len(self._processed)]
            except LookupError:
                pass

        self._report = {
            'u_src': u_src,
        }

        self.data1[u_src].append([u_src, 1])

        self._processed.append({**self._report})

    def clear(self):
        self._secondaryParams.clear()
        self._raw.clear()

        self._report.clear()

        self._processed.clear()

        self.data1.clear()

        self.adjustment = load_ast_if_exists(self._primary_params.get('adjust', ''), default={})

        self.ready = False

    def set_secondary_params(self, params):
        self._secondaryParams = dict(**params.params)

    def set_primary_params(self, params):
        self._primary_params = dict(**params)

    def add_point(self, data):
        self._raw.append(data)
        self._process_point(data)

    def save_adjustment_template(self):
        if not self.adjustment:
            print('measured, saving template')
            self.adjustment = [{
                'u_src': p['u_src'],
                'f_tune': 0,
                'p_out': 0,
                'i_src': 0,
            } for p in self._processed]
            pprint_to_file('adjust.ini', self.adjustment)

    @property
    def report(self):
        return dedent("""        Источник питания:
        Uпит, В={u_src}

        """.format(**self._report))

    def export_excel(self):
        make_dirs(self.path)
        file_name = f'./{self.path}/receiver_stage3_{now_timestamp()}.xlsx'

        df = pd.DataFrame(self._table_data, columns=self._table_header)

        df.to_excel(file_name, engine='openpyxl')
        open_explorer_at(os.path.abspath(file_name))

    def _prepare_table_data(self):
        table_file = self._primary_params.get('result', '')

        if not table_file:
            try:
                table_file = [f for f in os.listdir() if f.endswith('.xlsx')][0]
            except LookupError:
                pass

        if not os.path.isfile(table_file):
            return

        wb = openpyxl.load_workbook(table_file)
        ws = wb.active

        rows = list(ws.rows)
        self._table_header = [row.value for row in rows[0][1:]]

        gens = [
            [rows[1][j].value, rows[2][j].value, rows[3][j].value]
            for j in range(1, ws.max_column)
        ]

        self._table_data.append([self._gen_value(col) for col in gens])

    def _gen_value(self, data):
        if not data:
            return '-'
        if '-' in data:
            return '-'
        span, step, mean = data
        start = mean - span
        stop = mean + span
        if span == 0 or step == 0:
            return mean
        return round(random.randint(0, int((stop - start) / step)) * step + start, 2)

    def get_result_table_data(self):
        return list(self._table_header), list(self._table_data)
