import os, sys
import ProjectPaths
from Props import QueryConfig as qc
from Props import AnalysisCatalog as ac

root_ = ProjectPaths.C_PATH_BASE
print(root_)
os.chdir(root_)
sys.path.append(root_)

import streamlit as st
st.set_page_config(layout='centered', page_title='AnalysisConfiguration', initial_sidebar_state='collapsed')

import numpy as np
import yaml
import warnings
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

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

    data_dir = os.path.join(ProjectPaths.C_PATH_ANALYSIS, '{}'.format(analysis_selected), 'data')

    cfg_dir = qc(analysis_selected).cfg_path
    yaml_config_ = qc(analysis_selected).cfg_file

    config_ = qc(analysis_selected).query_cfg

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
    data = yf.download(qc(analysis_selected).query_tickers, qc(analysis_selected).query_start,
                       qc(analysis_selected).query_end)

    sd_text = (qc(analysis_selected).query_start).strftime('%Y%m%d')
    ed_text = (qc(analysis_selected).query_end).strftime('%Y%m%d')

    print(qc(analysis_selected).query_tickers)

    if len(qc(analysis_selected).query_tickers) == 1:
        data_dict = {qc(analysis_selected).query_tickers[0]:data}
        data.to_csv(os.path.join(data_dir, '{0}_{1}_{2}.csv'.format(qc(analysis_selected).query_tickers[0],
                                                                    sd_text, ed_text)))
    else:
        data_dict = {}
        cols = np.unique([data.columns[i][0] for i in np.arange(len(data.columns))])  # get unique list of columns

        for t in qc(analysis_selected).query_tickers:
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
        data['Date'] = pd.to_datetime(data['Date'])
        data.set_index('Date', inplace=True)
        f_txt = (f[:-4]).split('_')
        t = f_txt[0]
        data_dict.update({t:data})
    return data_dict

def addChartElement(df, elems):
    if '9D Moving Avg' in elems:
        df = ac(df).nineDayMA
    if '18D Moving Avg' in elems:
        df = ac(df).eighteenDayMA
    return df

def makeFig(t, df, elems):
    fig_data = [go.Candlestick(x=t_data.index,
                               open=t_data['Open'],
                               high=t_data['High'],
                               low=t_data['Low'],
                               close=t_data['Close'],
                               name=t)
                ]

    if '9D Moving Avg' in elems:
        fig_data.extend([go.Scatter(x=t_data.index, y=t_data['9dma'], mode='lines', name='9D Moving Avg')])

    if '18D Moving Avg' in elems:
        fig_data.extend([go.Scatter(x=t_data.index, y=t_data['18dma'], mode='lines', name='18D Moving Avg')])

    fig = go.Figure(data=fig_data)
    fig.update_layout(title=t,
                      yaxis_title='USD')

    fig.update_xaxes(rangebreaks=[{'pattern': 'day of week', 'bounds': [6, 1]}])

    return fig

st.markdown("<h2 style='text-align: center; color: grey;'> Data Query from Yahoo Finance </h2>", unsafe_allow_html=True)

config_params = qc(analysis_selected).query_cfg['analysisParameters']
st.dataframe(qc(analysis_selected).df_cfg, hide_index=True)
st.divider()

if qc(analysis_selected).check_data == False:

    queryData = st.button('Query Data?')
    if queryData:
        data = run_query(qc(analysis_selected).df_cfg)
else:
    st.write('Data for this set of configuration parameters has already been queried. Reading data from file(s):')

    data = read_data()

if qc(analysis_selected).check_data:
    t1, t2 = st.tabs(['Data Tables', 'Charts'])

    with t1:
        st.markdown("<h2 style='text-align: center; color: grey;'> Raw Data Tables </h2>", unsafe_allow_html=True)
        for t in qc(analysis_selected).query_tickers:
            st.write('Queried Data for Ticker: {}'.format(t))
            st.dataframe(data[t])

    with t2:
        st.markdown("<h2 style='text-align: center; color: grey;'> Data Charts </h2>", unsafe_allow_html=True)

        t = st.selectbox(label='Select Ticker', options=qc(analysis_selected).query_tickers)

        elements = st.multiselect(label='Select one or more additional chart elements', options=ac.list_analyses)

        sd = st.date_input(label='Select Chart Start Date', value=None,
                           min_value=pd.to_datetime(qc(analysis_selected).query_start),
                           max_value=pd.to_datetime(qc(analysis_selected).query_end))

        ed = st.date_input(label='Select Chart End Date', value=None,
                           min_value=pd.to_datetime(qc(analysis_selected).query_start),
                           max_value=pd.to_datetime(qc(analysis_selected).query_end))

        t_data = addChartElement(data[t], elements)

        t_data = t_data.loc[sd:ed, :]

        showChart = st.button(label='Show Chart?')

        if showChart:
            st.plotly_chart(figure_or_data=makeFig(t, t_data, elements), theme='streamlit', use_container_width=True, on_select='ignore')
