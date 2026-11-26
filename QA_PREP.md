# Q&A prep — every member should be able to answer all of this

Format for each script: **what it does**, the **3 lines that matter** and why, and **what breaks if you remove them**.

---

## src/utils.py — shared helpers
**What:** folder paths, the cleaning-log writer, a polite HTTP helper with retries, the Wikipedia User-Agent, and the **YouTube quota guard**.

1. `used = _reserve_units(cost)`, *before* `requests.get(...)` in `youtube_get`. Units are reserved before a call is sent. If the reservation would pass 10,000, the call is never made.
   *Without it:* a loop could spend past the daily quota, and the key gets blocked for the day.
2. `if "googleapis.com/youtube" in url: raise ...` in `http_get_json`. This stops anyone calling YouTube without going through the guard.
   *Without it:* one careless script bypasses the cap.
3. `os.replace(tmp, QUOTA_FILE)`, an atomic write. Ten download processes share one quota file, and a half-written file once crashed a process.
   *Without it:* random `JSONDecodeError` crashes during parallel downloads.

Also: `trailer_start_times()` defines when a trailer's buzz starts: the **earlier** of the API publish time and the first comment (because of the Raid 2 case).

## src/00_verify_films.py — choose the films
**What:** checks 18 candidates on Wikipedia, TMDb and YouTube and writes `film_list_candidates_checked.csv`.

1. `find_opening_weekend_sentences(html)` keeps only films whose page actually states a weekend figure.
2. `trailers = [v for v in videos if "trailer" in ...] or videos` makes a first guess at the trailer. We later found it picked wrong videos twice.
3. `youtube_get("search", ...)` is the expensive call (100 units), so it runs once per film.

*Without the weekend check,* we would have films with no outcome to correlate.

## src/01_collect_wikipedia.py — box office (structured)
**What:** MediaWiki API `action=parse` gives page HTML inside JSON. `pd.read_html` reads the infobox, and the article text is split into sentences.

1. `wiki_get({"action": "parse", "page": page, "prop": "text|revid"})` uses the official API, not scraping. The `revid` records exactly which version of the page we used.
2. `pd.read_html(io.StringIO(html), attrs={"class": "infobox vevent"})` turns the infobox table into a DataFrame.
3. `if phrase not in text: raise SystemExit(...)` is the **anti-fabrication check**: the chosen first-weekend phrase must appear word for word in the downloaded page.
   *Without it:* a typo or an edited page could silently put a wrong number in the report.

## src/02_collect_tmdb.py — metadata (semi-structured JSON)
1. `re.sub(r"\s*\(.*?\)", "", film.title)`: TMDb doesn't use Wikipedia's "(film)" suffix.
2. `search_movie(title, year, key)`: the year filter avoids old films with the same name.
3. `append_to_response=credits` gets details and cast in **one** call instead of two.

## src/03_collect_youtube.py — trailers + comments (semi-structured + unstructured)
1. `official_versions()`: a language version must have a title with "trailer", no promo words, and a length **within 10% of the main trailer**. Peddi's channel had 16 "trailer" videos (speeches, Shorts, livestreams) and only 1 real trailer.
2. `"order": "time"` plus paging through `nextPageToken` until done. Comments come newest first, so reaching trailer week means downloading them **all**. A 5,000 cap would contain no trailer-week comments.
3. `state_file.write_text(json.dumps(state))` after every page makes the download **resumable**. If quota runs out, rerunning continues from the same page.

## src/04_flatten_json.py — json_normalize
1. `pd.json_normalize(items)` turns nested JSON into dotted column names, e.g. `snippet.topLevelComment.snippet.publishedAt`. A before/after example is in Appendix C.
2. `df.drop(columns=present_private)` drops author name, channel ID and profile URL: the **privacy rule**.
3. `", ".join(g["name"] for g in details["genres"])` joins a list into one text cell so each film fits in one row.

## src/05_match_films.py — one film_id across sources
1. `normalise()`: lowercase, remove brackets, "trailer", language tags, text after "|", and punctuation.
2. `fuzz.token_sort_ratio` for full titles, `fuzz.partial_ratio` for YouTube titles and Trends terms. With `partial_ratio`, "Dhurandhar" (the 2025 prequel) would score 100 against "Dhurandhar: The Revenge" and import the wrong ₹1,350-crore gross. `token_sort_ratio` scores it 62.5, so it is **rejected**.
3. `decide()`: ≥ 95 accept, 70–94 a human confirms (M9), < 70 reject.

## src/06_clean_typecast.py — type casting and missing values
1. `parse_money_to_crore()` handles "₹797.34–809 crore[b]" → 803.17 (footnotes stripped, range → midpoint), Unicode minus "−", "est.", lakh, Indian grouping "1,25,00,000" → 1.25, and "$80 million" → ₹ at the ECB rate.
2. `to_ist()` converts YouTube's UTC strings to IST. *Without it,* an evening IST comment lands on the wrong day.
3. `first_weekend_per_day = value / weekend_days`. Thursday releases have 4-day weekends.

Missing values: budget NULL (not invented), "<1" in Trends → 0.5, empty comments dropped. Each is logged.

## src/07_sentiment.py — VADER
1. `imdb.drop_duplicates(subset="review")` removes 418 duplicates before computing accuracy.
2. `(compound >= 0.05)` → positive. This is VADER's documented cut-off.
3. `accuracy_score / f1_score` validates **before** using VADER on our data: 0.70 accuracy, 0.69 macro-F1.

## src/08_spark_text_job.py — PySpark
1. `.master("local[*]")` is local mode, using all CPU cores. `fs.defaultFS = file:///` forces the local disk (this Mac has a Hadoop config pointing at HDFS).
2. `regexp_replace("text", r"[^\p{L}\p{M}\s]", " ")` keeps letters **and combining marks**. Without `\p{M}`, Indian vowel signs are stripped and words break into fragments.
3. `F.explode("terms")` creates one row per word: 400,008 texts become 14.3 million word rows. That size is why Spark is used.

## src/09_load_mysql.py — relational model
1. Execute `sql/schema.sql` first: primary keys and foreign keys.
2. Load order `films → trailers → box_office → comments → trends_daily`. Children need the parent row to exist (foreign key).
3. `to_sql(..., chunksize=5000, method="multi")`: inserting 350k comments in one statement would exceed MySQL's packet limit.

## src/10_analysis.py — the numbers behind the story
1. `spearmanr(...)` is rank correlation (see Q1 below).
2. `zscore(np.log10(...))`: log first, then z-score (see Q2).
3. `buzz_index_loo()`: each film is scored by weights learned from the *other 9*, an honest out-of-sample test.

Also `bot_check()` (same-hour copy-paste bursts) and `prepublish_check()` (Raid 2: 88.6% copy-paste before official publish).

## src/11_charts.py — charts
1. Titles are built from the result tables, e.g. `f"(ρ = {rho:.2f}, n = {n})"`, so no number is typed by hand.
2. `GROUP_COLOR = {False: BLUE, True: ORANGE}`: Hindi is always blue and regional always orange, on every chart.
3. `ax.set_xscale("log")`: views span 16M to 130M, and on a linear scale most films crowd into a corner.

## src/12, 13, 14 — evidence tables, the Sheets comparison, the report
- `12` builds the source register **from the collectors' access log** (real dates), the data inventory, and the V profile (measured, not estimated).
- `13` compares the Google Sheets result with pandas, string by string.
- `14` fills `{{num:...}}` and `{{table:...}}` in the templates, so every report number traces to a file.

---

# 25 likely viva questions

1. **Why Spearman and not Pearson?** With n = 10 and one film far bigger than the rest (Dhurandhar: The Revenge, ₹186 cr/day), Pearson would be driven by that one point. Spearman uses only the *order* of films, so one outlier can't dominate. It also doesn't assume a straight-line relationship.
2. **Why z-scores, and why log first?** Views (millions), crores and sentiment (−1 to +1) can't share a scale until each becomes "standard deviations from the average". Views span 8×, so we take log10 first, so the biggest trailer doesn't flatten everyone else.
3. **Is this causal?** No. Star power, screen count, holidays, franchise status and marketing spend raise *both* trailer views and collections. Views are also today's totals, so a hit's trailer keeps collecting views after release (reverse causation).
4. **Why did you drop 8 of the 18 candidate films?** No stated first-weekend figure on Wikipedia (War 2, Coolie, They Call Him OG, Dhurandhar give only opening *day*), no figure at all (Thamma, Jolly LLB 3, Border 2), or too new (Jailer 2).
5. **What is json_normalize doing?** It walks nested JSON and makes one column per leaf, joining the path with dots. `snippet → topLevelComment → snippet → publishedAt` becomes `snippet.topLevelComment.snippet.publishedAt`. One comment becomes one row.
6. **Why PySpark for ~400k rows?** pandas could do it on a laptop; we say so honestly. Splitting into words makes 14.3 million rows, which is where Spark's partitioned processing pays off. The same code would run unchanged on a cluster for hundreds of films. The brief also requires a big-data tool.
7. **Explain your JOIN query (Q2).** `films` JOIN `trailers` on `film_id` (one film, several language versions) JOIN `box_office` on `film_id` where `metric = 'first_weekend_per_day'`, then `GROUP BY film` with `SUM(views)`. The result is one row per film: total trailer views next to its weekend.
8. **How did you match film names?** Normalise (lowercase, strip brackets, "trailer", language tags, text after "|", punctuation), then rapidfuzz. ≥ 95 accept, 70–94 a person confirms, < 70 reject. 56 strings → 10 IDs. 2 were confirmed by a human and 1 rejected.
9. **Why VADER?** It's built for short social-media text (understands "!!!", CAPS, emojis), needs no training data, and is easy to explain. We validated it first: 0.70 accuracy on IMDb. Its weaknesses (Hinglish, Indian scripts, sarcasm) are reported.
10. **Nominal vs ordinal in your data?** Nominal has categories with no order: language, genre, film_id, the IMDb label. Ordinal has an order but no fixed gaps: the trade rank in the yearly list, and the Trends index (relative, scaled per export). Discrete counts: views, comments, runtime minutes. Continuous: crores, VADER score.
11. **Why "per day" for the first weekend?** Six of the ten films opened on a Thursday and have 4-day weekends. A 4-day total would look about a third bigger than a 3-day one for the same daily business.
12. **How did you convert "$80 million"?** At the ECB reference rate on its release date (₹93.25/USD, from the Frankfurter API), logged. It's "over $80 million", so it's a lower bound.
13. **What did you do about missing budgets?** Kantara has none published, and Dhurandhar: The Revenge's is shared with part 1. Both are NULL. We did not halve the combined figure, because that would invent a number.
14. **Why not cap comments at 5,000 per film?** YouTube returns them newest first. A 5,000 cap on Chhaava would contain only recent comments and zero from trailer week.
15. **What was the Raid 2 timestamp problem?** 16,245 comments were posted up to 20.7 hours *before* the official publish time. We start the trailer clock at the earlier of publish time and first comment. That cut the comments correlation from 0.56 to 0.37.
16. **…and why do you think Raid 2's buzz was seeded?** 88.6% of those early comments repeat text that appears 5+ times ("Can't wait" ×190). After publication, every film is at 18–51%. We can't prove who wrote them, so we flag rather than delete.
17. **How does the Buzz Index work, and is it any good?** It combines z-scored views, like ratio, comment volume, velocity and sentiment, each weighted by its rank correlation with the outcome. Weights are learned leaving the test film out. It called 6 of 10 above/below median, against about 5 for a coin toss. Not good enough to act on alone.
18. **Why did sentiment not help?** Partly the real world: the biggest opener had some of the least positive comments. Partly measurement: VADER is 70% accurate on English reviews, can't read 9% of our comments (Indian scripts), and scores 29% exactly 0.
19. **What is the cleaning log, and how is it produced?** One row per decision (problem, rows affected, action, why), 30+ rows. Each script appends its own rows with the counts it measured, so nothing is typed from memory.
20. **How do you protect commenters' privacy?** Usernames, channel IDs and profile URLs are dropped at flattening. The raw folder is gitignored. The committed sample replaces comment IDs with one-way hashes.
21. **How did you respect API limits?** The YouTube guard reserves units before every call (hard 10,000/day cap). Wikipedia gets a descriptive User-Agent and 1-second pauses. Retries back off. No scraping of IMDb or Sacnilk.
22. **Why is Google Trends only compared by shape?** Each export is scaled 0–100 to *its own* peak, so "100" for Lokah and "100" for Chhaava aren't the same number of searches.
23. **Spreadsheet vs pandas, which is better?** For 36 strings a spreadsheet is fine and visual. pandas is reproducible (`make all`), less error-prone (no copy-paste ranges) and scales to 350k rows. Both gave the same answers (Appendix D).
24. **Why MySQL with a separate box_office table in long format?** One row per film per metric (`film_id, metric, value_cr, source`) means new metrics or sources need no schema change. Keeping `source` lets us compare the infobox and the yearly list.
25. **What would you do with better data?** Capture view counts daily from trailer launch; use a licensed trade source with screen counts and day-wise collections; use a multilingual sentiment model; add Reddit and X; grow to 30+ films so the rule can be tested on unseen releases.

**Bonus, "show me in the code":** `grep -n "def " src/*.py` lists every function. Each one has a comment above it saying *why*.
