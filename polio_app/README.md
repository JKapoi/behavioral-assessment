# Polio Virus Heatmap & Cluster Map (Shiny for Python)

Python port of `../app.R`: filters (Year, Country, Virus Type, Emergence), a heatmap
tab with virus-coloured points and popups (zoom 5 and closer), a cluster map tab, and a PNG
download of the heatmap.

## Run

```bash
cd polio_app
pip install -r requirements.txt
playwright install chromium      # needed once, for "Download Heatmap (PNG)"
shiny run --reload app.py        # open http://127.0.0.1:8000
```

## Configure (optional environment variables)

| Variable | Default |
|---|---|
| `POLIO_DATA_PATH` | `AllPolioviruses_20230406_V2.xlsx` next to `app.py`, else `C:/Users/ADMIN/Documents/AAAPEPVirus/AScript/AllPolioviruses_20230406_V2.xlsx` |
| `POLIO_DATA_SHEET` | `AllPolioviruses_20230303` |
| `MAPTILER_API_KEY` | the key from `app.R`; set it to empty to use plain OpenStreetMap tiles |

Windows (PowerShell): `$env:POLIO_DATA_PATH="C:\path\to\file.xlsx"; shiny run app.py`

## Deploy

shinyapps.io / Posit Connect: `rsconnect deploy shiny polio_app`. Put the Excel file in
`polio_app/` so it is uploaded with the app. PNG export needs Chromium on the server
(`playwright install --with-deps chromium`). If the server can't provide it, the button
shows an error and the maps still work.
