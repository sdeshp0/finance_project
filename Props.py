import sys, os
import traceback
import yaml
import numpy as np
import pandas as pd
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname((__file__)))))

import ProjectPaths

class QueryConfig(object):
    """
    Access Query Properties from Config
    """

    def __init__(self, name):

        self.analysis_name = name
        self.cfg_path = os.path.join(ProjectPaths.C_PATH_ANALYSIS, '{}'.format(self.analysis_name), 'config')
        self.cfg_file = os.path.join(self.cfg_path, '{}.yaml'.format(self.analysis_name))

        self.query_cfg = self._get_query_cfg()
        self.check_data = self._check_data()

        self.list_params = self._get_param_list()
        self.df_cfg = self._get_display()

        self.query_start = self._get_param('startDate')
        self.query_end = self._get_param('endDate')
        self.query_tz = self._get_param('analysisTZ')
        self.query_tickers = self._get_param('selectedTickers')

    def _get_query_cfg(self):
        cfg_file = os.path.join(self.cfg_path, '{}.yaml'.format(self.analysis_name))

        with open(cfg_file, 'r') as f:
            config_ = yaml.safe_load(f)
        f.close()

        return config_

    def _check_data(self):
        if self.query_cfg['queriedData'] > 0:
            return True
        else:
            return False

    def _get_param_list(self):
        return self.query_cfg['analysisParameters'].keys()

    def _get_param(self, param):
        if param in ['startDate', 'endDate']:
            return pd.to_datetime(self.query_cfg['analysisParameters'][param])
        else:
            return self.query_cfg['analysisParameters'][param]

    def _get_display(self):
        df = pd.DataFrame(index=[0], columns=['selectedTickers', 'startDate', 'endDate', 'analysisTZ'])
        for p in df.columns:
            if p in ['selectedTickers']:
                df.loc[0, p] = ', '.join(self._get_param(p))
            else:
                df.loc[0, p] = self._get_param(p)
            if p in ['startDate', 'endDate']:
                df[p] = pd.to_datetime(df[p])
        return df

class AnalysisCatalog(object):
    """
    Catalog of all the analyses used in this project
    """

    list_analyses = ['9D Moving Avg', '18D Moving Avg']

    def __init__(self, data):
        self.data = data
        self.nineDayMA = self._nineDayMA(data)
        self.eighteenDayMA = self._eighteenDayMA(data)

    def _nineDayMA(self, data):
        """Compute 9 Day Moving Average of Stock Data"""
        data['9dma'] = data['Close'].rolling(9).mean()
        return data

    def _eighteenDayMA(self, data):
        """Compute 18 Day Moving Average of Stock Data"""
        data['18dma'] = data['Close'].rolling(18).mean()
        return data