-- Release Day Radar — analysis queries (MySQL 8)
-- Each query starts with a comment saying which question it answers.
-- src/09_load_mysql.py runs every query in this file and saves the results to outputs/tables/sql_q*.csv
-- Queries are separated by a line containing only ";" at the end of the statement.

-- Q1. What is in the database? Row count of every table (evidence for "row counts per table").
SELECT 'films' AS table_name, COUNT(*) AS row_count FROM films
UNION ALL SELECT 'trailers', COUNT(*) FROM trailers
UNION ALL SELECT 'box_office', COUNT(*) FROM box_office
UNION ALL SELECT 'comments', COUNT(*) FROM comments
UNION ALL SELECT 'trends_daily', COUNT(*) FROM trends_daily;

-- Q2. (JOIN + GROUP BY) For each film: total trailer views across all language versions,
--     next to its first-weekend collection per day. This is the core comparison of our question.
SELECT f.film_id,
       f.language,
       COUNT(t.trailer_id)            AS trailer_versions,
       SUM(t.views)                   AS total_trailer_views,
       b.value_cr                     AS first_weekend_per_day_cr
FROM films f
JOIN trailers   t ON t.film_id = f.film_id
JOIN box_office b ON b.film_id = f.film_id AND b.metric = 'first_weekend_per_day'
GROUP BY f.film_id, f.language, b.value_cr
ORDER BY total_trailer_views DESC;

-- Q3. (JOIN + GROUP BY) Velocity: how many comments arrived in the first 72 hours after the
--     main trailer went live, and the average comments per hour in that window.
--     "Went live" = the earlier of the API publish time and the first comment (Raid 2's trailer
--     was commented on 20.7 h before its official publish time).
SELECT c.film_id,
       COUNT(*)                                   AS comments_first_72h,
       ROUND(COUNT(*) / 72, 1)                    AS comments_per_hour_72h
FROM comments c
JOIN (SELECT t.film_id, LEAST(t.publish_ts, MIN(c2.published_ts)) AS start_ts
      FROM trailers t
      JOIN comments c2 ON c2.film_id = t.film_id
      WHERE t.is_main_trailer = 1
      GROUP BY t.film_id, t.publish_ts) s ON s.film_id = c.film_id
WHERE c.published_ts >= s.start_ts
  AND c.published_ts <  s.start_ts + INTERVAL 72 HOUR
GROUP BY c.film_id
ORDER BY comments_first_72h DESC;

-- Q4. (JOIN + GROUP BY) Do Hindi and regional films get different trailer sentiment?
--     Mean VADER score, ignoring comments VADER could not read (score exactly 0).
SELECT CASE WHEN f.language = 'Hindi' THEN 'Hindi' ELSE 'Regional' END AS film_group,
       COUNT(DISTINCT f.film_id)          AS films,
       COUNT(*)                           AS scored_comments,
       ROUND(AVG(c.vader_compound), 3)    AS mean_vader_nonzero,
       ROUND(AVG(c.vader_compound > 0.05), 3) AS share_positive
FROM comments c
JOIN films f ON f.film_id = c.film_id
WHERE c.vader_compound <> 0
GROUP BY film_group;

-- Q5. (JOIN + window function) When did Google search interest peak, relative to release day?
--     A peak on release day means search follows the release, not the trailer.
SELECT film_id, peak_date, release_date, DATEDIFF(peak_date, release_date) AS peak_days_after_release, interest
FROM (
    SELECT td.film_id, td.date AS peak_date, f.release_date, td.interest,
           ROW_NUMBER() OVER (PARTITION BY td.film_id ORDER BY td.interest DESC, td.date) AS rn
    FROM trends_daily td
    JOIN films f ON f.film_id = td.film_id
) ranked
WHERE rn = 1
ORDER BY peak_days_after_release;

-- Q6. (GROUP BY) Missing values: which films lack a budget, and how many box-office metrics does each film have?
SELECT f.film_id,
       f.budget_cr IS NULL          AS budget_missing,
       COUNT(DISTINCT b.metric)     AS box_office_metrics,
       GROUP_CONCAT(DISTINCT b.source ORDER BY b.source SEPARATOR ' + ') AS sources
FROM films f
LEFT JOIN box_office b ON b.film_id = f.film_id
GROUP BY f.film_id, f.budget_cr
ORDER BY budget_missing DESC, f.film_id;

-- Q7. (JOIN + GROUP BY) Hindi vs regional: average first-weekend collection per day and average trailer views.
SELECT CASE WHEN f.language = 'Hindi' THEN 'Hindi' ELSE 'Regional' END AS film_group,
       COUNT(*)                          AS films,
       ROUND(AVG(b.value_cr), 1)         AS avg_first_weekend_per_day_cr,
       ROUND(AVG(v.total_views) / 1e6, 1) AS avg_trailer_views_millions
FROM films f
JOIN box_office b ON b.film_id = f.film_id AND b.metric = 'first_weekend_per_day'
JOIN (SELECT film_id, SUM(views) AS total_views FROM trailers GROUP BY film_id) v ON v.film_id = f.film_id
GROUP BY film_group;
