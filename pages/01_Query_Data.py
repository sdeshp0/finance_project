import os, sys
import ProjectPaths

root_ = ProjectPaths.C_PATH_BASE
print(root_)
os.chdir(root_)
sys.path.append(root_)

import streamlit as st
st.set_page_config(layout='centered', page_title='AnalysisConfiguration', initial_sidebar_state='collapsed')

import numpy as np
import yaml
import time
import warnings
import pandas as pd
import pytz
import yfinance as yf
from datetime import datetime, timedelta

#Suppress FutureWarning messages
warnings.simplefilter(action='ignore', category=FutureWarning)
config_=None

st.markdown("<h1 style='text-align: center; color: grey;'> Configure Analysis </h1>", unsafe_allow_html=True)
st.divider()

if 'current_analysis' in st.session_state:
    analysis_selected = st.session_state['current_analysis']
else:
    st.error('Please go back to the analysis selection page and select an analysis')
    st.page_link('Finance_App.py', label='Click to go to Analysis Selection')

if analysis_selected != '':

    if os.path.exists(os.path.join(ProjectPaths.C_PATH_ANALYSIS, '{}'.format(analysis_selected))):
        analysis_dir = os.path.join(ProjectPaths.C_PATH_ANALYSIS, '{}'.format(analysis_selected))
    else:
        st.error('Analysis directory does not exist')
        st.stop()

    cfg_dir = os.path.join(ProjectPaths.C_PATH_ANALYSIS, '{}'.format(analysis_selected), 'config')
    data_dir = os.path.join(ProjectPaths.C_PATH_ANALYSIS, '{}'.format(analysis_selected), 'data')

    yaml_config_ = os.path.join(cfg_dir, '{}.yaml'.format(analysis_selected))

    with open(yaml_config_, 'r') as f:
        config_ = yaml.safe_load(f)
    f.close()

def display_config(cfg):
    '''Display query configuration parameters in table form using DataFrame'''
    df = pd.DataFrame(index=[0], columns=['startDate', 'endDate', 'analysisTZ', 'selectedTickers'])

    for c in df.columns:
        if c in ['startDate', 'endDate']:
            df.loc[0, c] = pd.to_datetime(cfg[c])
        else:
            df.loc[0, c] = cfg[c]
    st.dataframe(df, hide_index=True, use_container_width=True)
    return df

def run_query(df):
    '''Run query from Yahoo Finance using configuration parameters. Parse and return data.'''
    data = yf.download(df['selectedTickers'].values[0], df['startDate'].values[0], df['endDate'].values[0])

    sd_text = (df['startDate'].values[0]).strftime('%Y%m%d')
    ed_text = (df['endDate'].values[0]).strftime('%Y%m%d')

    data_dict = {}
    cols = np.unique([data.columns[i][0] for i in np.arange(len(data.columns))])  # get unique list of columns

    for t in df['selectedTickers'].values[0]:
        dummy = pd.DataFrame(index=data.index, columns=cols)
        for c in cols:
            dummy.loc[:, c] = data[c][t]

        dummy.to_csv(os.path.join(data_dir, '{0}_{1}_{2}.csv'.format(t,sd_text, ed_text)))

        data_dict.update({t:dummy})
    config_['queriedData'] = 1

    with open(yaml_config_, 'w') as f:
        yaml.dump(config_, f, default_flow_style=False)
        f.close()

    return data_dict

def read_data():
    files = os.listdir(data_dir)
    data_dict = {}
    for f in files:
        data = pd.read_csv(os.path.join(data_dir, f))
        f_txt = (f[:-4]).split('_')
        t = f_txt[0]
        data_dict.update({t:data})
    return data_dict




    return data

st.markdown("<h2 style='text-align: center; color: grey;'> Data Query from Yahoo Finance </h2>", unsafe_allow_html=True)

config_params = config_['analysisParameters']
df = display_config(config_params)
st.divider()

if config_['queriedData'] == 0:

    queryData = st.button('Query Data?')
    if queryData:
        data = run_query(df)
else:
    st.write('Data for this set of configuration parameters has already been queried. Reading data from file(s):')

    data = read_data()

if config_['queriedData'] > 0:
    t1, t2 = st.tabs(['Data Tables', 'Charts'])

    with t1:
        st.markdown("<h2 style='text-align: center; color: grey;'> Raw Data Tables </h2>", unsafe_allow_html=True)
        for t in df['selectedTickers'].values[0]:
            st.write('Queried Data for Ticker: {}'.format(t))
            st.dataframe(data[t])

    with t2:
        st.markdown("<h2 style='text-align: center; color: grey;'> Data Charts </h2>", unsafe_allow_html=True)

        t_opt = ['All'].extend(df['selectedTickers'].values[0])
        tick = st.selectbox(label='Select Ticker', options=t_opt)




