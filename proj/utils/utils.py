import pandas as pd
import json

# TODO: data validation - only accept 1, 5, 10, 15 min data


def load_data(request, valid_keys):
    # expects incoming data in json format
    if request.json is None:
        raise ValueError("No json sent")

    inc_data = request.get_json()

    if type(inc_data) != dict:
        raise ValueError("Data not parsed as a dict")

    data_types = set(inc_data.keys())

    if not data_types.issubset(set(valid_keys.keys())):
        raise ValueError(f"Invalid data types: {data_types - set(valid_keys.keys())}")

    for data_type in data_types:
        if set(inc_data[data_type].keys()) != valid_keys[data_type]:
            raise ValueError(f"Data type {data_type} has invalid keys")

    data = {}

    if request.path == "/api/rain":
        data = pd.DataFrame.from_dict(inc_data["rain"])

    elif request.path == "/api/flow":
        for data_type, df in inc_data.items():
            data[data_type] = pd.DataFrame.from_dict(df)

    elif request.path == "/api/rainflow":
        for data_type, df in inc_data.items():
            data[data_type] = pd.DataFrame.from_dict(df)
    else:
        raise ValueError("Some other error occurred")

    return data


def format_data(data):
    # need to make a time_index with resolution of 1 second in order to properly
    # use the window/rolling function later, since data may be recorded
    # with second precision
    # imputed timestamps will have nan values
    data["datetime"] = pd.to_datetime(data["datetime"]).sort_values()
    tmp = data.iloc[:, 0:2].set_index("datetime").squeeze(axis=1)
    # start from beginning of submitted data, end at the end, rounding to the
    # lower and upper minute values respectively
    time_index = pd.date_range(
        start=tmp.index.floor("T")[0], end=tmp.index.ceil("T")[-1], freq="1S"
    )
    formatted_data = pd.Series(data=tmp, index=time_index)
    return formatted_data


def format_statistics(df):
    # awkward, but need to use pandas to_json to correctly format NaNs to null for correct json spec,
    # then load that string to nest final dictionary object, for returning final json body + response
    df_dict = json.loads(df.to_json())

    # want final format to be {stat: [list, of, event, values]}
    # to_json() by default converts to {stat: { {"0": event_value_0}, {"1": event_value_1}, ... }
    for stat, event_dict in df_dict.items():
        event_list = []
        for value in event_dict.values():
            event_list.append(value)
        df_dict[stat] = event_list
    return df_dict
