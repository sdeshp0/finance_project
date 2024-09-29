import os, sys
import ProjectPaths
from Props import ConfigProps as cp

root_ = ProjectPaths.C_PATH_BASE
print(root_)
os.chdir(root_)
sys.path.append(root_)

import streamlit as st
st.set_page_config(layout='centered', page_title='AnalysisConfiguration', initial_sidebar_state='collapsed')

import yaml
import time
import warnings
import pandas as pd
import pytz
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

    cfg_dir = cp(analysis_selected).cfg_path
    yaml_config_ = cp(analysis_selected).cfg_file

    config_ = cp(analysis_selected).config

def update_config(key, preset=None):

    if key == 'update_query':
        updates_ = st.session_state['query_df']
        print(updates_)

        for idx, _ in updates_['edited_rows'].items():
            for k, v in _.items():
                if k in ['startDate', 'endDate']:
                    config_['queryParameters'][k] = v.strftime('%Y-%m-%d %H:%M:%S')
                elif k == 'selectedTickers':
                    config_['queryParameters'][k] = v.split(', ')
                else:
                    config_['queryParameters'][k] = v

    if key == 'update_params':
        updates_ = st.session_state['analysis_df']
        print(updates_)

        for idx, _ in updates_['edited_rows'].items():
            for k, v in _.items():
                config_['queryParameters'][k] = v

    if key == 'apply_preset':
        sd = cp(analysis_selected).query_start
        ed = cp(analysis_selected).query_end

        if preset == 'Past 7 days':
            sd = datetime.now() - timedelta(days=7)
            ed = datetime.now()
        if preset == 'Past 30 days':
            sd = datetime.now() - timedelta(days=30)
            ed = datetime.now()
        if preset == 'Past Year':
            sd = datetime.now() - timedelta(days=365)
            ed = datetime.now()

        config_['queryParameters']['startDate'] = sd.strftime('%Y-%m-%d 00:00:00')
        config_['queryParameters']['endDate'] = ed.strftime('%Y-%m-%d 00:00:00')

    with open(yaml_config_, 'w') as f:
        yaml.dump(config_, f, default_flow_style=False)
        f.close()

        st.rerun()

def form_update_query(data):

    with st.form(key='analysis_query'):

        st.write('Review query parameters')

        df = pd.DataFrame(index=[0], columns=['startDate', 'endDate', 'analysisTZ', 'selectedTickers'])
        for c in df.columns:
            if c in ['startDate', 'endDate']:
                df.loc[0, c] = pd.to_datetime(data[c])
            elif c == 'selectedTickers':
                df.loc[0, c] = ', '.join(data[c])
            else:
                df.loc[0, c] = data[c]

        result = st.data_editor(data=df,
                                column_config={
                                    'startDate': st.column_config.DateColumn('Start Date',
                                                                             format='YYYY-MM-DD',
                                                                             disabled=False,
                                                                             required=True),
                                    'endDate': st.column_config.DateColumn('End Date',
                                                                           format='YYYY-MM-DD',
                                                                           disabled=False,
                                                                           required=True),
                                    'analysisTZ': st.column_config.SelectboxColumn('TimeZone',
                                                                                   options=pytz.common_timezones_set),
                                    'selectedTickers': st.column_config.TextColumn('Ticker List',
                                                                                   disabled=False,
                                                                                   required=True,
                                                                                   help='Enter list of tickers separated by comma')
                                },
                                num_rows='fixed',
                                use_container_width=True,
                                key='query_df',
                                hide_index=True)

        button = st.form_submit_button(label='Save')
        return button, result

def form_update_params(data):

    with st.form(key='analysis_params'):

        st.write('Review analysis parameters')

        df = pd.DataFrame(index=[0], columns=['smaShort', 'smaLong', 'emaShort', 'emaLong'])
        for c in df.columns:
            df.loc[0, c] = data[c]

        result = st.data_editor(data=df,
                                column_config={
                                    'smaShort': st.column_config.NumberColumn('Short SMA Period',
                                                                             disabled=False,
                                                                             required=True),
                                    'smaLong': st.column_config.NumberColumn('Long SMA Period',
                                                                                    disabled=False,
                                                                                    required=True),
                                    'emaShort': st.column_config.NumberColumn('Short EMA Period',
                                                                             disabled=False,
                                                                             required=True),
                                    'emaLong': st.column_config.NumberColumn('Long EMA Period',
                                                                             disabled=False,
                                                                             required=True),
                                },
                                num_rows='fixed',
                                use_container_width=True,
                                key='analysis_df',
                                hide_index=True)

        button = st.form_submit_button(label='Save')
        return button, result

t1, t2, t3 = st.tabs(['Query Config', 'Parameter Config', 'View Yaml'])

if config_ != None:

    with t1:
        st.markdown("<h2 style='text-align: center; color: grey;'> Set Query Config </h2>", unsafe_allow_html=True)

        config_query = config_['queryParameters']

        button_query, result = form_update_query(data=config_query)

        if button_query:
            st.toast('SAVED! (Query Parameters)', icon='✅')
            time.sleep(2)
            update_config(key='update_query')

        st.write('You can update the Start/End dates in the editor above, or you can use the following presets:')
        date_preset = st.selectbox(label='Common Presets', options=['Past 7 days', 'Past 30 days', 'Past Year'])

        apply_preset = st.button(label='Use preset?')

        if apply_preset:
            st.toast('SAVED! Date Preset', icon='✅')
            time.sleep(2)
            update_config(key='apply_preset', preset=date_preset)

    with t2:
        st.markdown("<h2 style='text-align: center; color: grey;'> Set Parameter Config </h2>", unsafe_allow_html=True)

        config_params = config_['analysisParameters']

        button_analysis, result = form_update_params(data=config_params)

        if button_analysis:
            st.toast('SAVED! (Analysis Parameters)', icon='✅')
            time.sleep(2)
            update_config(key='update_params')

    with t3:
        config_
