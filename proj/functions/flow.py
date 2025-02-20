import pandas as pd
import numpy as np

def get_runoff_duration(formatted_data):
    times = formatted_data.dropna().index.to_numpy()
    runoff_duration = (times[-1] - times[0]).astype('timedelta64[s]').astype('float64')/3600
    return runoff_duration

def get_runoff_volume(formatted_data, unit = "s"):
    runoff_volume_segments = formatted_data.dropna()
    runoff_volume_segments = runoff_volume_segments.rolling(window = 2).apply(trapezoid, kwargs = {"unit": unit})
    runoff_volume = runoff_volume_segments.sum()
    return runoff_volume
    
def trapezoid(data_window, unit):
    units = {
        "min": "m",
        "m": "m",
        "s": "s",
        "sec": "s"
    }
    diff = data_window.index.to_series().diff().dt.total_seconds().iloc[-1]
    return data_window.mean()*diff

def get_peak_flow_rate(formatted_data, minute_window=5):
    # assumes data starts at regular intervals i.e. if 15 min frequency, then data is taken at 12:00, 12:15, etc.
    # as opposed to 12:02, 12:17, etc.
    data = formatted_data.dropna()
    
    # if data has a longer frequency than the minute_window, then we need to interpolate to minute_window frequency
    # in that case, the peak_flow_rate is just the max of the minute_window interpolated data
    
    if round((data.index[1] - data.index[0]).seconds/60) > minute_window:
        time_index = pd.date_range(start = data.index.floor('T')[0], end = data.index.ceil('T')[-1], freq = f"{minute_window}T")
        interpolated_data = pd.Series(data = data, index = time_index).interpolate()
        peak_flow_rate = interpolated_data.max()
        return peak_flow_rate
    
    # otherwise, we take the rolling average over the minute_window and take the max of that series
    peak_flow_rate = data.rolling(window = f"{minute_window}T").mean().max()
    return peak_flow_rate

def get_percent_change(inflow1_value, outflow_value, inflow2_value = None, bypass_value = None):
    percent_change = []
    if inflow2_value is None and bypass_value is None:
        for inflow1, outflow in zip(inflow1_value, outflow_value):
            percent_change.append((inflow1 - outflow)/(inflow1)*100)

    elif inflow2_value is not None and bypass_value is None:
        for inflow1, outflow, inflow2 in zip(inflow1_value, outflow_value, inflow2_value):
            percent_change.append((inflow1 + inflow2 - outflow)/(inflow1 + inflow2)*100)
    
    elif bypass_value is not None and inflow2_value is None:
        for inflow1, outflow, bypass in zip(inflow1_value, outflow_value, bypass_value):
            percent_change.append((inflow1 + bypass - outflow)/(inflow1 + bypass)*100)
    else:
        for inflow1, outflow, inflow2, bypass in zip(inflow1_value, outflow_value, inflow2_value, bypass_value):
            percent_change.append((inflow1 + inflow2 + bypass - outflow)/(inflow1 + inflow2 + bypass)*100)
        
    return percent_change

