import sys, os
import traceback
import yaml
import numpy as np
import pandas as pd
pd.options.mode.chained_assignment = None  # default='warn'
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname((__file__)))))

import ProjectPaths

class ConfigProps(object):
    """
    Access Properties from Config
    """

    def __init__(self, name):

        self.analysis_name = name
        self.cfg_path = os.path.join(ProjectPaths.C_PATH_ANALYSIS, '{}'.format(self.analysis_name), 'config')
        self.data_path = os.path.join(ProjectPaths.C_PATH_ANALYSIS, '{}'.format(self.analysis_name), 'data')
        self.cfg_file = os.path.join(self.cfg_path, '{}.yaml'.format(self.analysis_name))

        self.config = self._get_cfg()

        self.query_params = self._get_query_param_list()
        self.analysis_params = self._get_analysis_param_list()
        self.df_query = self._display_query()
        self.df_analysis = self._display_analysis()

        self.query_start = self._get_param('startDate')
        self.query_end = self._get_param('endDate')
        self.query_tz = self._get_param('analysisTZ')
        self.query_tickers = self._get_param('selectedTickers')

        self.short_sma_range = self._get_param('smaShort')
        self.long_sma_range = self._get_param('smaLong')
        self.short_ema_range = self._get_param('emaShort')
        self.long_ema_range = self._get_param('emaLong')

    def _get_cfg(self):
        cfg_file = os.path.join(self.cfg_path, '{}.yaml'.format(self.analysis_name))

        with open(cfg_file, 'r') as f:
            config_ = yaml.safe_load(f)
        f.close()

        return config_

    def _get_query_param_list(self):
        return self.config['queryParameters'].keys()

    def _get_analysis_param_list(self):
        return self.config['analysisParameters'].keys()

    def _get_param(self, param):

        if param in self.query_params:
            if param in ['startDate', 'endDate']:
                return pd.to_datetime(self.config['queryParameters'][param])
            else:
                return self.config['queryParameters'][param]

        if param in self.analysis_params:
            return self.config['analysisParameters'][param]

    def _display_query(self):
        df = pd.DataFrame(index=[0], columns=self.query_params)
        for p in df.columns:
            if p in ['selectedTickers']:
                df.loc[0, p] = ', '.join(self._get_param(p))
            else:
                df.loc[0, p] = self._get_param(p)
            if p in ['startDate', 'endDate']:
                df[p] = pd.to_datetime(df[p])
        return df

    def _display_analysis(self):
        df = pd.DataFrame(index=[0], columns=self.analysis_params)
        for p in df.columns:
            df.loc[0, p] = self._get_param(p)
        return df

class AnalysisCatalogGlobal(object):
    """
    Catalog of all the global analyses used in this project
    """

    list_analyses = ['SMA Short',
                     'SMA Long',
                     'EMA Short',
                     'EMA Long'
                     ]

    def __init__(self, data, param):
        self.data = data
        self.param = param
        self.shortSMA = self._shortSMA(data)
        self.longSMA = self._longSMA(data)
        self.shortEMA = self._shortEMA(data)
        self.longEMA = self._longEMA(data)

    def _shortSMA(self, data):
        """Compute Short Term Moving Average of Stock Data"""
        data['shortSMA'] = data['Adj Close'].rolling(self.param['shortSMA']).mean()
        return data

    def _longSMA(self, data):
        """Compute Long Term Moving Average of Stock Data"""
        data['longSMA'] = data['Adj Close'].rolling(self.param['longSMA']).mean()
        return data

    def _shortEMA(self, data):
        """Compute Short Term Exponential Moving Average of Stock Data"""
        data['shortEMA'] = data['Adj Close'].ewm(span=self.param['shortEMA'], adjust=False).mean()
        return data

    def _longEMA(self, data):
        """Compute Long Term Exponential Moving Average of Stock Data"""
        data['longEMA'] = data['Adj Close'].ewm(span=self.param['longEMA'], adjust=False).mean()
        return data

class AnalysisCatalogSubset(object):
    """
    Catalog of all the subset analyses used in this project
    """

    list_analyses = ['Fibonacci']

    def __init__(self, data):
        self.data = data
        self.fibonacci = self._get_fibonnaci(data)

    def _get_fibonnaci(self, data):
        p_min = data['Adj Close'].min()
        p_max = data['Adj Close'].max()
        diff = p_max - p_min

        data['fibonacci_min'] = p_min
        data['fibonacci_level1'] = p_max - 0.236 * diff
        data['fibonacci_level2'] = p_max - 0.382 * diff
        data['fibonacci_level3'] = p_max - 0.618 * diff
        data['fibonacci_max'] = p_max
        return data