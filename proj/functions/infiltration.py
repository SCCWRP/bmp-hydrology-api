import numpy as np
from scipy.optimize import curve_fit
import math

# Global default parameters (will be overridden by the API payload if provided)
SMOOTHING_WINDOW = 15  # e.g., 15 minute window for median filter
REGRESSION_WINDOW = 720  # e.g., 12 hour window (in minutes) for regression
REGRESSION_THRESHOLD = 0.999  # Minimum acceptable R-squared value


def smooth_timeseries(depth, smoothing_window=SMOOTHING_WINDOW):
    """Apply a median filter to smooth the depth data."""
    # Get the average time difference in seconds between consecutive depth measurements
    mean_delta_t_s = depth.index.to_series().diff().mean().total_seconds()
    # Divide 15 minutes by the mean delta time to get the filter size in terms of data points
    filter_size = min(math.ceil(smoothing_window * 60.0 / mean_delta_t_s), 1)
    return depth.rolling(window=f"{filter_size}s", center=True).median(), mean_delta_t_s / 60


def exponential_decay(t, y0, k, c):
    """Exponential decay function."""
    return y0 * np.exp(-k * t) + c


def fit_exponential_decay(time, depth, mean_delta_t_s, window_size):
    """
    Fits an exponential decay model to a time series of depth measurements within a sliding window.
    Returns:
        best_window: tuple of (window_time, window_depth)
        best_params: list of parameters [y0, k] for the best fit
        best_fit: array of fitted values (not used in the API output)
        best_r_squared: best R-squared value obtained
    """
    print("Starting fit_exponential_decay function")

    best_fit = None
    best_params = None
    best_r_squared = -np.inf
    best_window = None

    # Continue trying with a sliding window until the R-squared threshold is met

    while best_r_squared < REGRESSION_THRESHOLD and window_size > 1:
        print(f"Trying window size: {window_size}")

        for i in range(len(time) - window_size + 1):
            window_time = time.iloc[i : i + window_size].values
            window_depth = depth.iloc[i : i + window_size].values
            # Convert datetime to numeric values (seconds since the start of the window)
            window_time_numeric = (window_time - window_time[0]) / np.timedelta64(
                1, "s"
            )

            # Original data
            t_orig = np.array(window_time_numeric)
            y_orig = np.array(window_depth)

            # Normalize time to [0, 1] and depth to [0, 1]
            t_max = np.max(t_orig)
            y_max = np.max(y_orig)
            t_norm = t_orig / t_max if t_max != 0 else t_orig
            y_norm = y_orig / y_max if y_max != 0 else y_orig

            try:
                # Provide an initial guess for the parameters
                params, _ = curve_fit(
                    exponential_decay,
                    t_norm,
                    y_norm,
                )
                # Calculate the R-squared value
                residuals = y_norm - exponential_decay(t_norm, *params)
                ss_res = np.sum(residuals**2)
                ss_tot = np.sum((y_norm - np.mean(y_norm)) ** 2)
                r_squared = 1 - (ss_res / ss_tot)

                # Denormalize the params: y0, k, c
                params[0] = params[0] * y_max  # y0
                params[1] = params[1] / t_max  # k
                params[2] = params[2] * y_max  # c

                if r_squared > best_r_squared:
                    best_r_squared = r_squared
                    best_fit = exponential_decay(window_time_numeric, *params)
                    best_params = params
                    best_window = (window_time, window_depth)
            except RuntimeError:
                # If the fit fails, skip to the next window
                continue

        # If no acceptable fit is found, reduce the window size and try again
        if best_r_squared < REGRESSION_THRESHOLD:
            print(
                f"R-squared below threshold: {best_r_squared} for window size {window_size}."
            )
            window_size -= math.ceil(60 / mean_delta_t_s)
    print(f"Finished. Fitted parameters: {best_params}, R-squared: {best_r_squared}")
    return best_window, best_params, best_fit, best_r_squared, window_size
