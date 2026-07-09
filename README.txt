Modular cerebral autoregulation dashboard

Run order:
1. Keep patient_registry.csv in this folder.
2. Keep source patient datasets in datasets/ folder.
3. Run writer.py in one terminal:
   python writer.py
4. Run dashboard in another terminal:
   streamlit run dashboard_v4_prx.py

Main files:
- dashboard_v4_prx.py: main Streamlit app with Live Monitoring and PRx History tabs.
- config.py: all paths, colors, speed options, graph windows, and settings.
- stream_control.py: dataset/sheet/speed controls and stream_config.json updates.
- patient_info.py: maps selected dataset file to patient display using patient_registry.csv.
- live_data_reader.py: reads live_data.csv and parses TTDate + TTTime.
- ui/theme.py: CSS, font sizes, dark-mode title styling.
- ui/cards.py: metric cards, side-value cards, patient box, autoregulation badge.
- ui/plots.py: graph-window cropping and Plotly chart rendering.
- prx_history.py: PRx history, tags, durations, good/bad segments.
- analysis_1.py: core CPP, PRx, CPPopt calculations.
