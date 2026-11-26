"""
Step 08 — PySpark text job over ALL our text: trailer comments + the IMDb 50K corpus.

Why Spark for ~400k rows? Honestly, pandas could do this on a laptop. We use Spark because
(a) the brief asks for a big-data tool, and (b) the same code would run unchanged on a cluster
if we tracked 100 films live instead of 10 — exploding text into words multiplies rows
(~400k texts become millions of word rows), which is exactly where Spark's split-into-partitions
model pays off.

Stages (row counts printed before and after each one):
  1. Load   — comments (source = youtube_comments) UNION IMDb reviews (source = imdb_50k)
  2. Clean  — lowercase, keep letters only (any script), squeeze spaces, drop empty rows
  3. Length — characters and words per text
  4. Terms  — split into words, drop stopwords and 1-letter tokens
  5. Aggregate — per film and source: rows, mean length; top 10 terms per film

Runs in local mode:  .venv/bin/python src/08_spark_text_job.py
"""

import os
import sys

import pandas as pd
from pyspark.ml.feature import StopWordsRemover
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

sys.path.insert(0, os.path.dirname(__file__))
from utils import DATA_CLEAN, DATA_MANUAL, OUT_TABLES, ROOT  # noqa: E402

# English stopwords (Spark's built-in list) + common Hindi/Hinglish fillers seen in our comments.
# Without the Hinglish list, the "top terms" for Hindi films are just "hai", "ka", "ki".
HINGLISH_STOPWORDS = ["hai", "hain", "ka", "ki", "ke", "ko", "se", "bhi", "na", "ho", "h", "ye", "yeh",
                      "aur", "nahi", "toh", "to", "ek", "mein", "me", "hi", "tha", "kya", "kar", "ne",
                      "wo", "woh", "jo", "par", "bhai", "sir", "ji"]
TOP_N = 10

stage_counts = []


def record(stage, df, note=""):
    """Count rows at a stage boundary and remember it for the report."""
    n = df.count()
    stage_counts.append({"stage": stage, "rows": n, "note": note})
    print(f"[{stage:<28}] {n:>12,} rows  {note}")
    return n


def start_spark():
    return (SparkSession.builder
            .master("local[*]")                      # local mode: all CPU cores of this laptop
            .appName("release-day-radar-text")
            .config("spark.driver.memory", "4g")
            .config("spark.sql.shuffle.partitions", "16")  # default 200 is overkill for one machine
            .config("spark.local.dir", os.environ.get("TMPDIR", "/tmp"))
            # Read and write the LOCAL disk, even if this machine has a Hadoop config pointing at HDFS
            .config("spark.hadoop.fs.defaultFS", "file:///")
            .config("spark.ui.showConsoleProgress", "false")
            .getOrCreate())


def load(spark):
    comments = (spark.read.option("header", True).option("multiLine", True).option("escape", '"')
                .csv(str(DATA_CLEAN / "comments.csv"))
                .select(F.col("film_id"), F.col("text_clean").alias("text"))
                .withColumn("source", F.lit("youtube_comments")))
    record("1a load comments", comments)

    imdb = (spark.read.option("header", True).option("multiLine", True).option("escape", '"')
            .csv(str(DATA_MANUAL / "imdb_50k.csv"))
            .dropDuplicates(["review"])               # same rule as step 07
            .select(F.lit("imdb_50k").alias("film_id"), F.col("review").alias("text"))
            .withColumn("source", F.lit("imdb_50k")))
    record("1b load imdb (deduplicated)", imdb)

    both = comments.unionByName(imdb)
    record("1c union", both, "must be ≥ 50,000")
    return both


def clean(df):
    cleaned = (df
               .withColumn("text", F.lower(F.col("text")))
               .withColumn("text", F.regexp_replace("text", r"<br\s*/?>", " "))   # IMDb HTML line breaks
               # keep letters (\p{L}) AND combining marks (\p{M}) of any script: Indian vowel signs are
               # combining marks, so dropping them would cut "ಕನ್ನಡ" into broken pieces
               .withColumn("text", F.regexp_replace("text", r"[^\p{L}\p{M}\s]", " "))
               .withColumn("text", F.trim(F.regexp_replace("text", r"\s+", " ")))
               .filter(F.col("text") != ""))
    record("2 clean (non-empty)", cleaned, "emoji-only / number-only texts drop out here")
    return cleaned


def measure(df):
    measured = (df
                .withColumn("char_length", F.length("text"))
                .withColumn("word_count", F.size(F.split("text", " "))))
    record("3 length measured", measured)
    return measured


def terms(df):
    words = df.withColumn("words", F.split("text", " "))
    remover = StopWordsRemover(inputCol="words", outputCol="terms",
                               stopWords=StopWordsRemover.loadDefaultStopWords("english") + HINGLISH_STOPWORDS)
    no_stop = remover.transform(words)

    exploded = no_stop.select("film_id", "source", F.explode("words").alias("term"))
    record("4a words (exploded)", exploded, "one row per word, before stopwords")

    kept = (no_stop.select("film_id", "source", F.explode("terms").alias("term"))
            .filter(F.length("term") > 1))
    record("4b terms (no stopwords)", kept)
    return kept


def aggregate(measured, kept):
    summary = (measured.groupBy("source", "film_id")
               .agg(F.count("*").alias("texts"),
                    F.round(F.avg("char_length"), 1).alias("mean_chars"),
                    F.round(F.avg("word_count"), 1).alias("mean_words"))
               .orderBy("source", "film_id"))
    record("5a summary by film+source", summary)

    counts = kept.groupBy("source", "film_id", "term").count()
    record("5b term counts", counts, "distinct (film, term) pairs")

    # Rank terms inside each film and keep the top 10
    rank = Window.partitionBy("film_id").orderBy(F.desc("count"), F.asc("term"))
    top = (counts.withColumn("rank", F.row_number().over(rank))
           .filter(F.col("rank") <= TOP_N)
           .orderBy("film_id", "rank"))
    record("5c top terms per film", top, f"top {TOP_N} × films")
    return summary, top


def main():
    spark = start_spark()
    spark.sparkContext.setLogLevel("ERROR")

    df = load(spark)
    df = clean(df)
    measured = measure(df).cache()   # reused by two later stages, so keep it in memory
    kept = terms(measured)
    summary, top = aggregate(measured, kept)

    OUT_TABLES.mkdir(parents=True, exist_ok=True)
    summary_pd = summary.toPandas()
    top_pd = top.toPandas()
    summary_pd.to_csv(OUT_TABLES / "spark_summary_by_film.csv", index=False)
    top_pd.to_csv(OUT_TABLES / "spark_top_terms.csv", index=False)
    pd.DataFrame(stage_counts).to_csv(OUT_TABLES / "spark_stage_counts.csv", index=False)

    print("\n", summary_pd.to_string(index=False))
    wide = top_pd.groupby("film_id")["term"].apply(lambda t: ", ".join(t))
    print("\nTop terms per film:\n" + wide.to_string())
    spark.stop()


if __name__ == "__main__":
    main()
