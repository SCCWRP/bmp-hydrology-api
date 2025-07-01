# BMP Hydrology Calculator API

This is a Flask application served as an API for [https://github.com/SCCWRP/bmp-hydrology-calculator](https://github.com/SCCWRP/bmp-hydrology-calculator).

## Overview

This API provides endpoints for hydrological calculations related to Best Management Practices (BMPs), including rainfall event analysis, flow statistics, and infiltration modeling. It is designed to be used as a backend for the BMP Hydrology Calculator web application.

## Features

- **Rainfall Event Analysis**: Detects rainfall events, calculates total rainfall, rainfall intensity, and antecedent dry periods.
- **Flow Analysis**: Computes runoff volume, duration, peak flow rates, and percent change between inflow and outflow.
- **Rain-Flow Event Linking**: Associates rainfall events with corresponding flow events for event-based analysis.
- **Infiltration Modeling**: Fits exponential decay models to piezometer data to estimate infiltration rates.

## API Endpoints

### `GET /`
Returns the main index page.

### `GET /api/docs`
Returns the Swagger UI documentation page.

### `POST /api/rain`
Accepts rainfall data and returns statistics for detected rainfall events.

**Request Body Example:**
```json
{
  "rain": {
    "datetime": [...],
    "rain": [...]
  }
}
```

### `POST /api/flow`
Accepts flow data (inflow, outflow, bypass, etc.) and returns flow statistics.

**Request Body Example:**
```json
{
  "inflow1": {
    "datetime": [...],
    "flow": [...],
    "time_unit": "L/s"
  },
  "outflow": {
    "datetime": [...],
    "flow": [...],
    "time_unit": "L/s"
  }
}
```

### `POST /api/rainflow`
Accepts both rain and flow data, links rain events to flow events, and returns combined statistics.

### `POST /api/infiltration`
Accepts piezometer depth data and parameters for smoothing and regression, fits exponential decay models, and returns infiltration rates and fit statistics.

**Request Body Example:**
```json
{
  "data": [
    {"datetime": "...", "PZ1": ..., "PZ2": ...},
    ...
  ],
  "SMOOTHING_WINDOW": 5,
  "REGRESSION_WINDOW": 720,
  "REGRESSION_THRESHOLD": 0.999
}
```

## Usage

1. Install dependencies (see `requirements.txt`).
2. Set the `FLASK_APP_SECRET_KEY` environment variable.
3. Run the Flask app (e.g., `flask run` or via WSGI).
4. Use the `/api/docs` endpoint for interactive API documentation.

## Project Structure

- `proj/app.py`: Main Flask application and API endpoints.
- `proj/functions/`: Core hydrology calculation modules.
- `proj/utils/`: Utility functions for data formatting and validation.
- `proj/templates/`: HTML templates for index and Swagger UI.
- `proj/static/`: Static files (JS, CSS, OpenAPI YAML).

## License

See [LICENSE](https://github.com/SCCWRP/bmp-hydrology-calculator/blob/main/LICENSE) in the main project repository.

