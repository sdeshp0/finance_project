import os
import sys
import ProjectPaths
from Props import ConfigProps as cp
from Props import AnalysisCatalogGlobal as acg
from Props import AnalysisCatalogSubset as acs

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

    cfg_dir = cp(analysis_selected).cfg_path
    data_dir = cp(analysis_selected).data_path
    yaml_config_ = cp(analysis_selected).cfg_file

    config_ = cp(analysis_selected).config


def run_query():
    '''Run query from Yahoo Finance using configuration parameters. Parse and return data.'''
    data = yf.download(cp(analysis_selected).query_tickers, cp(analysis_selected).query_start,
                       cp(analysis_selected).query_end)

    sd_text = (cp(analysis_selected).query_start).strftime('%Y%m%d')
    ed_text = (cp(analysis_selected).query_end).strftime('%Y%m%d')

    print(cp(analysis_selected).query_tickers)

    if len(cp(analysis_selected).query_tickers) == 1:
        data_dict = {cp(analysis_selected).query_tickers[0]:data}
        data.to_csv(os.path.join(data_dir, '{0}_{1}_{2}.csv'.format(cp(analysis_selected).query_tickers[0],
                                                                        sd_text, ed_text)))
    else:
        data_dict = {}
        cols = np.unique([data.columns[i][0] for i in np.arange(len(data.columns))])  # get unique list of columns

        for t in cp(analysis_selected).query_tickers:
            dummy = pd.DataFrame(index=data.index, columns=cols)
            for c in cols:
                dummy.loc[:, c] = data[c][t]

            dummy.to_csv(os.path.join(data_dir, '{0}_{1}_{2}.csv'.format(t,sd_text, ed_text)))

            data_dict.update({t:dummy})

    with open(yaml_config_, 'w') as f:
        yaml.dump(config_, f, default_flow_style=False)
        f.close()
    st.success('Data for the selected tickers and date range has been queried and saved!')
    return data_dict


def read_data():
    data_dict = {}
    for t in cp(analysis_selected).query_tickers:
        sd = cp(analysis_selected).query_start.strftime('%Y%m%d')
        ed = cp(analysis_selected).query_end.strftime('%Y%m%d')
        file = '{0}_{1}_{2}.csv'.format(t, sd, ed)
        data = pd.read_csv(os.path.join(data_dir, file))
        data['Date'] = pd.to_datetime(data['Date'])
        data.set_index('Date', inplace=True)
        data_dict.update({t:data})
    st.success('Data for the selected tickers and date range has already been query. Data has been read from files!')
    return data_dict

def updateParams(elems):
    params = {}
    if 'SMA Short' in elems:
        params['shortSMA'] = cp(analysis_selected).short_sma_range
    if 'SMA Long' in elems:
        params['longSMA'] = cp(analysis_selected).long_sma_range
    if 'EMA Short' in elems:
        params['shortEMA'] = cp(analysis_selected).short_ema_range
    if 'EMA Long' in elems:
        params['longEMA'] = cp(analysis_selected).long_ema_range
    return params


def addChartElement(df, elems):
    params = updateParams(elems)
    if 'SMA Short' in elems:
        df = acg(df, params).shortSMA
    if 'SMA Long' in elems:
        df = acg(df, params).longSMA
    if 'EMA Short' in elems:
        df = acg(df, params).shortEMA
    if 'EMA Long' in elems:
        df = acg(df, params).longEMA
    return df


def addChartElementSubset(df, elems):
    if 'Fibonacci' in elems:
        df = acs(df).fibonacci
    return df


def makeFig(t, df, elems):
    fig_data = [go.Candlestick(x=df.index,
                               open=df['Open'],
                               high=df['High'],
                               low=df['Low'],
                               close=df['Adj Close'],
                               name=t)
                ]

    if 'SMA Short' in elems:
        fig_data.extend([go.Scatter(x=df.index, y=df['shortSMA'], mode='lines', name='Short SMA')])

    if 'SMA Long' in elems:
        fig_data.extend([go.Scatter(x=df.index, y=df['longSMA'], mode='lines', name='Long SMA')])

    if 'EMA Short' in elems:
        fig_data.extend([go.Scatter(x=df.index, y=df['shortEMA'], mode='lines', name='Short EMA')])

    if 'EMA Long' in elems:
        fig_data.extend([go.Scatter(x=df.index, y=df['longEMA'], mode='lines', name='Long EMA')])

    if 'Fibonacci' in elems:
        fig_data.extend(
            [go.Scatter(x=df.index, y=df[f], mode='lines', opacity=0.5, name=f, line=dict(dash='dash')) for f in df.columns if 'fibonacci' in f]
        )

    fig = go.Figure(data=fig_data)
    fig.update_layout(title=t,
                      yaxis_title='USD')

    fig.update_xaxes(rangebreaks=[{'pattern': 'day of week', 'bounds': [6, 1]}])

    return fig


st.markdown("<h2 style='text-align: center; color: grey;'> Data Query from Yahoo Finance </h2>", unsafe_allow_html=True)

config_params = cp(analysis_selected).config['analysisParameters']
st.dataframe(cp(analysis_selected).df_query, hide_index=True)
st.dataframe(cp(analysis_selected).df_analysis, hide_index=True)
st.divider()

check_data = 0
haveData = False

for t in cp(analysis_selected).query_tickers:
    sd = cp(analysis_selected).query_start.strftime('%Y%m%d')
    ed = cp(analysis_selected).query_end.strftime('%Y%m%d')
    if '{0}_{1}_{2}.csv'.format(t, sd, ed) in os.listdir(cp(analysis_selected).data_path):
        check_data += 1

if check_data == len(cp(analysis_selected).query_tickers):
    data = read_data()
else:
    data = run_query()

t1, t2 = st.tabs(['Data Tables', 'Charts'])

with t1:
    st.markdown("<h2 style='text-align: center; color: grey;'> Raw Data Tables </h2>", unsafe_allow_html=True)
    for t in cp(analysis_selected).query_tickers:
        st.write('Data for Ticker: {}'.format(t))
        st.dataframe(data[t])

with t2:
    st.markdown("<h2 style='text-align: center; color: grey;'> Data Charts </h2>", unsafe_allow_html=True)

    t = st.selectbox(label='Select Ticker', options=cp(analysis_selected).query_tickers)

    analysis_options = acg.list_analyses + acs.list_analyses



    sd = st.date_input(label='Select Chart Start Date', value=None,
                       min_value=pd.to_datetime(cp(analysis_selected).query_start),
                       max_value=pd.to_datetime(cp(analysis_selected).query_end)
                       )

    ed = st.date_input(label='Select Chart End Date', value=None,
                       min_value=pd.to_datetime(cp(analysis_selected).query_start),
                       max_value=pd.to_datetime(cp(analysis_selected).query_end)
                       )

    if sd != None and ed != None:
        elements = st.multiselect(label='Select one or more additional chart elements', options=analysis_options)

        t_data = addChartElement(data[t], elements)

        t_data = t_data.loc[sd:ed, :]

        t_data = addChartElementSubset(t_data, elements)

        showChart = st.button(label='Show Chart?')

        if showChart:
            st.plotly_chart(figure_or_data=makeFig(t, t_data, elements), theme='streamlit', use_container_width=True, on_select='ignore')
