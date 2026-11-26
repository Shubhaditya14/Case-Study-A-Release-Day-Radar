# Release Day Radar

Case Study A for Data and Storytelling, Module 1. Team: Sata and Dory Letting.

This project checks whether trailer buzz on YouTube predicted first-weekend box office for 10 Hindi and regional films released in 2025–26.

The report is in `report/report.pdf` (and `report/report.docx`).

## Requirements

- macOS or Linux
- uv (for Python 3.12)
- Java 17 or newer (for PySpark)
- Docker (for MySQL 8)
- Graphviz

## Setup

```bash
git clone https://github.com/Shubhaditya14/Case-Study-A-Release-Day-Radar.git
cd Case-Study-A-Release-Day-Radar
make setup
cp .env.example .env
```

Fill in `.env`:

- `YT_API_KEY`: a YouTube Data API v3 key from Google Cloud Console
- `TMDB_API_KEY`: an API key from themoviedb.org
- `MYSQL_*`: your MySQL details

Start MySQL in Docker:

```bash
docker run -d --name radar-mysql -p 3307:3306 \
  -e MYSQL_ROOT_PASSWORD=yourpassword -e MYSQL_DATABASE=release_day_radar \
  -e MYSQL_USER=radar -e MYSQL_PASSWORD=yourpassword mysql:8.0
```

Copy the IMDb 50K reviews CSV to `data/manual/imdb_50k.csv`.

The Google Trends CSVs are already in `data/manual/`.

## Run

```bash
make smoke   # check every data source works
make all     # run the whole pipeline
```

Or run one stage at a time:

```bash
make collect   # download data (uses about 4,500 YouTube quota units)
make clean     # match film names, clean data, sentiment
make spark     # PySpark text job
make sql       # load MySQL and run the queries
make charts    # analysis and charts
make zip       # build the submission zip
```

## Folders

- `src/`: the Python scripts, numbered in the order they run
- `sql/`: database schema and queries
- `notebooks/`: the Spark and exploration notebooks
- `data/manual/`: hand-made inputs (film list, Trends CSVs)
- `data/clean/`: the final cleaned tables
- `outputs/charts/`: the charts
- `outputs/tables/`: result tables
- `outputs/cleaning_log.csv`: every cleaning decision
- `report/`: the final report

## Notes

- `data/raw/` is not in the repo. It holds commenter usernames and is about 370 MB. `make collect` downloads it again.
- API keys stay in `.env`, which is not committed.

## AI disclosure

In line with the course policy, we used Claude Opus (Anthropic) as an assistant for research, coding and drafting the report. The team chose the question, approved the films, confirmed the uncertain matches, agreed the cleaning rules and reviewed every result. All numbers come from our code and the data we collected. See Appendix I of the report for details.
