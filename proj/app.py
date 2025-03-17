from flask import Flask
from flask import session, request, send_from_directory, render_template, redirect, send_file, session, jsonify
import os, json
import pandas as pd
import numpy as np
from .utils.utils import *
from .functions.rain import get_first_rain, get_last_rain, get_avg_rainfall_intensity, get_peak_rainfall_intensity, get_total_rainfall, get_total_rainfall_duration, get_antecedent_dry_period
from .functions.flow import get_runoff_volume, get_peak_flow_rate, get_runoff_duration, get_percent_change
from .functions.infiltration import *


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
    print("time units")
    print(time_units)
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
    print("body for flow api")
    print(body)

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

@app.route("/api/infiltration", methods=['POST'])
def infiltration():
    print("infiltration called")
    try:
        # Get JSON input from the POST request
        request_data = request.get_json()
        data = request_data.get("data")
        smoothing_window = int(request_data.get("SMOOTHING_WINDOW"))
        regression_window = int(request_data.get("REGRESSION_WINDOW"))
        regression_threshold = float(request_data.get("REGRESSION_THRESHOLD"))

        print("Parameters:", smoothing_window, regression_window, regression_threshold)

        # Override global parameters for this request
        global SMOOTHING_WINDOW, REGRESSION_WINDOW, REGRESSION_THRESHOLD
        SMOOTHING_WINDOW = smoothing_window
        REGRESSION_WINDOW = regression_window
        REGRESSION_THRESHOLD = regression_threshold

        # Create a dataframe from the provided data and convert the datetime column
        df = pd.DataFrame(data)
        print("Original datetime column:", df['datetime'])
        df['datetime'] = pd.to_datetime(
            df['datetime'].astype(str).str.replace(r'^(\d{4}-\d{2}-\d{2})$', r'\1 00:00:00', regex=True),
            format="%Y-%m-%d %H:%M:%S"
        )

        # Prepare dictionaries to store results for each piezometer column
        best_windows = {}
        best_params_list = {}
        best_r_squared_list = {}
        calc_results = {}

        # Dynamically determine which columns to process (all except 'datetime')
        piezometer_cols = [col for col in df.columns if col != 'datetime']

        for piez in piezometer_cols:
            # Create a smoothed column name that replaces spaces with underscores
            smoothed_col = f'smooth_{piez.replace(" ", "_")}'
            df[smoothed_col] = smooth_timeseries(df[piez], kernel_size=SMOOTHING_WINDOW)
            
            # Fit the exponential decay model using the provided regression window size
            best_window, best_params, best_fit, best_r_squared = fit_exponential_decay(
                df['datetime'],
                df[smoothed_col],
                REGRESSION_WINDOW
            )
            
            if best_window:
                best_windows[piez] = best_window
                best_params_list[piez] = best_params.tolist() if best_params is not None else None
                best_r_squared_list[piez] = best_r_squared
                
                # Identify the best window start and end times
                window_start = best_window[0][0]
                window_end = best_window[0][-1]
                best_window_indexes = df.index[(df['datetime'] >= window_start) & (df['datetime'] <= window_end)]
                
                # Calculate infiltration rate parameters
                k_value = best_params[1] * 3600  # Convert k from 1/hr to 1/s
                y_average = df.loc[best_window_indexes, smoothed_col].mean()
                delta_x = pd.Timedelta(window_end - window_start).total_seconds() / 3600
                infiltration_rate = k_value * y_average
                
                print(f"Best window for {piez}: {window_start} - {window_end}")
                print(f"Average infiltration rate during the best window for {piez}: {infiltration_rate:.2f} cm/hr")
                print(f"Duration of the best window for {piez}: {delta_x:.0f} hrs")
                print(f"Average depth during the best window for {piez}: {y_average:.2f} cm")
                
                # Compute extended time series and best fit line for plotting
                buffer_time = pd.Timedelta(minutes=720)
                extended_time = pd.date_range(start=window_start - buffer_time, 
                                              end=window_end + buffer_time, freq='T')
                extended_time_numeric = (extended_time - window_start).total_seconds().to_numpy()
                best_fit_line = exponential_decay(extended_time_numeric, *best_params)
                
                # Store computed values for this piezometer
                calc_results[piez] = {
                    "extended_time": [pd.Timestamp(x) for x in extended_time],
                    "best_fit_line": best_fit_line.tolist(),
                    "infiltration_rate": infiltration_rate,
                    "delta_x": delta_x,
                    "y_average": y_average
                }
            else:
                best_windows[piez] = None
                best_params_list[piez] = None
                best_r_squared_list[piez] = None
                calc_results[piez] = None

        # Convert the datetime column to ISO format for JSON serialization.
        df['datetime'] = df['datetime'].apply(lambda x: x.isoformat())
        dataframe_json = df.to_dict(orient='records')

        # Convert the best_windows results (which may include numpy arrays) into serializable lists.
        converted_best_windows = {}
        for piez, window in best_windows.items():
            if window is not None:
                window_time, window_depth = window
                window_time_str = [pd.Timestamp(x).isoformat() for x in window_time]
                window_depth_list = window_depth.tolist()
                converted_best_windows[piez] = {
                    "window_time": window_time_str,
                    "window_depth": window_depth_list
                }
            else:
                converted_best_windows[piez] = None

        result = {
            "dataframe": dataframe_json,
            "best_windows": converted_best_windows,
            "best_params_list": best_params_list,
            "best_r_squared_list": best_r_squared_list,
            "calc_results": calc_results
        }
        return jsonify(result)
    except Exception as e:
        # Return error message and a 500 status code if something goes wrong
        return jsonify({"error": str(e)}), 500
