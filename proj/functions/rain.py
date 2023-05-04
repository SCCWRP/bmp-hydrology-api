import pandas as pd
import numpy as np

def get_first_rain(formatted_data, hour_window = 12):
    # expects formatted data from format_data function
    # if rain depth is 0, then no rain, but for the purposes of this function
    # it is convenient to convert these to NaNs
    # need deep copy of data in order to avoid mutating original data
    tmp = formatted_data.copy()
    tmp[tmp == 0] = np.nan

    # get a series of the sum of rain depth for the previous 12 hours (default hour_window, inclusive)
    # if no rain in the past 12 hours, value will be NaN
    # example: rain_gauge                       past_12_hours
    #          2021-09-24 16:24:30      NaN     2021-09-24 16:24:30      NaN
    #          2021-09-24 16:24:40    0.508     2021-09-24 16:24:40    0.508
    #          2021-09-24 16:24:50    1.524     2021-09-24 16:24:50    2.032
    #          2021-09-24 16:25:00    1.016     2021-09-24 16:25:00    3.048
    #          2021-09-24 16:25:10      NaN     2021-09-24 16:25:10    3.048
    #          2021-09-24 16:25:20      NaN     2021-09-24 16:25:20    3.048
    #          2021-09-24 16:25:30    0.762     2021-09-24 16:25:30    3.810
    
    past_hours = tmp.rolling(window = f"{hour_window}H").sum().apply(lambda x: 0 if x < 1e-9 else x)
    # first rain occurs when the sum of the past 12 hours of rain depth changes from 
    # 0 to a number. can compare this with a shifted-down version of the same series
    # to find the time at which this occurs
    # example: past_12_hours                    past_12_hours.shift()
    #          2021-09-24 16:24:30      NaN     2021-09-24 16:24:30      NaN
    #      ->  2021-09-24 16:24:40    0.508     2021-09-24 16:24:40      NaN
    #          2021-09-24 16:24:50    2.032     2021-09-24 16:24:50    0.508
    #          2021-09-24 16:25:00    3.048     2021-09-24 16:25:00    2.032
    #          2021-09-24 16:25:10    3.048     2021-09-24 16:25:10    3.048
    #          2021-09-24 16:25:20    3.048     2021-09-24 16:25:20    3.048
    #          2021-09-24 16:25:30    3.810     2021-09-24 16:25:30    3.810

    first_rain = past_hours[(~past_hours.isna()) & (past_hours.shift().isna())].index.values
    return first_rain

def get_last_rain(formatted_data, first_rain, hour_window = 12):
    # expects formatted data from format_data function
    tmp = formatted_data.copy()
    tmp[tmp == 0] = np.nan

    # similar to get_first_rain, but need to reverse the rain_gauge series 
    # and reverse again in order to get the sum of the next 12 (default hour_window) hours
    next_hours = tmp[::-1].rolling(window = f"{hour_window}H").sum()[::-1].apply(lambda x: 0 if x < 1e-9 else x)
    last_rain = next_hours[(~next_hours.isna()) & (next_hours.shift(-1).isna())].index.values
    # if len(last_rain) != len(first_rain), then we reached the end of the data before 
    # the rain event ended, so add the last timestamp as the last last_rain
    if len(last_rain) != len(first_rain):
        last_rain = np.append(last_rain, tmp.index.to_numpy()[-1])
    return last_rain

def get_total_rainfall_duration(first_rain, last_rain):
    total_rainfall_duration = (last_rain - first_rain) / np.timedelta64(1, "h")
    return total_rainfall_duration

def get_total_rainfall(formatted_data, first_rain, last_rain):
    first_last = pd.DataFrame({"first_rain":first_rain, "last_rain":last_rain})
    total_rainfall = first_last.apply(lambda x: formatted_data[x.first_rain:x.last_rain].sum(), axis = 1).to_numpy()
    return total_rainfall

def get_avg_rainfall_intensity(total_rainfall, total_rainfall_duration):
    avg_rainfall_intensity = total_rainfall/total_rainfall_duration
    avg_rainfall_intensity[avg_rainfall_intensity == np.inf] = np.nan
    return avg_rainfall_intensity

def get_peak_rainfall_intensity(formatted_data, first_rain, last_rain, minute_window = 5):
    first_last = pd.DataFrame({"first_rain":first_rain, "last_rain":last_rain})
    # peak_rainfall_intensity = first_last.apply(
    #     lambda x: formatted_data[x.first_rain: x.last_rain].rolling(window = f"{minute_window}T").apply(custom_mean, raw = True, kwargs = {"minute_window": minute_window})[calculate_start_time(x.first_rain, x.last_rain, minute_window): ].max(), 
    #     axis = 1
    # )
    peak_rainfall_intensity = first_last.apply(
        lambda x: formatted_data[x.first_rain: x.last_rain].rolling(window = f"{minute_window}T").sum().apply(lambda x: 0 if x < 1e-9 else x)[calculate_start_time(x.first_rain, x.last_rain, minute_window): ].max(), 
        axis = 1
    ).to_numpy()
    return peak_rainfall_intensity*60/minute_window

def custom_mean(data_window, minute_window):
    return data_window.sum(where = ~np.isnan(data_window))/minute_window


def calculate_start_time(first_rain, last_rain, minute_window = 5):
    if last_rain - first_rain < np.timedelta64(minute_window, 'm'):
        return 0
    return first_rain + np.timedelta64(minute_window, 'm')