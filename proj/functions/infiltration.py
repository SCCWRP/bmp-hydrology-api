import numpy as np
from scipy.signal import medfilt
from scipy.optimize import curve_fit

# Global default parameters (will be overridden by the API payload if provided)
SMOOTHING_WINDOW = 5  # e.g., 5 minute window for median filter
REGRESSION_WINDOW = 720  # e.g., 12 hour window (in minutes) for regression
REGRESSION_THRESHOLD = 0.999  # Minimum acceptable R-squared value


def smooth_timeseries(depth, kernel_size=SMOOTHING_WINDOW):
    """Apply a median filter to smooth the depth data."""
    return medfilt(depth, kernel_size)


def exponential_decay(t, y0, k):
    """Exponential decay function."""
    return y0 * np.exp(-k * t)


def fit_exponential_decay(time, depth, window_size):
    """
    Fits an exponential decay model to a time series of depth measurements within a sliding window.
    Returns:
        best_window: tuple of (window_time, window_depth)
        best_params: list of parameters [y0, k] for the best fit
        best_fit: array of fitted values (not used in the API output)
        best_r_squared: best R-squared value obtained
    """
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

            try:
                # Provide an initial guess for the parameters
                initial_guess = [window_depth[0], 0.1]
                params, _ = curve_fit(
                    exponential_decay,
                    window_time_numeric,
                    window_depth,
                    p0=initial_guess,
                    maxfev=10000,
                )
                # Calculate the R-squared value
                residuals = window_depth - exponential_decay(
                    window_time_numeric, *params
                )
                ss_res = np.sum(residuals**2)
                ss_tot = np.sum((window_depth - np.mean(window_depth)) ** 2)
                r_squared = 1 - (ss_res / ss_tot)

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
            window_size -= 60

    return best_window, best_params, best_fit, best_r_squared
