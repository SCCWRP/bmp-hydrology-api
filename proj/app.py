from flask import Flask
from flask import session, request, send_from_directory, render_template, redirect, send_file, session, jsonify
import os, json
import pandas as pd
import numpy as np
from .utils.utils import *
from .functions.rain import get_first_rain, get_last_rain, get_avg_rainfall_intensity, get_peak_rainfall_intensity, get_total_rainfall, get_total_rainfall_duration, get_antecedent_dry_period
from .functions.flow import get_runoff_volume, get_peak_flow_rate, get_runoff_duration, get_percent_change

app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_APP_SECRET_KEY")

valid_keys = {
    "inflow1" : {"datetime", "flow", "time_unit"},
    "inflow2": {"datetime", "flow", "time_unit"}, 
    "outflow": {"datetime", "flow", "time_unit"}, 
    "bypass": {"datetime", "flow", "time_unit"}, 
    "rain": {"datetime", "rain"}
}

bmp_drain_interval = 12


@app.route("/", methods=['GET'])
def main():
    return render_template("index.html")

@app.route("/api/docs", methods = ['GET'])
def get_docs():
    return render_template("swaggerui.html")

@app.route("/api/rain", methods=['POST'])
def rain():
    # TODO check request.args for date or parameter filtering?
    try:
        data = load_data(request, valid_keys)
    except ValueError as err:
        print(err)
        response = app.response_class(
            response = 'Invalid data format',
            status = 400,
            mimetype = 'application/json'
        )
        return response
    # need data in a time series with regular frequency/interval for pandas window functions to work properly
    # with time windows e.g. get the mean over a 5 minute interval
    formatted_rain_data = format_data(data)
    # calculate statistics, add them to a dataframe to more easily manipulate them
    # each statistic is an array with the number of entries equal to the number
    # of rain events in the data 
    first_rain = get_first_rain(formatted_rain_data, hour_window = bmp_drain_interval)
    last_rain = get_last_rain(formatted_rain_data, first_rain, hour_window = bmp_drain_interval)
    total_rainfall = get_total_rainfall(formatted_rain_data, first_rain, last_rain)
    total_rainfall_duration = get_total_rainfall_duration(first_rain, last_rain)
    avg_rainfall_intensity = get_avg_rainfall_intensity(total_rainfall, total_rainfall_duration)
    peak_5_min_rainfall_intensity = get_peak_rainfall_intensity(formatted_rain_data, first_rain, last_rain)
    peak_10_min_rainfall_intensity = get_peak_rainfall_intensity(formatted_rain_data, first_rain, last_rain, minute_window = 10)
    peak_60_min_rainfall_intensity = get_peak_rainfall_intensity(formatted_rain_data, first_rain, last_rain, minute_window = 60)
    antecedent_dry_period = get_antecedent_dry_period(first_rain, last_rain)

    df = pd.DataFrame({
        "first_rain": np.datetime_as_string(first_rain, unit = 's'),
        "last_rain": np.datetime_as_string(last_rain, unit = 's'),
        "total_rainfall": total_rainfall,
        "avg_rainfall_intensity": avg_rainfall_intensity,
        "peak_5_min_rainfall_intensity": peak_5_min_rainfall_intensity,
        "peak_10_min_rainfall_intensity": peak_10_min_rainfall_intensity,
        "peak_60_min_rainfall_intensity": peak_60_min_rainfall_intensity,
        "antecedent_dry_period": antecedent_dry_period
    })

    # don't care about single tip events
    df = df[first_rain != last_rain].reset_index(drop = True)
    # convert the dataframe to a json format, using the pandas to_json() method
    # with slight changes afterward
    statistics = format_statistics(df)
    
    body = {
        "statistics": statistics, 
    }

    return jsonify(body)

@app.route("/api/flow", methods=['POST'])
def flow():
    try:
        data = load_data(request, valid_keys)
    except ValueError as err:
        print(err)
        response = app.response_class(
            response = 'Invalid data format',
            status = 400,
            mimetype = 'application/json'
        )
        return response

    time_units = {}
    for data_type, data_dict in data.items():
        time_units[data_type] = data_dict.pop('time_unit')
        
        if not isinstance(time_units[data_type], str):
            time_units[data_type] =  list(set(time_units[data_type]))[0]

    formatted_data = {}
    for data_type, df in data.items():
        formatted_data[data_type] = format_data(df)
    
    statistics = {}
    for data_type, series in formatted_data.items():
        df = pd.DataFrame({
            "runoff_volume": [get_runoff_volume(series, unit = time_units[data_type])],
            "runoff_duration" : [get_runoff_duration(series)],
            "peak_flow_rate" : [get_peak_flow_rate(series)],
            "start_time" : [np.datetime_as_string(series.index.to_numpy()[0], unit = 's')],
            "end_time" : [np.datetime_as_string(series.index.to_numpy()[-1], unit = 's')]
        })
        statistics[data_type] = format_statistics(df)
    
    flow_keys_in_data = set(valid_keys.keys()).intersection(set(formatted_data.keys()))
    
    if flow_keys_in_data == {"inflow1", "outflow"}:
        statistics["percent_change_volume"] = get_percent_change(
            inflow1_value = statistics["inflow1"]["runoff_volume"], 
            outflow_value = statistics["outflow"]["runoff_volume"]
        )
        statistics["percent_change_flow_rate"] = get_percent_change(
            inflow1_value = statistics["inflow1"]["peak_flow_rate"], 
            outflow_value = statistics["outflow"]["peak_flow_rate"]
        )
    
    elif flow_keys_in_data == {"inflow1", "outflow", "bypass"}:
        statistics["percent_change_volume"] = get_percent_change(
            inflow1_value = statistics["inflow1"]["runoff_volume"], 
            outflow_value = statistics["outflow"]["runoff_volume"],
            bypass_value = statistics["bypass"]["runoff_volume"]
        )

    elif flow_keys_in_data == {"inflow1", "inflow2", "bypass", "outflow"}:
        statistics["percent_change_volume"] = get_percent_change(
            inflow1_value = statistics["inflow1"]["runoff_volume"], 
            inflow2_value = statistics["inflow2"]["runoff_volume"], 
            outflow_value = statistics["outflow"]["runoff_volume"],
            bypass_value = statistics["bypass"]["runoff_volume"]
        )


    body = {
        "statistics": statistics
    }
    return jsonify(body)

@app.route("/api/rainflow", methods=['POST'])
def rainflow():
    try:
        data = load_data(request, valid_keys)
    except ValueError as err:
        print(err)
        response = app.response_class(
            response = 'Invalid data format',
            status = 400,
            mimetype = 'application/json'
        )
        return response
    
    formatted_data = {}
    for data_type, df in data.items():
        formatted_data[data_type] = format_data(df)
    
    formatted_rain_data = formatted_data['rain']

    first_rain = get_first_rain(formatted_rain_data, hour_window = bmp_drain_interval)
    last_rain = get_last_rain(formatted_rain_data, first_rain, hour_window = bmp_drain_interval)
    total_rainfall = get_total_rainfall(formatted_rain_data, first_rain, last_rain)
    total_rainfall_duration = get_total_rainfall_duration(first_rain, last_rain)
    avg_rainfall_intensity = get_avg_rainfall_intensity(total_rainfall, total_rainfall_duration)
    peak_5_min_rainfall_intensity = get_peak_rainfall_intensity(formatted_rain_data, first_rain, last_rain)
    peak_10_min_rainfall_intensity = get_peak_rainfall_intensity(formatted_rain_data, first_rain, last_rain, minute_window = 10)

    rain_df = pd.DataFrame({
        "first_rain": np.datetime_as_string(first_rain, unit = 's'),
        "last_rain": np.datetime_as_string(last_rain, unit = 's'),
        "total_rainfall": total_rainfall,
        "avg_rainfall_intensity": avg_rainfall_intensity,
        "peak_5_min_rainfall_intensity": peak_5_min_rainfall_intensity,
        "peak_10_min_rainfall_intensity": peak_10_min_rainfall_intensity
    })

    # don't care about single tip events
    rain_df = rain_df[first_rain != last_rain].reset_index(drop = True)
    
    statistics = {}
    statistics['rain'] = format_statistics(rain_df)

    rain_df['last_rain_plus_interval'] = pd.to_datetime(rain_df['last_rain']) + pd.Timedelta(bmp_drain_interval, unit = 'hours')

    valid_flow_keys = {x for x in valid_keys if "flow" in valid_keys[x]}
    flow_keys_in_data = valid_flow_keys.intersection(set(formatted_data.keys()))
    formatted_flow_data = {x: formatted_data[x] for x in flow_keys_in_data}

    time_units = {}
    for data_type, data_dict in data.items():
        time_units[data_type] = data_dict.pop('time_unit')

    for data_type, series in formatted_flow_data.items():
        flow_df = pd.DataFrame({
            "runoff_volume": rain_df.apply(lambda x: get_runoff_volume(series[x.first_rain: x.last_rain_plus_interval], unit = time_units[data_type]), axis = 1),
            "runoff_duration" : rain_df.apply(lambda x: get_runoff_duration(series[x.first_rain: x.last_rain_plus_interval]), axis = 1),
            "peak_flow_rate" : rain_df.apply(lambda x: get_peak_flow_rate(series[x.first_rain: x.last_rain_plus_interval]), axis = 1)
        })
        statistics[data_type] = format_statistics(flow_df)
    
    if flow_keys_in_data == {"inflow1", "outflow"}:
        statistics["percent_change_volume"] = get_percent_change(
            inflow1_value = statistics["inflow1"]["runoff_volume"], 
            outflow_value = statistics["outflow"]["runoff_volume"]
        )
        statistics["percent_change_flow_rate"] = get_percent_change(
            inflow1_value = statistics["inflow1"]["peak_flow_rate"], 
            outflow_value = statistics["outflow"]["peak_flow_rate"]
        )
    
    elif flow_keys_in_data == {"inflow1", "outflow", "bypass"}:
        statistics["percent_change_volume"] = get_percent_change(
            inflow1_value = statistics["inflow1"]["runoff_volume"], 
            outflow_value = statistics["outflow"]["runoff_volume"],
            bypass_value = statistics["bypass"]["runoff_volume"]
        )

    elif flow_keys_in_data == {"inflow1", "inflow2", "bypass", "outflow"}:
        statistics["percent_change_volume"] = get_percent_change(
            inflow1_value = statistics["inflow1"]["runoff_volume"], 
            inflow2_value = statistics["inflow2"]["runoff_volume"], 
            outflow_value = statistics["outflow"]["runoff_volume"],
            bypass_value = statistics["bypass"]["runoff_volume"]
        )

    body = {"statistics": statistics}
    return jsonify(body)
