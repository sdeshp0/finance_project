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

    yaml_config_ = os.path.join(cfg_dir, '{}.yaml'.format(analysis_selected))

    with open(yaml_config_, 'r') as f:
        config_ = yaml.safe_load(f)
    f.close()

def update_config(key, status):

    status_ = config_['status']

    if key == 'update_analysis_name':
        config_['analysisName'] = st.session_state['analysis_name']
        st.toast('SAVED! (Analysis Name)', icon='✅')

        if int(status_) <= int(status):
            config_['status'] = int(status) + 1

    if key == 'update_params':
        updates_ = st.session_state['params_df']
        print(updates_)

        for idx, _ in updates_['edited_rows'].items():
            for k, v in _.items():
                if k in ['startDate', 'endDate']:
                    config_['analysisParameters'][k] = v.strftime('%Y-%m-%d %H:%M:%S')
                elif k == 'selectedTickers':
                    config_['analysisParameters'][k] = v.split(', ')
                else:
                    config_['analysisParameters'][k] = v

        config_['queriedData'] = 0

    with open(yaml_config_, 'w') as f:
        yaml.dump(config_, f, default_flow_style=False)
        f.close()

    if key != 'update_analysis_name':
        st.rerun()

def form_update_params(data):

    with st.form(key='analysis_params'):

        st.write('Review configuration parameters')

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
                                key='params_df',
                                hide_index=True)

        button = st.form_submit_button(label='Save')
        return button, result

t1, t2 = st.tabs(['Edit Config', 'View Yaml'])

if config_ != None:

    with t1:
        st.markdown("<h2 style='text-align: center; color: grey;'> Edit Analysis Config </h2>", unsafe_allow_html=True)

        analysis_name = st.text_input(label='Analysis Name',
                                      placeholder='enter name of analysis',
                                      value=config_['analysisName'],
                                      key='analysis_name',
                                      on_change=update_config,
                                      args=['update_analysis_name', 0])

        status_ = int(config_['status'])

        if status_ > 0:

            config_params = config_['analysisParameters']

            button_analysis, result = form_update_params(data=config_params)

            if button_analysis:
                st.toast('SAVED! (Analysis Parameters)', icon='✅')
                time.sleep(2)
                update_config(key='update_params', status=status_)

    with t2:
        config_
