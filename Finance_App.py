import os, sys
import ProjectPaths

root_ = ProjectPaths.C_PATH_BASE
print(root_)
os.chdir(root_)
sys.path.append(root_)

import streamlit as st
st.set_page_config(layout='centered', page_title='Analysis Selection', initial_sidebar_state='collapsed')

import yaml
import warnings

#Suppress FutureWarning messages
warnings.simplefilter(action='ignore', category=FutureWarning)
config_=None

st.markdown("<h1 style='text-align: center; color: grey;'> Finance App </h1>", unsafe_allow_html=True)
st.divider()

st.markdown("<p style='text-align: center; color: grey;'> Welcome to the Finance App </p>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: grey;'> The Finance App is a data collection and visualization tool "
            "that is intended to help automate stock analyses.</p>", unsafe_allow_html=True)
st.divider()

st.markdown("<p style='text-align: center; color: grey;'> To begin using the app, please select an analysis to run. "
            "The app will automatically link to the location of the analysis. "
            "Once you have made your selection, please use the '>' button on the top left of the page to navigate to "
            "the different modules.</p>", unsafe_allow_html=True)
st.divider()

t1, t2 = st.tabs(['Analysis Selection', 'About'])

with t1:
    st.markdown("<h2 style='text-align: center; color: grey;'> Analysis Selection </h2>", unsafe_allow_html=True)
    st.write('Please select an analysis. If you want to start a new analysis, select "Start new analysis".')

    select_analysis = st.selectbox(label='What would you like to do?', options=['Start a new analysis',
                                                                             'Open existing analysis'])

    if select_analysis == 'Start a new analysis':
        analysis_selected = st.text_input(label='Enter analysis name', value='NewAnalysis*', help='Please use a name '
                                                                                                  'that is appropriate'
                                                                                                  'for a folder name')

        st.write('Please click the button below to start the creation of a new analysis.')
        create_analysis = st.button(label='Start a new analysis named {}?'.format(analysis_selected))

        if create_analysis:

            if os.path.isdir(os.path.join(ProjectPaths.C_PATH_ANALYSIS, '{}'.format(analysis_selected))):
                st.error('Please check to make sure if this is already an existing analysis')
                st.stop()
            else:
                st.write('Analysis files will be saved in the path shown below:')
                st.write('{}'.format(os.path.join(ProjectPaths.C_PATH_ANALYSIS, '{}'.format(analysis_selected))))

                os.mkdir(os.path.join(ProjectPaths.C_PATH_ANALYSIS, '{}'.format(analysis_selected)))
                os.mkdir(os.path.join(ProjectPaths.C_PATH_ANALYSIS, '{}'.format(analysis_selected), 'config'))
                os.mkdir(os.path.join(ProjectPaths.C_PATH_ANALYSIS, '{}'.format(analysis_selected), 'data'))
                st.success('Created a new directory for this analysis')

            yaml_template_ = os.path.join(ProjectPaths.C_PATH_TEMPLATES, 'analysis_default.yaml')
            yaml_config_ = os.path.join(ProjectPaths.C_PATH_ANALYSIS, '{}'.format(analysis_selected), 'config',
                                        '{}.yaml'.format(analysis_selected))

            with open(yaml_template_, 'r') as f:
                template_config_ = yaml.safe_load(f)
            f.close()

            with open(yaml_config_, 'w') as f:
                yaml.dump(template_config_, f, default_flow_style=False)

            st.write('Analysis Selected: {}'.format(analysis_selected))
    else:
        existing_analysis = [x for x in os.listdir(ProjectPaths.C_PATH_ANALYSIS)]

        analysis_selected = st.selectbox(label='Which project would you like to work on?', options=existing_analysis,
                                         key='analysis_sbox')

        st.write('Analysis Selected: {}'.format(analysis_selected))

    st.write('After you have selected a project, please use the sidebar to choose a module')
    st.session_state['current_analysis'] = analysis_selected

with t2:
    st.markdown("<h2 style='text-align: center; color: grey;'> Release Ver 0.1 </h2>", unsafe_allow_html=True)

    st.subheader('Python')
    st.write(sys.version)
    st.write(sys.executable)
    st.divider()

    st.subheader('Streamlit')
    st.write(st.__version__)
    st.write(st.__path__[0])
    st.divider()

    st.subheader('Author')
    st.write('Siddharth Deshpande (siddharthdes.new@gmail.com')
    st.divider()